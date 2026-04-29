from uuid import uuid4  # Para generar identificadores únicos de tarea (UUID v4 aleatorio)

from fastapi import HTTPException, status  # Para lanzar errores HTTP estándar

from db import get_connection              # Función que abre una conexión a PostgreSQL
from rabbitmq_client import publish_task_message  # Función que publica mensajes en RabbitMQ
from settings import settings             # Configuración centralizada (nombres de colas, etc.)
from repository import (
    create_task,          # Inserta una nueva tarea en la tabla 'tasks'
    get_order_by_id,      # Busca una orden activa por su ID
    get_task_by_id,       # Busca una tarea por su UUID
    list_orders,          # Devuelve todas las órdenes activas
    update_order,         # Actualiza campos de una orden existente
    update_task_status,   # Cambia el estado de una tarea (ej: pending → failed)
)


def get_orders():
    """
    Devuelve la lista de todas las órdenes activas (no eliminadas).
    Se abre una conexión, se consulta y el context manager la cierra automáticamente.
    """
    with get_connection() as conn:  # Abre conexión y la cierra al salir del bloque
        return list_orders(conn)    # Ejecuta SELECT WHERE deleted_at IS NULL


def get_order(order_id: int):
    """
    Busca una orden por ID. Si no existe o fue eliminada (soft-delete), lanza 404.
    """
    with get_connection() as conn:
        order = get_order_by_id(conn, order_id)  # Busca en BD (filtra deleted_at IS NULL)

    if order is None:  # None significa que no se encontró o está eliminada
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    return order  # Devuelve el dict con los datos de la orden


def update_existing_order(order_id: int, order_update):
    """
    Actualiza campos de una orden existente (PUT /orders/{id}).
    - Si no se pasa ningún campo → ValueError → 400 Bad Request
    - Si la orden no existe o está eliminada → 404 Not Found
    """
    try:
        with get_connection() as conn:
            order = update_order(
                conn,
                order_id,
                description=order_update.description,  # None si el cliente no lo envió
                status=order_update.status,             # None si el cliente no lo envió
                metadata=order_update.metadata,         # None si el cliente no lo envió
            )
            conn.commit()  # Confirma el UPDATE en la base de datos
    except ValueError as exc:
        # ValueError lo lanza update_order() cuando no se pasa ningún campo
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if order is None:  # UPDATE no encontró la orden (no existe o está eliminada)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    return order  # Devuelve la orden actualizada


def enqueue_order_creation(order_create):
    """
    Flujo completo de creación asíncrona de una orden:
    1. Genera un UUID único para rastrear esta operación
    2. Registra la tarea en la BD con estado 'pending'
    3. Publica el mensaje en la cola 'orders_create' de RabbitMQ
    4. Si RabbitMQ falla → marca la tarea como 'failed' en BD → lanza 503
    5. Devuelve la tarea al endpoint para la respuesta 202 Accepted
    """
    task_id = uuid4()  # Genera UUID v4 aleatorio — identifica de forma única esta operación
    payload = {
        # Datos que el worker necesitará para crear la orden en la BD
        "description": order_create.description,
        "status": order_create.status,
        "metadata": order_create.metadata,
    }

    # PASO 1: Registra la tarea en la tabla 'tasks' con status='pending', done=False
    # Esto se hace ANTES de publicar en RabbitMQ para tener trazabilidad desde el inicio
    with get_connection() as conn:
        task = create_task(conn, task_id=task_id, operation="create_order", payload=payload)
        conn.commit()  # Confirma el INSERT en la BD

    try:
        # PASO 2: Publica el mensaje en la cola de RabbitMQ que el worker_post consume
        publish_task_message(
            {
                "task_id": str(task_id),      # El worker usará esto para actualizar la tarea en BD
                "operation": "create_order",  # Indica qué operación debe ejecutar el worker
                "payload": payload,           # Datos necesarios para ejecutar la operación
            },
            queue=settings.rabbitmq_queue_create,  # Cola: "orders_create"
        )
    except Exception as exc:
        # PASO 3 (solo si falla): Si RabbitMQ no está disponible o hay error de red,
        # actualiza la tarea a 'failed' en BD para que el cliente vea el error al consultar
        with get_connection() as conn:
            task = update_task_status(conn, task_id, status="failed", done=True, error_message=str(exc))
            conn.commit()
        # Lanza 503 Service Unavailable — el sistema de mensajería no está disponible
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not publish create_order task to RabbitMQ.",
        ) from exc

    return task  # Devuelve la tarea 'pending' → el endpoint responde 202 con el task_id


def enqueue_order_deletion(order_id: int):
    """
    Flujo completo de eliminación asíncrona de una orden:
    1. Verifica que la orden existe y no está ya eliminada → 404 si no
    2. Genera un UUID para rastrear esta operación
    3. Registra la tarea en BD con status='pending'
    4. Publica el mensaje en la cola 'orders_delete'
    5. Si RabbitMQ falla → marca la tarea como 'failed' → lanza 503
    6. Devuelve la tarea al endpoint para la respuesta 202 Accepted
    """
    # Verifica que la orden existe ANTES de encolarla — evita tareas huérfanas
    with get_connection() as conn:
        order = get_order_by_id(conn, order_id)  # Busca orden activa (WHERE deleted_at IS NULL)

    if order is None:  # La orden no existe o ya fue eliminada
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    task_id = uuid4()              # UUID único para esta operación de borrado
    payload = {"order_id": order_id}  # El worker necesita el ID para hacer el soft-delete

    # Registra la tarea en BD antes de publicar en RabbitMQ
    with get_connection() as conn:
        task = create_task(
            conn,
            task_id=task_id,
            operation="delete_order",
            payload=payload,
            target_order_id=order_id,  # Enlaza la tarea con la orden que se va a eliminar
        )
        conn.commit()  # Confirma el INSERT

    try:
        # Publica el mensaje en la cola que el worker_delete consume
        publish_task_message(
            {
                "task_id": str(task_id),       # Para que el worker actualice el estado de esta tarea
                "operation": "delete_order",   # Indica qué handler ejecutar en el worker
                "payload": payload,            # Contiene el order_id a eliminar
            },
            queue=settings.rabbitmq_queue_delete,  # Cola: "orders_delete"
        )
    except Exception as exc:
        # Si RabbitMQ no está disponible, marca la tarea como fallida en BD
        with get_connection() as conn:
            task = update_task_status(conn, task_id, status="failed", done=True, error_message=str(exc))
            conn.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not publish delete_order task to RabbitMQ.",
        ) from exc

    return task  # Devuelve la tarea 'pending' → endpoint responde 202


def get_task(task_id):
    """
    Busca una tarea por su UUID.
    El cliente usa este endpoint para saber si su operación asíncrona terminó.
    Devuelve 404 si el task_id no existe en la tabla 'tasks'.
    """
    with get_connection() as conn:
        task = get_task_by_id(conn, task_id)  # Busca en BD por UUID

    if task is None:  # task_id no existe en la tabla tasks
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    return task  # Devuelve el dict con status, done, error_message, etc.
