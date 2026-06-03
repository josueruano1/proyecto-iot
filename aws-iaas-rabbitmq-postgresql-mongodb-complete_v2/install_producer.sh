#!/bin/bash
set -euo pipefail

# Amazon Linux 2023 - Instalar Python y git
sudo dnf update -y
sudo dnf install -y python3 python3-pip git

# Clonar el repositorio de la aplicación
git clone https://github.com/josueruano1/orders-tasks-app.git /opt/orders-app

# Crear el archivo de variables de entorno con los valores inyectados por Terraform
cat <<'ENVEOF' > /opt/orders-app/producer/.env
POLL_INTERVAL_SECONDS=3
CYCLE_INTERVAL_SECONDS=15
TASK_POLL_ATTEMPTS=20
ENVEOF

# Instalar dependencias del producer
python3 -m pip install --upgrade pip
python3 -m pip install -r /opt/orders-app/producer/requirements.txt

# Crear el servicio systemd para que el producer arranque automáticamente
cat <<'SERVICEEOF' | sudo tee /etc/systemd/system/synthetic-producer.service >/dev/null
[Unit]
Description=Synthetic Event Producer
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/orders-app/producer
EnvironmentFile=/opt/orders-app/producer/.env
ExecStart=/usr/bin/python3 /opt/orders-app/producer/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable synthetic-producer
sudo systemctl restart synthetic-producer
