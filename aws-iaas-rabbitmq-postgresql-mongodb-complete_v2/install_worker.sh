#!/bin/bash
set -euo pipefail

# Amazon Linux 2023 - Instalar Python y git
sudo dnf update -y
sudo dnf install -y python3 python3-pip git

# Clonar el repositorio de la aplicación
git clone https://github.com/josueruano1/orders-tasks-app.git /opt/orders-app

# Crear el archivo de variables de entorno con los valores inyectados por Terraform
cat <<'ENVEOF' > /opt/orders-app/worker/.env
DB_HOST=${db_host}
DB_PORT=${db_port}
DB_NAME=${db_name}
DB_USER=${db_user}
DB_PASSWORD=${db_password}
RABBITMQ_HOST=${rabbitmq_host}
RABBITMQ_PORT=${rabbitmq_port}
RABBITMQ_USER=${rabbitmq_user}
RABBITMQ_PASSWORD=${rabbitmq_password}
RABBITMQ_QUEUE=${rabbitmq_queue}
ENVEOF

# Instalar dependencias del worker
python3 -m pip install --ignore-installed -r /opt/orders-app/worker/requirements.txt

# Crear el servicio systemd para que el worker arranque automáticamente
cat <<'SERVICEEOF' | sudo tee /etc/systemd/system/orders-worker.service >/dev/null
[Unit]
Description=Orders Task Worker
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/orders-app/worker
EnvironmentFile=/opt/orders-app/worker/.env
ExecStart=/usr/bin/python3 /opt/orders-app/worker/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable orders-worker
sudo systemctl restart orders-worker
