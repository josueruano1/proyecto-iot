#!/bin/bash
set -euo pipefail

# Amazon Linux 2023 - Instalar Docker y git
sudo dnf update -y
sudo dnf install -y docker git

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Habilitar y arrancar Docker
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user

# Clonar el repositorio de la aplicación
git clone https://github.com/josueruano1/orders-tasks-app.git /home/ec2-user/app

# Crear el archivo de variables de entorno con los valores inyectados por Terraform
cat <<'ENVEOF' > /home/ec2-user/app/api/.env
DB_HOST=${db_host}
DB_PORT=${db_port}
DB_NAME=${db_name}
DB_USER=${db_user}
DB_PASSWORD=${db_password}
RABBITMQ_HOST=${rabbitmq_host}
RABBITMQ_PORT=${rabbitmq_port}
RABBITMQ_USER=${rabbitmq_user}
RABBITMQ_PASSWORD=${rabbitmq_password}
RABBITMQ_QUEUE_CREATE=${rabbitmq_queue_create}
RABBITMQ_QUEUE_DELETE=${rabbitmq_queue_delete}
ENVEOF

# Construir y ejecutar el contenedor Docker de la API
cd /home/ec2-user/app/api
sudo docker rm -f fast-api || true
sudo docker build -t orders-tasks-api .
sudo docker run -d --restart=always --name fast-api --env-file .env -p 80:8000 orders-tasks-api
