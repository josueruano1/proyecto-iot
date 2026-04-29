import os                      # Para leer variables de entorno del sistema operativo
from dataclasses import dataclass  # Para crear clases de configuración inmutables

import boto3                   # SDK de AWS — usado para leer parámetros de SSM Parameter Store
from botocore.exceptions import ClientError  # Excepción de AWS cuando falla una llamada a la API


def _get_ssm(name: str, default: str) -> str:
    """
    Intenta obtener un parámetro de AWS SSM Parameter Store.
    Si el default NO es 'localhost', significa que ya viene inyectado como variable
    de entorno desde Terraform (install_api.sh), y se usa directamente sin llamar a AWS.
    Si el default SÍ es 'localhost' (entorno local), intenta recuperarlo de SSM.
    Si SSM falla, usa el default como fallback.
    """
    if default != "localhost":  # La variable de entorno ya tiene el valor real → úsala directo
        return default
    try:
        # Crea un cliente de AWS SSM en la región us-east-1 (región del Learner Lab)
        client = boto3.client("ssm", region_name="us-east-1")
        # Obtiene el parámetro por nombre y extrae su valor del JSON de respuesta
        return client.get_parameter(Name=name)["Parameter"]["Value"]
    except ClientError:
        # Si el parámetro no existe o no hay permisos, avisa y usa el default
        print(f"[WARN] SSM parameter '{name}' not found. Using default: '{default}'")
        return default


@dataclass(frozen=True)  # frozen=True hace la instancia inmutable (no se puede modificar después de crear)
class Settings:
    """
    Centraliza toda la configuración de la API.
    Los valores se leen de variables de entorno inyectadas por Terraform en install_api.sh.
    Si no existen (entorno local), se usan defaults o se consulta AWS SSM.
    """
    # Nombre visible de la aplicación en Swagger UI
    app_name: str = os.getenv("APP_NAME", "orders-tasks-api")

    # Host de PostgreSQL: primero intenta la variable de entorno DB_HOST,
    # si no existe intenta obtenerlo de SSM Parameter Store
    db_host: str = _get_ssm("/message-queue/dev/postgres/public_ip", os.getenv("DB_HOST", "localhost"))
    db_port: int = int(os.getenv("DB_PORT", "5432"))       # Puerto de PostgreSQL (default 5432)
    db_name: str = os.getenv("DB_NAME", "mydb")            # Nombre de la base de datos
    db_user: str = os.getenv("DB_USER", "admin")           # Usuario de PostgreSQL
    db_password: str = os.getenv("DB_PASSWORD", "password123")  # Contraseña de PostgreSQL

    # Host de RabbitMQ: misma lógica que db_host (variable de entorno o SSM)
    rabbitmq_host: str = _get_ssm("/message-queue/dev/rabbitmq/public_ip", os.getenv("RABBITMQ_HOST", "localhost"))
    rabbitmq_port: int = int(os.getenv("RABBITMQ_PORT", "5672"))          # Puerto AMQP de RabbitMQ
    rabbitmq_user: str = os.getenv("RABBITMQ_USER", "admin")               # Usuario de RabbitMQ
    rabbitmq_password: str = os.getenv("RABBITMQ_PASSWORD", "password123") # Contraseña de RabbitMQ
    rabbitmq_queue_create: str = os.getenv("RABBITMQ_QUEUE_CREATE", "orders_create")  # Cola para crear órdenes
    rabbitmq_queue_delete: str = os.getenv("RABBITMQ_QUEUE_DELETE", "orders_delete")  # Cola para eliminar órdenes
    rabbitmq_timeout_seconds: int = int(os.getenv("RABBITMQ_TIMEOUT_SECONDS", "5"))   # Timeout de conexión a RabbitMQ


# Instancia única de Settings que se importa en todos los módulos de la API
settings = Settings()
