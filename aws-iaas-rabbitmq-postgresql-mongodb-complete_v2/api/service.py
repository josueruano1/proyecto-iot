from uuid import uuid4

from fastapi import HTTPException, status

from db import get_connection
from rabbitmq_client import publish_task_message
from settings import settings
from repository import (
    create_task,
    get_order_by_id,
    get_task_by_id,
    list_orders,
    update_order,
    update_task_status,
)


def get_orders():
    with get_connection() as conn:
        return list_orders(conn)


def get_order(order_id: int):
    with get_connection() as conn:
        order = get_order_by_id(conn, order_id)

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    return order


def update_existing_order(order_id: int, order_update):
    try:
        with get_connection() as conn:
            order = update_order(
                conn,
                order_id,
                description=order_update.description,
                status=order_update.status,
                metadata=order_update.metadata,
            )
            conn.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    return order


def enqueue_order_creation(order_create):
    task_id = uuid4()
    payload = {
        "description": order_create.description,
        "status": order_create.status,
        "metadata": order_create.metadata,
    }

    with get_connection() as conn:
        task = create_task(conn, task_id=task_id, operation="create_order", payload=payload)
        conn.commit()

    try:
        publish_task_message(
            {
                "task_id": str(task_id),
                "operation": "create_order",
                "payload": payload,
            },
            queue=settings.rabbitmq_queue_create,
        )
    except Exception as exc:
        with get_connection() as conn:
            task = update_task_status(conn, task_id, status="failed", done=True, error_message=str(exc))
            conn.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not publish create_order task to RabbitMQ.",
        ) from exc

    return task


def enqueue_order_deletion(order_id: int):
    with get_connection() as conn:
        order = get_order_by_id(conn, order_id)

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    task_id = uuid4()
    payload = {"order_id": order_id}

    with get_connection() as conn:
        task = create_task(
            conn,
            task_id=task_id,
            operation="delete_order",
            payload=payload,
            target_order_id=order_id,
        )
        conn.commit()

    try:
        publish_task_message(
            {
                "task_id": str(task_id),
                "operation": "delete_order",
                "payload": payload,
            },
            queue=settings.rabbitmq_queue_delete,
        )
    except Exception as exc:
        with get_connection() as conn:
            task = update_task_status(conn, task_id, status="failed", done=True, error_message=str(exc))
            conn.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not publish delete_order task to RabbitMQ.",
        ) from exc

    return task


def get_task(task_id):
    with get_connection() as conn:
        task = get_task_by_id(conn, task_id)

    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    return task
