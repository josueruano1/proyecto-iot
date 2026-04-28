#!/bin/bash
set -euo pipefail

# Amazon Linux 2023 - Instalar Docker
sudo dnf update -y
sudo dnf install -y docker git

# Instalar Docker Compose (recomendado)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Habilitar y arrancar Docker
sudo systemctl enable docker
sudo systemctl start docker

# Añadir al usuario ec2-user al grupo docker
sudo usermod -aG docker ec2-user

# --- Despliegue de la API FastAPI ---

# Crear directorio para la API
mkdir -p /home/ec2-user/api
cd /home/ec2-user/api

# Crear main.py
cat <<'EOF' > main.py
${api_main_py}
EOF

# Crear settings.py
cat <<'EOF' > settings.py
${api_settings_py}
EOF

# Crear db.py
cat <<'EOF' > db.py
${api_db_py}
EOF

# Crear schemas.py
cat <<'EOF' > schemas.py
${api_schemas_py}
EOF

# Crear repository.py
cat <<'EOF' > repository.py
${api_repository_py}
EOF

# Crear rabbitmq_client.py
cat <<'EOF' > rabbitmq_client.py
${api_rabbitmq_client_py}
EOF

# Crear service.py
cat <<'EOF' > service.py
${api_service_py}
EOF

# Crear requirements.txt
cat <<'EOF' > requirements.txt
${api_requirements_txt}
EOF

# Crear Dockerfile
cat <<'EOF' > Dockerfile
${api_dockerfile}
EOF

cat <<'EOF' > .env
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
EOF

# Construir y ejecutar el contenedor
sudo docker rm -f fast-api || true
sudo docker build -t orders-tasks-api .
sudo docker run -d --restart=always --name fast-api --env-file .env -p 80:8000 orders-tasks-api
