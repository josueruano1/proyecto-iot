#!/bin/bash
set -euo pipefail

# Amazon Linux 2023 - Instalar dependencias para un Worker (Python)
sudo dnf update -y
sudo dnf install -y python3 python3-pip git

mkdir -p /opt/orders-worker
cd /opt/orders-worker

cat <<'EOF' > main.py
${worker_main_py}
EOF

cat <<'EOF' > settings.py
${worker_settings_py}
EOF

cat <<'EOF' > db.py
${worker_db_py}
EOF

cat <<'EOF' > handlers.py
${worker_handlers_py}
EOF

cat <<'EOF' > requirements.txt
${worker_requirements_txt}
EOF

cat <<'EOF' > /opt/orders-worker/.env
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
EOF

python3 -m pip install --ignore-installed -r requirements.txt

cat <<'EOF' | sudo tee /etc/systemd/system/orders-worker.service >/dev/null
[Unit]
Description=Orders Task Worker
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/orders-worker
EnvironmentFile=/opt/orders-worker/.env
ExecStart=/usr/bin/python3 /opt/orders-worker/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable orders-worker
sudo systemctl restart orders-worker
