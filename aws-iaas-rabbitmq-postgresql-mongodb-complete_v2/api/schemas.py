from datetime import datetime    # Para campos de fecha y hora en los modelos
from typing import Any           # Para campos con tipo genérico (JSON libre)
from uuid import UUID            # Para el tipo UUID del task_id

from pydantic import BaseModel, ConfigDict, Field  # Framework de validación de datos


class OrderCreate(BaseModel):
    """
    Esquema de entrada para POST /orders.
    Valida el cuerpo JSON que envía el cliente al crear una orden.
    Si faltan campos obligatorios o no cumplen las restricciones, Pydantic devuelve 422.
    """
    description: str = Field(..., min_length=1)         # Obligatorio, al menos 1 carácter
    status: str = Field(default="created", min_length=1, max_length=50)  # Opcional, default "created"
    metadata: dict[str, Any] = Field(default_factory=dict)  # JSON libre, default {}


class OrderUpdate(BaseModel):
    """
    Esquema de entrada para PUT /orders/{order_id}.
    Todos los campos son opcionales — el cliente sólo envía lo que quiere cambiar.
    extra='forbid' rechaza cualquier campo extra que no esté definido aquí.
    """
    description: str | None = None      # Opcional: nueva descripción
    status: str | None = None           # Opcional: nuevo estado
    metadata: dict[str, Any] | None = None  # Opcional: nuevos metadatos

    model_config = ConfigDict(extra="forbid")  # Rechaza campos desconocidos en el JSON de entrada


class OrderResponse(BaseModel):
    """
    Esquema de salida para GET /orders y GET /orders/{order_id}.
    Define exactamente qué campos devuelve la API al cliente — mapea la fila de BD.
    """
    order_id: int                    # ID autoincremental de la orden
    description: str                 # Texto descriptivo de la orden
    status: str                      # Estado: created | deleted
    metadata: dict[str, Any]         # Datos JSON adicionales
    created_at: datetime             # Timestamp de creación
    updated_at: datetime             # Timestamp de última actualización
    deleted_at: datetime | None = None  # None si está activa, fecha si fue eliminada (soft-delete)

    model_config = ConfigDict(from_attributes=True)  # Permite crear el modelo desde un objeto/dict de BD


class AcceptedTaskResponse(BaseModel):
    """
    Esquema de salida para POST /orders y DELETE /orders/{id}.
    Respuesta 202 Accepted: confirma que la operación fue encolada en RabbitMQ.
    El cliente usa el task_id para consultar el progreso via GET /tasks/{task_id}.
    """
    task_id: UUID   # Identificador único de la tarea asincrónica generado con uuid4()
    status: str     # Estado inicial: siempre "pending" al devolver el 202
    done: bool      # False en el 202, True cuando el worker termina
    created_at: datetime  # Timestamp de cuando se creó la tarea

    model_config = ConfigDict(from_attributes=True)


class TaskResponse(BaseModel):
    """
    Esquema de salida para GET /tasks/{task_id}.
    Muestra el estado completo de una tarea asincrónica.
    El cliente consulta esto repetidamente hasta que done=True.
    """
    task_id: UUID                        # Identificador único de la tarea
    operation: str                       # Operación: "create_order" o "delete_order"
    target_order_id: int | None = None   # ID de la orden afectada (None mientras está pending)
    status: str                          # pending | processing | completed | failed
    done: bool                           # True cuando la tarea terminó (exitosa o fallida)
    payload: dict[str, Any]             # Datos originales del mensaje enviado a RabbitMQ
    error_message: str | None = None     # Mensaje de error si status=failed
    created_at: datetime                 # Timestamp de creación de la tarea
    updated_at: datetime                 # Timestamp de última actualización
    completed_at: datetime | None = None # Timestamp de finalización (None si aún no terminó)

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    """
    Esquema de salida para GET /health.
    Indica si la API está activa y puede conectarse a PostgreSQL.
    """
    status: str    # "healthy" si todo está bien, "unhealthy" si hay algún problema
    database: str  # "reachable" si PostgreSQL responde, "unreachable" si no
