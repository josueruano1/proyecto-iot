from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# ── Shared test fixtures ──────────────────────────────────────────────────────

TASK_ID = uuid4()
NOW = datetime.now(timezone.utc)


def _task_row():
    """Minimal dict that satisfies AcceptedTaskResponse."""
    return {
        "task_id": TASK_ID,
        "status": "pending",
        "done": False,
        "created_at": NOW,
    }


def _order_row(order_id: int = 1):
    """Minimal dict that satisfies OrderResponse."""
    return {
        "order_id": order_id,
        "description": "test order",
        "status": "created",
        "metadata": {},
        "created_at": NOW,
        "updated_at": NOW,
        "deleted_at": None,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_health():
    """GET /health should return 200 and {"status": "healthy"}."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("main.get_connection", return_value=mock_conn):
        r = client.get("/health")

    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@patch("main.enqueue_order_creation")
def test_create_order_returns_202(mock_enqueue):
    """POST /orders should return 202 and include task_id."""
    mock_enqueue.return_value = _task_row()

    r = client.post("/orders", json={"description": "test order"})

    assert r.status_code == 202
    assert "task_id" in r.json()


@patch("main.get_orders")
def test_list_orders_returns_200(mock_get_orders):
    """GET /orders should return 200 and a list."""
    mock_get_orders.return_value = [_order_row()]

    r = client.get("/orders")

    assert r.status_code == 200
    assert isinstance(r.json(), list)


@patch("main.get_order")
def test_get_order_not_found_returns_404(mock_get_order):
    """GET /orders/{id} for a non-existent id should return 404."""
    mock_get_order.side_effect = HTTPException(status_code=404, detail="Order not found.")

    r = client.get("/orders/9999")

    assert r.status_code == 404


@patch("main.enqueue_order_deletion")
def test_delete_order_returns_202(mock_enqueue):
    """DELETE /orders/{id} should return 202 and include task_id."""
    mock_enqueue.return_value = _task_row()

    r = client.delete("/orders/1")

    assert r.status_code == 202
    assert "task_id" in r.json()
