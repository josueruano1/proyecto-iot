from psycopg2.extras import Json  # Envuelve dicts Python para insertarlos como JSONB en PostgreSQL


def mark_task_processing(conn, task_id):
    """
    Actualiza la tarea a status='processing' cuando el worker comienza a procesarla.
    Esto hace visible en GET /tasks/{id} que el mensaje fue tomado por el worker.
    done=FALSE indica que la tarea aún no ha terminado.
    error_message=NULL limpia cualquier error previo (en caso de reintento).
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE tasks
            SET status = 'processing', done = FALSE, error_message = NULL
            WHERE task_id = %s
            """,
            (str(task_id),),  # task_id como string (columna es de tipo uuid en PostgreSQL)
        )


def mark_task_failed(conn, task_id, error_message: str):
    """
    Actualiza la tarea a status='failed' cuando ocurre un error durante el procesamiento.
    done=TRUE indica que no se reintentará automáticamente.
    completed_at=NOW() registra cuándo terminó (aunque con fallo).
    El error_message guarda el mensaje de la excepción para diagnóstico.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE tasks
            SET status = 'failed', done = TRUE, error_message = %s, completed_at = NOW()
            WHERE task_id = %s
            """,
            (error_message, str(task_id)),  # Primero el error, luego el task_id para el WHERE
        )


def complete_task(conn, task_id, target_order_id=None):
    """
    Actualiza la tarea a status='completed' cuando la operación terminó exitosamente.
    COALESCE(%s, target_order_id): si se pasa un target_order_id, lo actualiza;
    si es None, mantiene el valor que ya tenía en la BD.
    Este campo enlaza la tarea con la orden que se creó o eliminó.
    completed_at=NOW() registra el timestamp de finalización exitosa.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE tasks
            SET target_order_id = COALESCE(%s, target_order_id),
                status = 'completed',
                done = TRUE,
                error_message = NULL,
                completed_at = NOW()
            WHERE task_id = %s
            """,
            (target_order_id, str(task_id)),  # COALESCE toma el nuevo ID o mantiene el existente
        )


def handle_create_order(conn, task_id, payload: dict):
    """
    Ejecuta la creación real de la orden en PostgreSQL.
    Es llamado por el worker_post cuando recibe un mensaje de la cola 'orders_create'.

    Flujo:
        1. Extrae los campos del payload (description es obligatorio)
        2. Inserta la nueva fila en la tabla orders
        3. Obtiene el order_id generado por la secuencia de PostgreSQL
        4. Marca la tarea como completed con el order_id recién creado
    """
    # Extrae los campos del payload del mensaje RabbitMQ
    description = payload.get("description")
    if not description:  # description es obligatorio — sin él no se puede crear la orden
        raise ValueError("create_order payload must include a description.")

    order_status = payload.get("status", "created")  # Default 'created' si no se envió
    metadata = payload.get("metadata", {})            # Default {} si no se envió metadata

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO orders (description, status, metadata)
            VALUES (%s, %s, %s)
            RETURNING order_id
            """,
            # Json(metadata) convierte el dict Python a JSONB de PostgreSQL
            (description, order_status, Json(metadata)),
        )
        row = cursor.fetchone()  # Obtiene el order_id generado por la secuencia SERIAL

    # Marca la tarea como completed y registra qué orden fue creada
    complete_task(conn, task_id, target_order_id=row["order_id"])


def handle_delete_order(conn, task_id, payload: dict):
    """
    Ejecuta el soft-delete de una orden en PostgreSQL.
    Es llamado por el worker_delete cuando recibe un mensaje de la cola 'orders_delete'.

    Soft-delete significa que la fila NO se elimina físicamente:
    - Se actualiza status a 'deleted'
    - Se registra deleted_at = NOW()
    La orden queda invisible para GET /orders (que filtra WHERE deleted_at IS NULL)
    pero sigue en la base de datos para auditoría.

    Flujo:
        1. Extrae el order_id del payload
        2. Hace UPDATE con deleted_at = NOW() solo si no está ya eliminada
        3. Si la orden ya no existe o ya estaba eliminada → raise ValueError
        4. Marca la tarea como completed
    """
    order_id = payload.get("order_id")
    if order_id is None:  # order_id es obligatorio en el payload del mensaje
        raise ValueError("delete_order payload must include an order_id.")

    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE orders
            SET status = 'deleted', deleted_at = NOW()
            WHERE order_id = %s AND deleted_at IS NULL
            RETURNING order_id
            """,
            (order_id,),  # Tupla con el ID de la orden a eliminar
        )
        row = cursor.fetchone()  # None si la orden no existía o ya estaba eliminada

    if row is None:
        # La orden no existe o ya fue eliminada por otro request simultáneo
        raise ValueError(f"Order {order_id} not found or already deleted.")

    # Marca la tarea como completed con el order_id que fue soft-deleted
    complete_task(conn, task_id, target_order_id=order_id)
