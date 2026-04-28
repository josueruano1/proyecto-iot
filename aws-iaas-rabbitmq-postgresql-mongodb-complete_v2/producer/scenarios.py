import time
from datetime import datetime, timezone

import requests

from config import config


def _url(path: str) -> str:
    return f"{config.api_base_url.rstrip('/')}{path}"


def wait_for_task(task_id: str):
    last_response = None
    for _ in range(config.task_poll_attempts):
        response = requests.get(_url(f"/tasks/{task_id}"), timeout=10)
        response.raise_for_status()
        last_response = response.json()
        if last_response["done"]:
            return last_response
        time.sleep(config.poll_interval_seconds)
    return last_response


def run_order_lifecycle():
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    create_payload = {
        "description": f"synthetic-order-{suffix}",
        "status": "created",
        "metadata": {"source": "synthetic-producer", "timestamp": suffix},
    }

    create_response = requests.post(_url("/orders"), json=create_payload, timeout=10)
    create_response.raise_for_status()
    create_task = create_response.json()
    print(f"POST /orders -> task {create_task['task_id']}", flush=True)

    create_result = wait_for_task(create_task["task_id"])
    print(f"GET /tasks/{create_task['task_id']} -> {create_result}", flush=True)
    if not create_result or create_result["status"] != "completed":
        return

    order_id = create_result["target_order_id"]
    order_response = requests.get(_url(f"/orders/{order_id}"), timeout=10)
    order_response.raise_for_status()
    print(f"GET /orders/{order_id} -> {order_response.json()}", flush=True)

    update_payload = {
        "description": f"updated-synthetic-order-{suffix}",
        "status": "updated",
        "metadata": {"source": "synthetic-producer", "updated": True},
    }
    update_response = requests.put(_url(f"/orders/{order_id}"), json=update_payload, timeout=10)
    update_response.raise_for_status()
    print(f"PUT /orders/{order_id} -> {update_response.json()}", flush=True)

    list_response = requests.get(_url("/orders"), timeout=10)
    list_response.raise_for_status()
    print(f"GET /orders -> {len(list_response.json())} orders", flush=True)

    delete_response = requests.delete(_url(f"/orders/{order_id}"), timeout=10)
    delete_response.raise_for_status()
    delete_task = delete_response.json()
    print(f"DELETE /orders/{order_id} -> task {delete_task['task_id']}", flush=True)

    delete_result = wait_for_task(delete_task["task_id"])
    print(f"GET /tasks/{delete_task['task_id']} -> {delete_result}", flush=True)
