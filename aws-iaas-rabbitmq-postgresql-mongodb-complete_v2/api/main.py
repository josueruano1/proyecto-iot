from fastapi import FastAPI, status                     # FastAPI: framework web; status: constantes HTTP
from fastapi.middleware.cors import CORSMiddleware       # Middleware para habilitar CORS (peticiones cross-origin)
from fastapi.responses import JSONResponse               # Para devolver respuestas JSON personalizadas (ej: 503)

from db import get_connection                            # Función para crear conexión a PostgreSQL
from schemas import AcceptedTaskResponse, HealthResponse, OrderCreate, OrderResponse, OrderUpdate, TaskResponse  # Modelos Pydantic
from service import enqueue_order_creation, enqueue_order_deletion, get_order, get_orders, get_task, update_existing_order  # Lógica de negocio
from settings import settings                            # Configuración centralizada (APP_NAME, etc.)


# Instancia principal de la aplicación FastAPI
# El title aparece en la documentación automática de Swagger UI en /docs
app = FastAPI(title=settings.app_name)

# Habilita CORS (Cross-Origin Resource Sharing) para permitir peticiones desde:
# - El frontend en el navegador (diferente dominio/puerto)
# - Swagger UI en otro servidor
# - Herramientas externas
# allow_origins=["*"] permite cualquier origen (apropiado para entorno de lab/desarrollo)
# En producción se debería restringir a dominios específicos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Permite peticiones desde cualquier dominio
    allow_methods=["*"],   # Permite todos los métodos HTTP: GET, POST, PUT, DELETE, OPTIONS
    allow_headers=["*"],   # Permite todas las cabeceras HTTP
)


@app.get("/")
def read_root():
    """
    Endpoint raíz — solo para verificar que la API está corriendo.
    No requiere autenticación ni parámetros.
    Devuelve el nombre del servicio y los recursos disponibles.
    """
    return {
        "service": settings.app_name,  # Nombre de la app (orders-tasks-api)
        "status": "ok",
        "resources": ["orders", "tasks"],  # Rutas principales disponibles
    }


@app.get("/health", response_model=HealthResponse)
def health_check():
    """
    Endpoint de salud — verifica que la API puede conectarse a PostgreSQL.
    HAProxy usa este endpoint (o similar) para verificar que los servidores están vivos.
    Devuelve 200 si todo está bien, 503 si no puede conectarse a la BD.
    """
    try:
        with get_connection() as conn:       # Intenta abrir conexión a PostgreSQL
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")   # Query mínimo que confirma que la BD responde
                cursor.fetchone()            # Consume el resultado (necesario antes de cerrar)
        return {"status": "healthy", "database": "reachable"}  # 200 OK
    except Exception as exc:
        # Si la conexión falla (BD caída, red cortada), devuelve 503
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "unreachable", "error": str(exc)},
        )


@app.get("/orders", response_model=list[OrderResponse])
def list_orders():
    """
    GET /orders — Devuelve todas las órdenes activas (no eliminadas).
    Internamente filtra WHERE deleted_at IS NULL (soft-delete).
    Response: lista de OrderResponse (puede ser lista vacía []).
    """
    return get_orders()  # Delega a service.py que delega a repository.py


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order_by_id(order_id: int):
    """
    GET /orders/{order_id} — Devuelve una orden específica por su ID.
    - 200 si existe y no está eliminada
    - 404 si no existe o fue eliminada (soft-delete la hace invisible)
    """
    return get_order(order_id)  # service.py maneja el 404 si no se encuentra


@app.put("/orders/{order_id}", response_model=OrderResponse)
def update_order_by_id(order_id: int, order_update: OrderUpdate):
    """
    PUT /orders/{order_id} — Actualiza campos de una orden existente.
    - Solo actualiza los campos enviados en el body (los otros quedan igual)
    - 400 si el body viene completamente vacío (ningún campo para actualizar)
    - 404 si la orden no existe o está eliminada
    - 422 si el body tiene campos no permitidos (OrderUpdate tiene extra='forbid')
    """
    return update_existing_order(order_id, order_update)


@app.post("/orders", response_model=AcceptedTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def create_order(order_create: OrderCreate):
    """
    POST /orders — Encola la creación de una orden de forma asíncrona.
    La API NO inserta la orden directamente — en su lugar:
    1. Crea una tarea (task) en BD con status='pending'
    2. Publica un mensaje en RabbitMQ cola 'orders_create'
    3. Devuelve 202 Accepted con el task_id para que el cliente pueda rastrear el progreso

    El worker_post consume el mensaje y hace el INSERT real en la tabla orders.
    - 202 si el mensaje se encoló correctamente
    - 503 si RabbitMQ no está disponible
    - 422 si el body de la request no es válido (Pydantic validation)
    """
    return enqueue_order_creation(order_create)


@app.delete("/orders/{order_id}", response_model=AcceptedTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def delete_order(order_id: int):
    """
    DELETE /orders/{order_id} — Encola la eliminación de una orden (soft-delete asíncrono).
    La API NO elimina la orden directamente — en su lugar:
    1. Verifica que la orden existe y no está ya eliminada → 404 si no
    2. Crea una tarea con status='pending'
    3. Publica en RabbitMQ cola 'orders_delete'
    4. Devuelve 202 Accepted con el task_id

    El worker_delete consume el mensaje y hace el UPDATE real (deleted_at = NOW()).
    - 202 si el mensaje se encoló correctamente
    - 404 si la orden no existe o ya fue eliminada
    - 503 si RabbitMQ no está disponible
    """
    return enqueue_order_deletion(order_id)


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task_by_id(task_id: str):
    """
    GET /tasks/{task_id} — Consulta el estado de una tarea asíncrona por su UUID.
    El cliente usa este endpoint para saber si su POST o DELETE terminó:
    - status='pending'    → el worker aún no procesó el mensaje
    - status='processing' → el worker está ejecutando la operación
    - status='completed'  → la operación terminó exitosamente (done=True)
    - status='failed'     → la operación falló (done=True, error_message con el detalle)

    - 200 con el TaskResponse si el task_id existe
    - 404 si el task_id no existe (UUID incorrecto o no generado por esta API)
    """
    return get_task(task_id)
