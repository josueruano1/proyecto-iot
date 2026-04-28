import os
from dataclasses import dataclass

import boto3


def _get_ssm(name: str, default: str) -> str:
    if default != "localhost":
        return default
    try:
        client = boto3.client("ssm", region_name="us-east-1")
        return client.get_parameter(Name=name)["Parameter"]["Value"]
    except Exception:
        print(f"[WARN] SSM parameter '{name}' not found. Using default: '{default}'")
        return default


@dataclass(frozen=True)
class Settings:
    db_host: str = _get_ssm("/message-queue/dev/postgres/public_ip", os.getenv("DB_HOST", "localhost"))
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "mydb")
    db_user: str = os.getenv("DB_USER", "admin")
    db_password: str = os.getenv("DB_PASSWORD", "password123")
    rabbitmq_host: str = _get_ssm("/message-queue/dev/rabbitmq/public_ip", os.getenv("RABBITMQ_HOST", "localhost"))
    rabbitmq_port: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    rabbitmq_user: str = os.getenv("RABBITMQ_USER", "admin")
    rabbitmq_password: str = os.getenv("RABBITMQ_PASSWORD", "password123")
    rabbitmq_queue: str = os.getenv("RABBITMQ_QUEUE", "orders_tasks")
    reconnect_delay_seconds: int = int(os.getenv("RECONNECT_DELAY_SECONDS", "5"))


settings = Settings()
