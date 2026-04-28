# Plan Completo — Proyecto IoT con FastAPI, RabbitMQ y AWS IaC (OpenTofu)

> Guía paso a paso para construir, desplegar y sustentar el proyecto desde cero.

---

## Arquitectura Final

```
[Productor Eventos Sintéticos] ──POST(1)──→ [ALB] ──→ [EC2: api_1]
[Actor] ──GET Task/TaskId──────────────────→ [ALB] ──→ [EC2: api_2]
[Actor] ──GET Orders───────────────────────→ [ALB] ──→

         ↑ 202 TaskId

[EC2: api] ──(2)──→ [EC2: DB PostgreSQL]
[EC2: api] ──(3)──→ [EC2: RabbitMQ] ──→ [EC2: consumer_post] ──→ [EC2: DB]
                                    ──→ [EC2: worker_delete]  ──→ [EC2: DB]
```

**EC2s requeridas:** api_1, api_2, rabbitmq, consumer_post, worker_delete, database  
**ALB:** único punto de entrada público  
**Parameter Store:** guarda IPs privadas de rabbitmq y db, y el DNS del ALB

---

## FASE 0 — Entorno de Desarrollo (Día 1 — mañana)

### Paso 1: Preparar Docker del profe

```bash
# Clonar o ubicarse en la carpeta con el Dockerfile del profe
docker build -t iot_dev_environment_image .

# Levantar el container montando TU carpeta de proyecto
docker run -it --name iot_dev_environment \
  -v /ruta/a/tu/proyecto:/app \
  iot_dev_environment_image bash
```

### Paso 2: Configurar AWS CLI dentro del container

```bash
# Dentro del container:
# 1. Entrar a AWS Academy → Learner Lab → Start Lab
# 2. Click en "AWS Details" → copiar las credenciales
# 3. En el container:
aws configure
# Pegar Access Key ID, Secret Access Key, región: us-east-1

# Verificar que funciona:
aws s3 ls
aws ssm describe-parameters
```

### Paso 3: Crear estructura del proyecto

```
proyecto/
├── api/
│   ├── main.py
│   ├── routes/
│   │   ├── tasks.py
│   │   └── orders.py
│   ├── models.py
│   ├── database.py
│   └── queue.py
├── workers/
│   ├── consumer_post.py
│   └── consumer_delete.py
├── producer/
│   └── producer.py
├── tests/
│   └── test_tasks.py
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── requirements.txt
├── .ruff.toml
├── Dockerfile
└── README.md
```

---

## FASE 1 — Base de Datos (Día 1 — tarde)

### Paso 4: Crear modelos y conexión a PostgreSQL

**`api/models.py`**
```python
from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
import uuid, datetime

Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    task_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status  = Column(String, default="PENDING")
    date    = Column(DateTime, default=datetime.datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    order_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id  = Column(String)
    date     = Column(DateTime, default=datetime.datetime.utcnow)
```

**`api/database.py`**
```python
import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models import Base

def get_db_ip():
    ssm = boto3.client('ssm', region_name='us-east-1')
    return ssm.get_parameter(Name='/project/db/ip')['Parameter']['Value']

def get_engine():
    ip = get_db_ip()
    url = f"postgresql://admin:password@{ip}:5432/projectdb"
    return create_engine(url)

engine = get_engine()
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## FASE 2 — API REST con FastAPI (Día 2)

### Paso 5: Conexión a RabbitMQ

**`api/queue.py`**
```python
import boto3, pika

def get_rabbitmq_ip():
    ssm = boto3.client('ssm', region_name='us-east-1')
    return ssm.get_parameter(Name='/project/rabbitmq/ip')['Parameter']['Value']

def publish_message(queue_name: str, message: str):
    ip = get_rabbitmq_ip()
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=ip))
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)
    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=message,
        properties=pika.BasicProperties(delivery_mode=2)
    )
    connection.close()
```

### Paso 6: Endpoints de la API

**`api/routes/tasks.py`**
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import Task
from api.queue import publish_message
import json, uuid

router = APIRouter()

# GET /tasks — lista todas las tasks
@router.get("/tasks")
def get_tasks(db: Session = Depends(get_db)):
    return db.query(Task).all()

# GET /tasks/{task_id} — consulta estado de una task
@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# POST /tasks — asíncrono, retorna 202 + TaskId
@router.post("/tasks", status_code=202)
def create_task(db: Session = Depends(get_db)):
    task = Task()
    db.add(task)
    db.commit()
    publish_message("post_queue", json.dumps({"task_id": task.task_id}))
    return {"taskId": task.task_id, "status": "PENDING"}

# PUT /tasks/{task_id} — actualiza task
@router.put("/tasks/{task_id}")
def update_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    task.status = "UPDATED"
    db.commit()
    return task

# DELETE /tasks/{task_id} — asíncrono, retorna 202 + TaskId
@router.delete("/tasks/{task_id}", status_code=202)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    task.status = "DELETING"
    db.commit()
    publish_message("delete_queue", json.dumps({"task_id": task_id}))
    return {"taskId": task_id, "status": "DELETING"}
```

**`api/main.py`**
```python
from fastapi import FastAPI
from api.routes.tasks import router as tasks_router
from api.routes.orders import router as orders_router

app = FastAPI(title="IoT Tasks API", version="1.0.0")
app.include_router(tasks_router)
app.include_router(orders_router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

---

## FASE 3 — Workers / Consumers (Día 2 — tarde)

### Paso 7: Consumer POST

**`workers/consumer_post.py`**
```python
import boto3, pika, json
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from api.models import Task, Order, Base

def get_ip(param):
    ssm = boto3.client('ssm', region_name='us-east-1')
    return ssm.get_parameter(Name=param)['Parameter']['Value']

db_ip       = get_ip('/project/db/ip')
rabbitmq_ip = get_ip('/project/rabbitmq/ip')

engine = create_engine(f"postgresql://admin:password@{db_ip}:5432/projectdb")
Session = sessionmaker(bind=engine)

def callback(ch, method, properties, body):
    data    = json.loads(body)
    task_id = data["task_id"]
    db      = Session()
    task    = db.query(Task).filter(Task.task_id == task_id).first()
    if task:
        order = Order(task_id=task_id)
        db.add(order)
        task.status = "DONE"
        db.commit()
    db.close()
    ch.basic_ack(delivery_tag=method.delivery_tag)

connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_ip))
channel    = connection.channel()
channel.queue_declare(queue='post_queue', durable=True)
channel.basic_consume(queue='post_queue', on_message_callback=callback)
channel.start_consuming()
```

### Paso 8: Worker DELETE — igual que consumer_post pero:

- Consume la cola `delete_queue`
- Elimina el registro del Task en la DB
- Actualiza el TaskId como `DELETED`

---

## FASE 4 — Productor de Eventos Sintéticos (Día 3 — mañana)

### Paso 9: Productor

**`producer/producer.py`**
```python
import boto3, requests, time, random

def get_alb_dns():
    ssm = boto3.client('ssm', region_name='us-east-1')
    return ssm.get_parameter(Name='/project/alb/dns')['Parameter']['Value']

alb_dns = get_alb_dns()
BASE_URL = f"http://{alb_dns}"

while True:
    # Crear task
    r = requests.post(f"{BASE_URL}/tasks")
    print(f"Created: {r.json()}")
    time.sleep(random.uniform(1, 3))
```

---

## FASE 5 — Pruebas Unitarias y Ruff (Día 3 — tarde)

### Paso 10: Tests con pytest

**`tests/test_tasks.py`**
```python
from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200

@patch("api.routes.tasks.get_db")
@patch("api.routes.tasks.publish_message")
def test_create_task_returns_202(mock_publish, mock_db):
    r = client.post("/tasks")
    assert r.status_code == 202
    assert "taskId" in r.json()

@patch("api.routes.tasks.get_db")
def test_get_tasks(mock_db):
    r = client.get("/tasks")
    assert r.status_code == 200

@patch("api.routes.tasks.get_db")
def test_get_task_not_found(mock_db):
    r = client.get("/tasks/fake-id-123")
    assert r.status_code == 404

@patch("api.routes.tasks.get_db")
@patch("api.routes.tasks.publish_message")
def test_delete_task_returns_202(mock_publish, mock_db):
    r = client.delete("/tasks/some-task-id")
    assert r.status_code == 202
```

```bash
# Correr los tests:
pytest tests/ -v
```

### Paso 11: Análisis estático con Ruff

**`.ruff.toml`**
```toml
[tool.ruff]
line-length = 88
select = ["E", "F", "W"]
ignore = []
```

```bash
ruff check .         # ver errores
ruff check . --fix   # corregir automáticamente
```

**El código debe pasar sin errores antes de entregar.**

---

## FASE 6 — Infraestructura OpenTofu (Día 4)

### Paso 12: Instalar OpenTofu

```bash
# Dentro del container del profe:
apt-get install -y opentofu
# o
brew install opentofu  # Mac
```

### Paso 13: Estudiar las carpetas del profe

```bash
# Antes de escribir código, leer los ejemplos:
cat aws-iaas-examples/aws-iaas-ec2/main.tf
cat aws-iaas-examples/aws-iaas-alb/main.tf
cat aws-iaas-examples/aws-iaas-rabbitmq-postgresql-mongodb-students/main.tf
```

Identifica en cada uno:
- Cómo define `aws_instance`
- El `user_data` (script de instalación)
- Los Security Groups
- El `key_name` para SSH

### Paso 14: Escribir `infra/main.tf`

```hcl
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = "us-east-1"
}

# ── Variables de AMI y Key ───────────────────────────────────────────
variable "ami_id"    { default = "ami-0c02fb55956c7d316" }  # Amazon Linux 2
variable "key_name"  { default = "mi-key-pair" }
variable "instance_type" { default = "t2.micro" }

# ── Security Group: ALB ──────────────────────────────────────────────
resource "aws_security_group" "alb_sg" {
  name = "alb-sg"
  ingress { from_port=80 to_port=80 protocol="tcp" cidr_blocks=["0.0.0.0/0"] }
  egress  { from_port=0  to_port=0  protocol="-1"  cidr_blocks=["0.0.0.0/0"] }
}

# ── Security Group: API EC2 ──────────────────────────────────────────
resource "aws_security_group" "api_sg" {
  name = "api-sg"
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]  # solo desde el ALB
  }
  ingress { from_port=22 to_port=22 protocol="tcp" cidr_blocks=["0.0.0.0/0"] }
  egress  { from_port=0  to_port=0  protocol="-1"  cidr_blocks=["0.0.0.0/0"] }
}

# ── Security Group: Servicios internos ──────────────────────────────
resource "aws_security_group" "internal_sg" {
  name = "internal-sg"
  ingress { from_port=0 to_port=65535 protocol="tcp" cidr_blocks=["10.0.0.0/8"] }
  egress  { from_port=0 to_port=0     protocol="-1"  cidr_blocks=["0.0.0.0/0"] }
}

# ── EC2: RabbitMQ ────────────────────────────────────────────────────
resource "aws_instance" "rabbitmq" {
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name
  vpc_security_group_ids = [aws_security_group.internal_sg.id]
  user_data = <<-EOF
    #!/bin/bash
    amazon-linux-extras enable rabbitmq-server38
    yum install -y rabbitmq-server
    systemctl start rabbitmq-server
    systemctl enable rabbitmq-server
    rabbitmq-plugins enable rabbitmq_management
  EOF
  tags = { Name = "rabbitmq" }
}

# ── EC2: PostgreSQL ──────────────────────────────────────────────────
resource "aws_instance" "database" {
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name
  vpc_security_group_ids = [aws_security_group.internal_sg.id]
  user_data = <<-EOF
    #!/bin/bash
    amazon-linux-extras enable postgresql14
    yum install -y postgresql-server
    postgresql-setup initdb
    systemctl start postgresql
    systemctl enable postgresql
    sudo -u postgres psql -c "CREATE USER admin WITH PASSWORD 'password';"
    sudo -u postgres psql -c "CREATE DATABASE projectdb OWNER admin;"
  EOF
  tags = { Name = "database" }
}

# ── EC2: API 1 ───────────────────────────────────────────────────────
resource "aws_instance" "api_1" {
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name
  vpc_security_group_ids = [aws_security_group.api_sg.id]
  user_data = <<-EOF
    #!/bin/bash
    yum install -y python3 git
    pip3 install fastapi uvicorn boto3 pika sqlalchemy psycopg2-binary
    cd /home/ec2-user
    git clone https://github.com/TU_USUARIO/TU_REPO.git proyecto
    cd proyecto
    uvicorn api.main:app --host 0.0.0.0 --port 8000 &
  EOF
  tags = { Name = "api-1" }
}

# ── EC2: API 2 ───────────────────────────────────────────────────────
resource "aws_instance" "api_2" {
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name
  vpc_security_group_ids = [aws_security_group.api_sg.id]
  user_data     = aws_instance.api_1.user_data
  tags          = { Name = "api-2" }
}

# ── EC2: Consumer POST ───────────────────────────────────────────────
resource "aws_instance" "consumer_post" {
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name
  vpc_security_group_ids = [aws_security_group.internal_sg.id]
  user_data = <<-EOF
    #!/bin/bash
    yum install -y python3 git
    pip3 install boto3 pika sqlalchemy psycopg2-binary
    cd /home/ec2-user
    git clone https://github.com/TU_USUARIO/TU_REPO.git proyecto
    cd proyecto
    python3 workers/consumer_post.py &
  EOF
  tags = { Name = "consumer-post" }
}

# ── EC2: Worker DELETE ───────────────────────────────────────────────
resource "aws_instance" "worker_delete" {
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name
  vpc_security_group_ids = [aws_security_group.internal_sg.id]
  user_data = <<-EOF
    #!/bin/bash
    yum install -y python3 git
    pip3 install boto3 pika sqlalchemy psycopg2-binary
    cd /home/ec2-user
    git clone https://github.com/TU_USUARIO/TU_REPO.git proyecto
    cd proyecto
    python3 workers/consumer_delete.py &
  EOF
  tags = { Name = "worker-delete" }
}

# ── Parameter Store: IPs internas ───────────────────────────────────
resource "aws_ssm_parameter" "rabbitmq_ip" {
  name  = "/project/rabbitmq/ip"
  type  = "String"
  value = aws_instance.rabbitmq.private_ip
}

resource "aws_ssm_parameter" "db_ip" {
  name  = "/project/db/ip"
  type  = "String"
  value = aws_instance.database.private_ip
}

# ── ALB ─────────────────────────────────────────────────────────────
data "aws_subnets" "default" {
  filter { name = "default-for-az" values = ["true"] }
}

resource "aws_lb" "main" {
  name               = "project-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = data.aws_subnets.default.ids
}

resource "aws_lb_target_group" "api_tg" {
  name     = "api-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.default.id

  health_check {
    path                = "/health"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_tg.arn
  }
}

resource "aws_lb_target_group_attachment" "api_1" {
  target_group_arn = aws_lb_target_group.api_tg.arn
  target_id        = aws_instance.api_1.id
  port             = 8000
}

resource "aws_lb_target_group_attachment" "api_2" {
  target_group_arn = aws_lb_target_group.api_tg.arn
  target_id        = aws_instance.api_2.id
  port             = 8000
}

# ── Parameter Store: DNS del ALB ────────────────────────────────────
resource "aws_ssm_parameter" "alb_dns" {
  name  = "/project/alb/dns"
  type  = "String"
  value = aws_lb.main.dns_name
}

data "aws_vpc" "default" {
  default = true
}
```

**`infra/outputs.tf`**
```hcl
output "alb_dns"      { value = aws_lb.main.dns_name }
output "rabbitmq_ip"  { value = aws_instance.rabbitmq.private_ip }
output "database_ip"  { value = aws_instance.database.private_ip }
output "api_1_ip"     { value = aws_instance.api_1.public_ip }
output "api_2_ip"     { value = aws_instance.api_2.public_ip }
```

### Paso 15: Aplicar la infraestructura

```bash
cd infra/
tofu init
tofu plan       # revisar qué va a crear
tofu apply      # escribir "yes" para confirmar
```

---

## FASE 7 — Deploy en EC2 (Día 5)

### Paso 16: Verificar que todo está corriendo

```bash
# 1. Ver los outputs de OpenTofu
tofu output

# 2. Probar el health check del ALB
curl http://<ALB_DNS>/health
# Esperado: {"status": "ok"}

# 3. Crear una task vía el ALB
curl -X POST http://<ALB_DNS>/tasks
# Esperado: {"taskId": "...", "status": "PENDING"}

# 4. Verificar que el TaskId queda en DONE después de unos segundos
curl http://<ALB_DNS>/tasks/<TaskId>
# Esperado: {"status": "DONE"}

# 5. Listar órdenes
curl http://<ALB_DNS>/orders
```

### Paso 17: Verificar el Swagger

```
http://<ALB_DNS>/docs
```
FastAPI genera el Swagger automáticamente. Tomar captura para la sustentación.

---

## FASE 8 — Entregables Finales (Día 6)

### Paso 18: README.md en inglés

```markdown
# IoT Tasks API

## Architecture Overview
REST API with async task processing using RabbitMQ workers and PostgreSQL.
All services run on individual EC2 instances. Traffic enters through an AWS ALB.

## Prerequisites
- Docker
- AWS Learner Lab credentials
- OpenTofu installed

## How to run locally
1. Build the dev environment: `docker build -t iot_dev_environment_image .`
2. Start container: `docker run -it -v $(pwd):/app iot_dev_environment_image bash`
3. Configure AWS CLI: `aws configure`

## How to deploy infrastructure
1. `cd infra/`
2. `tofu init && tofu apply`

## API Examples
# Create a task
curl -X POST http://<ALB_DNS>/tasks

# Check task status
curl http://<ALB_DNS>/tasks/<task_id>

# List all tasks
curl http://<ALB_DNS>/tasks

# Delete a task
curl -X DELETE http://<ALB_DNS>/tasks/<task_id>

# List orders
curl http://<ALB_DNS>/orders

## Running Tests
pytest tests/ -v

## Static Analysis
ruff check .
```

### Paso 19: Checklist final antes de la sustentación

- [ ] `tofu apply` crea todas las EC2 sin errores
- [ ] `curl http://<ALB>/health` responde 200
- [ ] `POST /tasks` retorna 202 + TaskId
- [ ] Después de ~5 segundos el TaskId está en status DONE
- [ ] `GET /orders` retorna las órdenes creadas
- [ ] `DELETE /tasks/{id}` retorna 202 y el worker lo procesa
- [ ] `pytest tests/ -v` pasa todos los tests
- [ ] `ruff check .` termina sin errores
- [ ] Swagger accesible en `http://<ALB>/docs`
- [ ] README.md en inglés completo
- [ ] Repo en GitHub con todo el código
- [ ] Parameter Store tiene `/project/rabbitmq/ip`, `/project/db/ip`, `/project/alb/dns`

---

## Cronograma Recomendado

| Día | Actividad | Fase |
|-----|-----------|------|
| Día 1 AM | Docker + AWS CLI + estructura del proyecto | Fase 0 |
| Día 1 PM | Modelos de DB + conexión PostgreSQL | Fase 1 |
| Día 2 AM | Endpoints FastAPI (5 rutas) | Fase 2 |
| Día 2 PM | Workers consumer_post y worker_delete | Fase 3 |
| Día 3 AM | Productor de eventos sintéticos | Fase 4 |
| Día 3 PM | Tests con pytest + análisis con Ruff | Fase 5 |
| Día 4    | OpenTofu: EC2s + ALB + Parameter Store | Fase 6 |
| Día 5    | Deploy real en AWS + verificación end-to-end | Fase 7 |
| Día 6    | README + checklist + práctica de sustentación | Fase 8 |

---

## Puntos Clave para la Sustentación

1. **¿Por qué el balancer?** Para alta disponibilidad — si cae api_1, api_2 sigue respondiendo
2. **¿Por qué Parameter Store?** Para no hardcodear IPs — si la EC2 se reinicia, la IP puede cambiar
3. **¿Por qué POST y DELETE son asíncronos?** Porque el procesamiento es pesado — la API no bloquea mientras el worker trabaja
4. **¿Qué pasa si RabbitMQ cae?** Las tasks quedan en PENDING indefinidamente — punto de mejora futuro
5. **¿Cómo el consumer sabe cuándo procesar?** RabbitMQ le entrega el mensaje cuando el consumer está listo (patrón push)
6. **¿Qué tablas tiene la DB?** Tasks (TaskId, Status, Date) y Orders (OrderId, TaskId, Date)
