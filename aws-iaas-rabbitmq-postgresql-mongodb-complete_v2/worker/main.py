import json      # Para deserializar el cuerpo del mensaje de RabbitMQ (string JSON → dict Python)
import time      # Para esperar entre reintentos de conexión a RabbitMQ
from uuid import UUID  # Para convertir el task_id string a tipo UUID en los handlers

import pika     # Biblioteca cliente AMQP para consumir mensajes de RabbitMQ

from db import get_connection   # Función para abrir conexión a PostgreSQL
from handlers import handle_create_order, handle_delete_order, mark_task_failed, mark_task_processing  # Lógica de operaciones
from settings import settings   # Configuración centralizada (host, cola, delay)


def process_message(channel, method, properties, body):
    """
    Callback que RabbitMQ llama automáticamente por cada mensaje en la cola.
    Este es el corazón del worker — ejecuta la operación real (crear o eliminar una orden).

    Parámetros que RabbitMQ inyecta automáticamente:
        channel:    El canal AMQP (usado al final para hacer basic_ack)
        method:     Metadatos del mensaje (incluye delivery_tag para el ack)
        properties: Propiedades del mensaje (content_type, etc.)
        body:       El cuerpo del mensaje en bytes

    Flujo de procesamiento:
        1. Decodifica el JSON del mensaje
        2. Marca la tarea como 'processing' en la BD
        3. Ejecuta el handler correspondiente (create_order o delete_order)
        4. Hace commit para confirmar todos los cambios en PostgreSQL
        5. Hace basic_ack para confirmar a RabbitMQ que el mensaje fue procesado
        Si algo falla, marca la tarea como 'failed' y aun así hace basic_ack
        (para no bloquear la cola con mensajes que no se pueden procesar)
    """
    task_id = None  # Se declara aquí para que sea accesible en el bloque except

    try:
        # PASO 1: Decodifica el cuerpo del mensaje de bytes a dict Python
        # body llega como b'{"task_id": "uuid", "operation": "...", "payload": {...}}'
        message = json.loads(body.decode("utf-8"))
        task_id = UUID(message["task_id"])  # Convierte el string a UUID para pasar a handlers
        operation = message["operation"]    # "create_order" o "delete_order"
        payload = message.get("payload", {})  # Datos de la operación (descripción, order_id, etc.)

        with get_connection() as conn:  # Abre conexión a PostgreSQL (se cierra al salir)
            # PASO 2: Actualiza la tarea a status='processing' antes de ejecutar
            # Esto hace visible en GET /tasks que el worker ya tomó el mensaje
            mark_task_processing(conn, task_id)

            # PASO 3: Despacha al handler correcto según la operación
            if operation == "create_order":
                handle_create_order(conn, task_id, payload)  # INSERT INTO orders
            elif operation == "delete_order":
                handle_delete_order(conn, task_id, payload)  # UPDATE orders SET deleted_at
            else:
                # Operación desconocida — no debería ocurrir en operación normal
                raise ValueError(f"Unsupported operation: {operation}")

            # PASO 4: Confirma todos los cambios en la BD (mark_task_processing + handle_*)
            # Si conn.commit() falla, se va al except y la tarea queda como 'processing'
            conn.commit()
    except Exception as exc:
        # Si cualquier paso falla, registra el error y trata de marcar la tarea como failed
        print(f"Worker failed to process message: {exc}", flush=True)
        if task_id is not None:  # Solo si pudimos parsear el task_id del mensaje
            try:
                with get_connection() as conn:
                    mark_task_failed(conn, task_id, str(exc))  # Actualiza status a 'failed'
                    conn.commit()  # Confirma el UPDATE
            except Exception as update_exc:
                # Si tampoco podemos actualizar la BD, solo loggea — el mensaje igual se ackea
                print(f"Worker could not persist task failure: {update_exc}", flush=True)
    finally:
        # PASO 5: Siempre hace basic_ack, incluso si el procesamiento falló
        # Esto remueve el mensaje de la cola para no procesarlo infinitamente
        # method.delivery_tag identifica de forma única este mensaje en el canal
        channel.basic_ack(delivery_tag=method.delivery_tag)


def start_worker():
    """
    Loop infinito que mantiene el worker escuchando mensajes de RabbitMQ.
    Si la conexión se cae (RabbitMQ reinició, error de red, etc.),
    espera 'reconnect_delay_seconds' segundos y reintenta automáticamente.
    Esto garantiza que el worker sea resiliente a reinicios del broker.
    """
    # Crea las credenciales una sola vez — se reusan en cada reconexión
    credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)

    while True:  # Loop infinito — el worker corre hasta que el proceso sea matado
        try:
            # Configura los parámetros de conexión al broker RabbitMQ
            parameters = pika.ConnectionParameters(
                host=settings.rabbitmq_host,   # IP de la EC2 RabbitMQ
                port=settings.rabbitmq_port,   # Puerto AMQP: 5672
                credentials=credentials,        # Usuario y contraseña
            )
            # Abre una conexión TCP bloqueante con RabbitMQ
            connection = pika.BlockingConnection(parameters)
            # Crea un canal sobre la conexión (los mensajes se consumen por canales)
            channel = connection.channel()
            # Declara la cola como durable — si RabbitMQ reinicia, la cola y sus mensajes persisten
            # Si la cola ya existe, esta línea no hace nada
            channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)
            # prefetch_count=1: el worker solo recibe UN mensaje a la vez
            # Garantiza que si hay 2 workers, cada uno procesa mensajes distintos
            channel.basic_qos(prefetch_count=1)
            # Registra process_message como callback para cada mensaje que llegue a la cola
            channel.basic_consume(queue=settings.rabbitmq_queue, on_message_callback=process_message)
            print("Worker started and waiting for messages.", flush=True)  # flush=True para logs en Docker
            # Entra en el loop de eventos de pika — bloquea aquí hasta que la conexión falle
            channel.start_consuming()
        except Exception as exc:
            # La conexión se cayó — registra el error y reintenta después del delay
            print(f"Worker connection error: {exc}", flush=True)
            time.sleep(settings.reconnect_delay_seconds)  # Espera antes de reconectar


if __name__ == "__main__":
    # Punto de entrada cuando se ejecuta: python main.py
    # Docker corre este archivo directamente vía CMD en el Dockerfile
    start_worker()
