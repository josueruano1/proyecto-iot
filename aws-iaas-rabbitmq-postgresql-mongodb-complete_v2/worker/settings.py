import os              # Para leer variables de entorno inyectadas por Terraform (install_worker.sh)
from dataclasses import dataclass  # Para crear una clase de configuración inmutable

import boto3           # SDK de AWS — usado para leer parámetros de SSM Parameter Store


def _get_ssm(name: str, default: str) -> str:
    """
    Mismo patrón que en api/settings.py:
    - Si el 'default' NO es 'localhost', la variable de entorno ya tiene el valor real
      (inyectado por Terraform) → úsalo directamente sin llamar a AWS.
    - Si el 'default' SÍ es 'localhost' (entorno de desarrollo local),
      intenta recuperar el valor de AWS SSM Parameter Store.
    - Si SSM falla (sin permisos, sin red), usa el default como fallback.
    """
    if default != "localhost":   # Variable de entorno ya tiene el valor real
        return default
    try:
        # Crea cliente SSM en us-east-1 (región del Learner Lab de AWS)
        client = boto3.client("ssm", region_name="us-east-1")
        # Llama a la API de SSM y extrae el valor del parámetro
        return client.get_parameter(Name=name)["Parameter"]["Value"]
    except Exception:
        # Cualquier error (ClientError, de red, etc.) → avisa y usa el default
        print(f"[WARN] SSM parameter '{name}' not found. Using default: '{default}'")
        return default


@dataclass(frozen=True)  # frozen=True → la instancia es inmutable (no se puede modificar después de crear)
class Settings:
    """
    Configuración del worker. Difiere de la API en dos campos adicionales:
    - rabbitmq_queue: nombre de la cola que este worker específico consume
      (cada worker tiene su propia cola: orders_create o orders_delete)
    - reconnect_delay_seconds: cuántos segundos esperar antes de reintentar
      conectarse a RabbitMQ si la conexión se cae
    """
    # Conexión a PostgreSQL
    db_host: str = _get_ssm("/message-queue/dev/postgres/public_ip", os.getenv("DB_HOST", "localhost"))
    db_port: int = int(os.getenv("DB_PORT", "5432"))          # Puerto estándar de PostgreSQL
    db_name: str = os.getenv("DB_NAME", "mydb")               # Nombre de la base de datos
    db_user: str = os.getenv("DB_USER", "admin")              # Usuario de PostgreSQL
    db_password: str = os.getenv("DB_PASSWORD", "password123")  # Contraseña de PostgreSQL

    # Conexión a RabbitMQ
    rabbitmq_host: str = _get_ssm("/message-queue/dev/rabbitmq/public_ip", os.getenv("RABBITMQ_HOST", "localhost"))
    rabbitmq_port: int = int(os.getenv("RABBITMQ_PORT", "5672"))           # Puerto AMQP estándar
    rabbitmq_user: str = os.getenv("RABBITMQ_USER", "admin")               # Usuario de RabbitMQ
    rabbitmq_password: str = os.getenv("RABBITMQ_PASSWORD", "password123") # Contraseña de RabbitMQ
    rabbitmq_queue: str = os.getenv("RABBITMQ_QUEUE", "orders_tasks")      # Cola que este worker consume
    # Tiempo de espera entre reintentos de conexión a RabbitMQ (en segundos)
    reconnect_delay_seconds: int = int(os.getenv("RECONNECT_DELAY_SECONDS", "5"))


# Instancia única de Settings que se importa en todos los módulos del worker
settings = Settings()
