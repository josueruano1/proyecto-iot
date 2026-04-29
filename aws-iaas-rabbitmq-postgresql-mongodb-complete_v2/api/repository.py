from datetime import datetime, timezone  # Para calcular timestamps de completado en UTC
from uuid import UUID                     # Para tipar los task_id que son UUID

from psycopg2.extras import Json          # Envuelve un dict Python para que psycopg2 lo inserte como JSONB


# Columnas que se seleccionan en todas las consultas a la tabla 'orders'
# Definirlas en una constante evita repetirlas en cada query y facilita el mantenimiento
ORDER_COLUMNS = """
    order_id,
    description,
    status,
    metadata,
    created_at,
    updated_at,
    deleted_at
"""

# Columnas que se seleccionan en todas las consultas a la tabla 'tasks'
TASK_COLUMNS = """
    task_id,
    operation,
    target_order_id,
    status,
    done,
    payload,
    error_message,
    created_at,
    updated_at,
    completed_at
"""


def create_task(conn, task_id: UUID, operation: str, payload: dict, target_order_id: int | None = None):
    """
    Inserta un nuevo registro en la tabla 'tasks' con estado inicial 'pending'.
    Devuelve la fila insertada como diccionario (gracias a RealDictCursor).

    El task_id se genera en service.py con uuid4() antes de llamar esta función.
    El payload es el JSON que el worker recibirá de RabbitMQ.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO tasks (task_id, operation, target_order_id, status, done, payload)
            VALUES (%s, %s, %s, 'pending', FALSE, %s)
            RETURNING {TASK_COLUMNS}
            """,
            # Convierte UUID a string porque PostgreSQL uuid puede recibir string
            # Json(payload) serializa el dict a JSONB de PostgreSQL
            (str(task_id), operation, target_order_id, Json(payload)),
        )
        return cursor.fetchone()  # Devuelve el registro recién insertado


def update_task_status(
    conn,
    task_id: UUID,
    status: str,
    done: bool,
    error_message: str | None = None,
):
    """
    Actualiza el estado de una tarea existente.
    Usado por service.py cuando RabbitMQ falla (status='failed', done=True).
    También podría usarse para marcar como completed si fuera necesario.
    Si done=True, registra el timestamp de completado en UTC.
    """
    # Solo registra completed_at si la tarea está terminando (done=True)
    completed_at = datetime.now(timezone.utc) if done else None
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE tasks
            SET status = %s,
                done = %s,
                error_message = %s,
                completed_at = %s
            WHERE task_id = %s
            RETURNING {TASK_COLUMNS}
            """,
            (status, done, error_message, completed_at, str(task_id)),
        )
        return cursor.fetchone()  # Devuelve la fila actualizada


def get_task_by_id(conn, task_id: UUID):
    """
    Busca y devuelve una tarea por su UUID.
    Devuelve None si no existe (el endpoint GET /tasks/{id} convierte None en 404).
    """
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT {TASK_COLUMNS} FROM tasks WHERE task_id = %s",
            (str(task_id),),  # Pasa el UUID como string en una tupla (psycopg2 requiere tupla)
        )
        return cursor.fetchone()  # None si no se encontró


def list_orders(conn):
    """
    Devuelve todas las órdenes activas (no eliminadas).
    El filtro 'WHERE deleted_at IS NULL' implementa el patrón de soft-delete:
    las órdenes eliminadas siguen en la BD pero tienen deleted_at != NULL.
    Ordenadas por order_id ASC para mostrarlas en orden de creación.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {ORDER_COLUMNS}
            FROM orders
            WHERE deleted_at IS NULL
            ORDER BY order_id ASC
            """
        )
        return cursor.fetchall()  # Lista de dicts, puede ser lista vacía []


def get_order_by_id(conn, order_id: int):
    """
    Busca una orden activa por su ID.
    El filtro 'AND deleted_at IS NULL' garantiza que las órdenes eliminadas (soft-delete)
    sean invisibles para los endpoints públicos.
    Devuelve None si la orden no existe o ya fue eliminada.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {ORDER_COLUMNS}
            FROM orders
            WHERE order_id = %s AND deleted_at IS NULL
            """,
            (order_id,),  # Tupla con el ID buscado
        )
        return cursor.fetchone()  # None si no se encontró o fue eliminada


def update_order(conn, order_id: int, description=None, status=None, metadata=None):
    """
    Actualiza campos opcionales de una orden activa (PUT /orders/{id}).
    Solo modifica los campos que no son None — construye el SET dinámicamente.
    Si no se pasa ningún campo, lanza ValueError (servicio convierte a 400).
    Devuelve None si la orden no existe o está eliminada.
    """
    assignments = []  # Lista de fragmentos SQL: ["description = %s", "status = %s"]
    values = []       # Lista de valores correspondientes a cada %s

    # Agrega solo los campos que el cliente quiere actualizar
    if description is not None:
        assignments.append("description = %s")  # Agrega fragmento SQL
        values.append(description)               # Agrega el valor al bind
    if status is not None:
        assignments.append("status = %s")
        values.append(status)
    if metadata is not None:
        assignments.append("metadata = %s")
        values.append(Json(metadata))            # Envuelve en Json() para serializar como JSONB

    if not assignments:  # Si no se proporcionó ningún campo, es un error de negocio
        raise ValueError("At least one field must be provided for update.")

    values.append(order_id)  # El order_id va al final para el WHERE

    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE orders
            SET {', '.join(assignments)}
            WHERE order_id = %s AND deleted_at IS NULL
            RETURNING {ORDER_COLUMNS}
            """,
            # Convierte la lista a tupla porque psycopg2 requiere tupla para los parámetros
            tuple(values),
        )
        return cursor.fetchone()  # None si la orden no existía o estaba eliminada
