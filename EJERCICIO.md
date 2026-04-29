# Ejercicio Práctico — Arquitectura IaaS con RabbitMQ y PostgreSQL

## Índice
1. [Arquitectura del sistema](#arquitectura-del-sistema)
2. [Infraestructura desplegada](#infraestructura-desplegada)
3. [Paso a paso del ejercicio](#paso-a-paso-del-ejercicio)
4. [Qué pasa internamente en cada acción](#qué-pasa-internamente-en-cada-acción)
5. [Cómo se conecta con la base de datos](#cómo-se-conecta-con-la-base-de-datos)
6. [Archivos involucrados por acción](#archivos-involucrados-por-acción)

---

## Arquitectura del sistema

```
Internet / Swagger UI
        │
        ▼
  HAProxy (EC2)          ← Balanceador de carga — reparte entre las 2 APIs
  52.91.13.99:80
        │
   ┌────┴────┐
   ▼         ▼
API Server 1  API Server 2    ← FastAPI en Docker (puerto 80→8000)
3.85.239.123  54.86.74.216
   │
   ├─── PostgreSQL (EC2) ─────────────── Lee/escribe órdenes y tasks
   │    3.95.213.11:5432
   │
   └─── RabbitMQ (EC2) ──────────────── Publica mensajes en 2 colas
        3.84.52.2:5672
              │
         ┌────┴────┐
         ▼         ▼
   worker_post   worker_delete   ← Consumers: leen la cola y ejecutan en BD
   54.174.154.174  54.88.94.58
         │         │
         └────┬────┘
              ▼
         PostgreSQL
         3.95.213.11:5432
```

El patrón usado es **procesamiento asíncrono con colas de mensajes**:
- La API **no hace la operación directamente** — la encola en RabbitMQ y devuelve `202 Accepted` inmediatamente.
- Un worker independiente consume el mensaje y hace el trabajo real en la base de datos.
- El cliente puede consultar el estado del trabajo via `GET /tasks/{task_id}`.

---

## Infraestructura desplegada

| Servidor | IP Pública | Rol | Script de instalación |
|---|---|---|---|
| HAProxy | `52.91.13.99` | Load Balancer | `install_haproxy.sh` |
| API Server 1 | `3.85.239.123` | FastAPI en Docker | `install_api.sh` |
| API Server 2 | `54.86.74.216` | FastAPI en Docker | `install_api.sh` |
| RabbitMQ | `3.84.52.2` | Message Broker | `install_rabbitmq.sh` |
| Worker Post | `54.174.154.174` | Consumer `orders_create` | `install_worker.sh` |
| Worker Delete | `54.88.94.58` | Consumer `orders_delete` | `install_worker.sh` |
| PostgreSQL | `3.95.213.11` | Base de datos | `install_postgres.sh` |

Toda la infraestructura se define como código en `main.tf` y `security_groups.tf`.

---

## Paso a paso del ejercicio

> Acceder a `http://52.91.13.99/docs` desde hotspot móvil (FortiGate bloquea IPs sin categoría desde red universitaria).

### PASO 1 — GET /health
Verificar que la API está viva y conectada a PostgreSQL.

**Resultado esperado:**
```json
{"status": "healthy", "database": "reachable"}
```

---

### PASO 2 — POST /orders
Crear una nueva orden. Esto dispara todo el flujo asíncrono.

**Body:**
```json
{"description": "prueba defensa"}
```

**Resultado esperado `202`:**
```json
{
  "task_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "status": "pending",
  "done": false,
  "created_at": "2026-04-29T20:40:29Z"
}
```

> Guardar el `task_id` para el siguiente paso.

---

### PASO 3 — GET /tasks/{task_id}
Consultar si el worker ya procesó la creación (esperar ~5 segundos).

**Resultado esperado:**
```json
{
  "task_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "status": "completed",
  "done": true,
  "completed_at": "2026-04-29T20:40:31Z"
}
```

---

### PASO 4 — GET /orders
Listar todas las órdenes activas. La orden recién creada aparece con `status: created`.

**Resultado esperado:**
```json
[
  {
    "order_id": 9,
    "description": "prueba defensa",
    "status": "created",
    "metadata": {},
    "created_at": "2026-04-29T20:40:29Z",
    "deleted_at": null
  }
]
```

> Guardar el `order_id` para el paso 6.

---

### PASO 5 — GET /orders/{order_id}
Ver los detalles de una orden específica.

---

### PASO 6 — DELETE /orders/{order_id}
Eliminar la orden. Dispara el segundo flujo asíncrono (cola `orders_delete`).

**Resultado esperado `202`:**
```json
{
  "task_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
  "status": "pending",
  "done": false
}
```

> Guardar el nuevo `task_id`.

---

### PASO 7 — GET /tasks/{task_id}
Consultar si el worker_delete procesó la eliminación (esperar ~5 segundos).

**Resultado esperado:**
```json
{"status": "completed", "done": true}
```

---

### PASO 8 — Verificar en PostgreSQL (evidencia directa en BD)
La orden ya no aparece en `GET /orders` (filtro `deleted_at IS NULL`), pero sigue en la BD marcada como eliminada:

```sql
SELECT order_id, description, status, deleted_at
FROM orders
ORDER BY order_id;
```

Resultado real:
```
 order_id |   description   | status  |          deleted_at
----------+-----------------+---------+-------------------------------
        1 | Test order      | deleted | 2026-04-29 20:54:25+00
        9 | prueba defensa  | created |
```

---

## Qué pasa internamente en cada acción

### POST /orders — Flujo completo

```
Cliente
  │
  │  POST /orders {"description": "prueba"}
  ▼
api/main.py → create_order()
  │
  │  1. Llama a service.enqueue_order_creation()
  ▼
api/service.py → enqueue_order_creation()
  │
  │  2. Genera un UUID para el task_id
  │  3. Llama a repository.create_task() → INSERT en tabla tasks (status: pending)
  │  4. Llama a rabbitmq_client.publish_task_message() → publica en cola "orders_create"
  │  5. Devuelve el task row al cliente → 202 Accepted
  ▼
RabbitMQ (cola: orders_create)
  │
  │  [Mensaje en cola: {task_id, operation: "create_order", payload: {description}}]
  ▼
worker/main.py → process_message()   ← El worker_post está escuchando permanentemente
  │
  │  6. Llama a handlers.mark_task_processing() → UPDATE tasks SET status='processing'
  │  7. Llama a handlers.handle_create_order()
  ▼
worker/handlers.py → handle_create_order()
  │
  │  8. INSERT INTO orders (description, status, metadata) → obtiene order_id
  │  9. Llama a handlers.complete_task() → UPDATE tasks SET status='completed', done=TRUE
  │
  └── conn.commit() → todo persiste en PostgreSQL
```

---

### DELETE /orders/{order_id} — Flujo completo

```
Cliente
  │
  │  DELETE /orders/9
  ▼
api/main.py → delete_order()
  │
  ▼
api/service.py → enqueue_order_deletion()
  │
  │  1. Genera nuevo task_id
  │  2. repository.create_task() → INSERT en tasks (operation: "delete_order")
  │  3. rabbitmq_client.publish_task_message() → publica en cola "orders_delete"
  │  4. Devuelve 202 Accepted
  ▼
RabbitMQ (cola: orders_delete)
  │
  ▼
worker/main.py → process_message()   ← El worker_delete está escuchando
  │
  ▼
worker/handlers.py → handle_delete_order()
  │
  │  5. UPDATE orders SET status='deleted', deleted_at=NOW()
  │     WHERE order_id = ? AND deleted_at IS NULL
  │  6. complete_task() → UPDATE tasks SET status='completed', done=TRUE
  │
  └── conn.commit()
```

---

### GET /tasks/{task_id} — Consulta de estado

```
Cliente → api/main.py → get_task_by_id()
              │
              ▼
          api/service.py → get_task()
              │
              ▼
          api/repository.py → get_task_by_id()
              │
              │  SELECT task_id, status, done, ... FROM tasks WHERE task_id = ?
              ▼
          PostgreSQL → devuelve fila → API → Cliente
```

---

### GET /health — Health check

```
api/main.py → health_check()
    │
    │  1. Abre conexión a PostgreSQL via api/db.py → get_connection()
    │  2. Ejecuta SELECT 1
    │  3. Si responde → {"status": "healthy", "database": "reachable"}
    │  4. Si falla → 503 {"status": "unhealthy"}
```

---

## Cómo se conecta con la base de datos

### Esquema de tablas (`sql/schema.sql`)

**Tabla `orders`** — almacena las órdenes:
```sql
CREATE TABLE orders (
    order_id   BIGSERIAL PRIMARY KEY,       -- ID autoincremental
    description TEXT NOT NULL,              -- texto de la orden
    status     VARCHAR(50) DEFAULT 'created', -- created | deleted
    metadata   JSONB DEFAULT '{}',          -- datos extra en JSON
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL             -- NULL = activa, fecha = eliminada (soft-delete)
);
```

**Tabla `tasks`** — rastrea el estado de cada operación asíncrona:
```sql
CREATE TABLE tasks (
    task_id        UUID PRIMARY KEY,         -- identificador único de la tarea
    operation      VARCHAR(50),              -- "create_order" | "delete_order"
    target_order_id BIGINT,                  -- orden afectada
    status         VARCHAR(50),              -- pending | processing | completed | failed
    done           BOOLEAN DEFAULT FALSE,
    payload        JSONB,                    -- datos del mensaje original
    error_message  TEXT,                     -- si falló, aquí está el error
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    completed_at   TIMESTAMPTZ              -- cuándo terminó
);
```

### Ciclo de vida de una tarea

```
pending      → la API creó la tarea, aún no la tomó el worker
processing   → el worker está ejecutando la operación
completed    → operación exitosa en BD
failed       → error durante la ejecución (ver error_message)
```

### Conexión a PostgreSQL (`api/db.py` y `worker/db.py`)

Ambas capas (API y workers) se conectan a PostgreSQL con `psycopg2`. La configuración viene de variables de entorno inyectadas al desplegar por Terraform via `install_api.sh` e `install_worker.sh`:

```
DB_HOST     = IP privada de la EC2 PostgreSQL
DB_PORT     = 5432
DB_NAME     = mydb
DB_USER     = admin
DB_PASSWORD = password123
```

---

## Archivos involucrados por acción

| Acción | Archivos ejecutados (en orden) |
|---|---|
| `POST /orders` | `api/main.py` → `api/service.py` → `api/repository.py` → `api/rabbitmq_client.py` |
| Worker crea orden | `worker/main.py` → `worker/handlers.py` → `worker/db.py` |
| `DELETE /orders/{id}` | `api/main.py` → `api/service.py` → `api/repository.py` → `api/rabbitmq_client.py` |
| Worker borra orden | `worker/main.py` → `worker/handlers.py` → `worker/db.py` |
| `GET /orders` | `api/main.py` → `api/service.py` → `api/repository.py` |
| `GET /tasks/{id}` | `api/main.py` → `api/service.py` → `api/repository.py` |
| `GET /health` | `api/main.py` → `api/db.py` |
| Esquema BD | `sql/schema.sql` (ejecutado al provisionar PostgreSQL) |
| Config API | `api/settings.py` (lee variables de entorno) |
| Config Worker | `worker/settings.py` (lee variables de entorno) |
| IaC | `main.tf`, `security_groups.tf`, `variables.tf`, `outputs.tf` |

---

## Soft-delete vs Hard-delete

El sistema usa **soft-delete**: las órdenes eliminadas **no se borran físicamente** de la base de datos. En su lugar se marca `deleted_at = NOW()` y `status = 'deleted'`.

Por eso:
- `GET /orders` → solo muestra órdenes con `deleted_at IS NULL` (activas)
- `GET /orders/{id}` → también filtra por `deleted_at IS NULL`, devuelve 404 si está eliminada
- La fila sigue en la BD para auditoría

Para ver todas incluyendo eliminadas, consultar directamente en PostgreSQL:
```sql
SELECT order_id, description, status, deleted_at FROM orders ORDER BY order_id;
```
