import json
import time
from uuid import UUID

import pika

from db import get_connection
from handlers import handle_create_order, handle_delete_order, mark_task_failed, mark_task_processing
from settings import settings


def process_message(channel, method, properties, body):
    task_id = None

    try:
        message = json.loads(body.decode("utf-8"))
        task_id = UUID(message["task_id"])
        operation = message["operation"]
        payload = message.get("payload", {})

        with get_connection() as conn:
            mark_task_processing(conn, task_id)

            if operation == "create_order":
                handle_create_order(conn, task_id, payload)
            elif operation == "delete_order":
                handle_delete_order(conn, task_id, payload)
            else:
                raise ValueError(f"Unsupported operation: {operation}")

            conn.commit()
    except Exception as exc:
        print(f"Worker failed to process message: {exc}", flush=True)
        if task_id is not None:
            try:
                with get_connection() as conn:
                    mark_task_failed(conn, task_id, str(exc))
                    conn.commit()
            except Exception as update_exc:
                print(f"Worker could not persist task failure: {update_exc}", flush=True)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def start_worker():
    credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)

    while True:
        try:
            parameters = pika.ConnectionParameters(
                host=settings.rabbitmq_host,
                port=settings.rabbitmq_port,
                credentials=credentials,
            )
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=settings.rabbitmq_queue, on_message_callback=process_message)
            print("Worker started and waiting for messages.", flush=True)
            channel.start_consuming()
        except Exception as exc:
            print(f"Worker connection error: {exc}", flush=True)
            time.sleep(settings.reconnect_delay_seconds)


if __name__ == "__main__":
    start_worker()
