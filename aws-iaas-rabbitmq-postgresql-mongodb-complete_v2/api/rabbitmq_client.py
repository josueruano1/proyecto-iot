import json          # Para serializar el diccionario del mensaje a una cadena JSON

import pika          # Biblioteca cliente de RabbitMQ para Python (protocolo AMQP)

from settings import settings  # Configuración centralizada (host, puerto, usuario, pass)


def publish_task_message(message: dict, queue: str):
    """
    Publica un mensaje en una cola específica de RabbitMQ.

    Parámetros:
        message (dict): Datos del mensaje a publicar. Ejemplo:
                        {"task_id": "uuid", "operation": "create_order", "payload": {...}}
        queue (str): Nombre de la cola destino. Ejemplo: "orders_create" o "orders_delete"

    Funcionamiento:
        1. Crea las credenciales de autenticación (usuario/contraseña)
        2. Configura los parámetros de conexión al broker RabbitMQ
        3. Abre una conexión bloqueante (sincrónica)
        4. Declara la cola como durable (sobrevive al reinicio del broker)
        5. Publica el mensaje en la cola con persistencia (delivery_mode=2)
        6. Cierra la conexión siempre, incluso si hubo un error
    """
    # Crea el objeto de credenciales con usuario y contraseña de RabbitMQ
    credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)

    # Configura los parámetros de conexión al servidor RabbitMQ
    parameters = pika.ConnectionParameters(
        host=settings.rabbitmq_host,                              # IP privada de la EC2 RabbitMQ
        port=settings.rabbitmq_port,                              # Puerto AMQP: 5672
        credentials=credentials,                                  # Credenciales de autenticación
        blocked_connection_timeout=settings.rabbitmq_timeout_seconds,  # Timeout si la conexión está bloqueada
        socket_timeout=settings.rabbitmq_timeout_seconds,         # Timeout de socket de red (5 segundos)
    )

    # Abre una conexión TCP bloqueante con el broker (espera confirmación)
    connection = pika.BlockingConnection(parameters)
    try:
        # Crea un canal (channel) sobre la conexión — los mensajes se publican por canales
        channel = connection.channel()

        # Declara la cola como durable=True: si RabbitMQ se reinicia, la cola sobrevive
        # Si la cola ya existe, esta línea no hace nada
        channel.queue_declare(queue=queue, durable=True)

        # Publica el mensaje en la cola
        channel.basic_publish(
            exchange="",         # Exchange vacío = direct exchange (entrega directo a la cola por nombre)
            routing_key=queue,   # Nombre de la cola destino (routing key = nombre de cola en direct exchange)
            body=json.dumps(message),  # Serializa el dict Python a string JSON para enviarlo como bytes
            properties=pika.BasicProperties(
                delivery_mode=2,              # 2 = persistente: el mensaje sobrevive al reinicio del broker
                content_type="application/json",  # Indica que el cuerpo es JSON
            ),
        )
    finally:
        # Cierra la conexión TCP siempre, incluso si hubo una excepción durante la publicación
        connection.close()
