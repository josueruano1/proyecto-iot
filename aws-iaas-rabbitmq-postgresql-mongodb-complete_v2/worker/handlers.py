from psycopg2.extras import Json


def mark_task_processing(conn, task_id):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE tasks
            SET status = 'processing', done = FALSE, error_message = NULL
            WHERE task_id = %s
            """,
            (str(task_id),),
        )


def mark_task_failed(conn, task_id, error_message: str):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE tasks
            SET status = 'failed', done = TRUE, error_message = %s, completed_at = NOW()
            WHERE task_id = %s
            """,
            (error_message, str(task_id)),
        )


def complete_task(conn, task_id, target_order_id=None):
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
            (target_order_id, str(task_id)),
        )


def handle_create_order(conn, task_id, payload: dict):
    description = payload.get("description")
    if not description:
        raise ValueError("create_order payload must include a description.")

    order_status = payload.get("status", "created")
    metadata = payload.get("metadata", {})

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO orders (description, status, metadata)
            VALUES (%s, %s, %s)
            RETURNING order_id
            """,
            (description, order_status, Json(metadata)),
        )
        row = cursor.fetchone()

    complete_task(conn, task_id, target_order_id=row["order_id"])


def handle_delete_order(conn, task_id, payload: dict):
    order_id = payload.get("order_id")
    if order_id is None:
        raise ValueError("delete_order payload must include an order_id.")

    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE orders
            SET status = 'deleted', deleted_at = NOW()
            WHERE order_id = %s AND deleted_at IS NULL
            RETURNING order_id
            """,
            (order_id,),
        )
        row = cursor.fetchone()

    if row is None:
        raise ValueError(f"Order {order_id} not found or already deleted.")

    complete_task(conn, task_id, target_order_id=order_id)
