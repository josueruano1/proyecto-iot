from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import get_connection
from schemas import AcceptedTaskResponse, HealthResponse, OrderCreate, OrderResponse, OrderUpdate, TaskResponse
from service import enqueue_order_creation, enqueue_order_deletion, get_order, get_orders, get_task, update_existing_order
from settings import settings


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "service": settings.app_name,
        "status": "ok",
        "resources": ["orders", "tasks"],
    }


@app.get("/health", response_model=HealthResponse)
def health_check():
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return {"status": "healthy", "database": "reachable"}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "unreachable", "error": str(exc)},
        )


@app.get("/orders", response_model=list[OrderResponse])
def list_orders():
    return get_orders()


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order_by_id(order_id: int):
    return get_order(order_id)


@app.put("/orders/{order_id}", response_model=OrderResponse)
def update_order_by_id(order_id: int, order_update: OrderUpdate):
    return update_existing_order(order_id, order_update)


@app.post("/orders", response_model=AcceptedTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def create_order(order_create: OrderCreate):
    return enqueue_order_creation(order_create)


@app.delete("/orders/{order_id}", response_model=AcceptedTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def delete_order(order_id: int):
    return enqueue_order_deletion(order_id)


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task_by_id(task_id: str):
    return get_task(task_id)
