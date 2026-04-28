import os
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError


def _get_ssm(name: str, default: str) -> str:
    try:
        client = boto3.client("ssm", region_name="us-east-1")
        return client.get_parameter(Name=name)["Parameter"]["Value"]
    except ClientError:
        print(f"[WARN] SSM parameter '{name}' not found. Using default: '{default}'")
        return default


@dataclass(frozen=True)
class ProducerConfig:
    api_base_url: str = f"http://{_get_ssm('/message-queue/dev/api/public_ip', os.getenv('API_BASE_URL', 'localhost'))}"
    poll_interval_seconds: int = int(os.getenv("POLL_INTERVAL_SECONDS", "3"))
    cycle_interval_seconds: int = int(os.getenv("CYCLE_INTERVAL_SECONDS", "15"))
    task_poll_attempts: int = int(os.getenv("TASK_POLL_ATTEMPTS", "20"))


config = ProducerConfig()
