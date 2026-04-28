from datetime import datetime, timezone
from uuid import UUID

from psycopg2.extras import Json


ORDER_COLUMNS = """
    order_id,
    description,
    status,
    metadata,
    created_at,
    updated_at,
    deleted_at
"""

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
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO tasks (task_id, operation, target_order_id, status, done, payload)
            VALUES (%s, %s, %s, 'pending', FALSE, %s)
            RETURNING {TASK_COLUMNS}
            """,
            (str(task_id), operation, target_order_id, Json(payload)),
        )
        return cursor.fetchone()


def update_task_status(
    conn,
    task_id: UUID,
    status: str,
    done: bool,
    error_message: str | None = None,
):
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
        return cursor.fetchone()


def get_task_by_id(conn, task_id: UUID):
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT {TASK_COLUMNS} FROM tasks WHERE task_id = %s",
            (str(task_id),),
        )
        return cursor.fetchone()


def list_orders(conn):
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {ORDER_COLUMNS}
            FROM orders
            WHERE deleted_at IS NULL
            ORDER BY order_id ASC
            """
        )
        return cursor.fetchall()


def get_order_by_id(conn, order_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {ORDER_COLUMNS}
            FROM orders
            WHERE order_id = %s AND deleted_at IS NULL
            """,
            (order_id,),
        )
        return cursor.fetchone()


def update_order(conn, order_id: int, description=None, status=None, metadata=None):
    assignments = []
    values = []

    if description is not None:
        assignments.append("description = %s")
        values.append(description)
    if status is not None:
        assignments.append("status = %s")
        values.append(status)
    if metadata is not None:
        assignments.append("metadata = %s")
        values.append(Json(metadata))

    if not assignments:
        raise ValueError("At least one field must be provided for update.")

    values.append(order_id)

    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE orders
            SET {', '.join(assignments)}
            WHERE order_id = %s AND deleted_at IS NULL
            RETURNING {ORDER_COLUMNS}
            """,
            tuple(values),
        )
        return cursor.fetchone()
