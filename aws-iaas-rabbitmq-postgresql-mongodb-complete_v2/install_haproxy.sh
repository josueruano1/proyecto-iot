#!/bin/bash
# ==========================================
# HAProxy Load Balancer - User Data Script
# Amazon Linux 2023
# Corre HAProxy como contenedor Docker
# (mismo patrón que simple_balancer)
# ==========================================

set -e

# 1. Instalar Docker
dnf update -y
dnf install -y docker
systemctl enable docker
systemctl start docker

# 2. Instalar Docker Compose Plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
     -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 3. Crear directorio de trabajo
mkdir -p /opt/haproxy
cd /opt/haproxy

# 4. Escribir haproxy.cfg con las IPs privadas de los backends
#    (Variables inyectadas por Terraform via templatefile)
cat > /opt/haproxy/haproxy.cfg <<EOF
defaults
    mode http
    timeout connect 5000ms
    timeout client  50000ms
    timeout server  50000ms

frontend http-in
    bind *:80
    default_backend api_servers

backend api_servers
    balance roundrobin
    option  httpchk GET /health
    server  api1 ${api_server_1_ip}:80 check
    server  api2 ${api_server_2_ip}:80 check
EOF

# 5. Escribir docker-compose.yml (igual a simple_balancer)
cat > /opt/haproxy/docker-compose.yml <<'COMPOSE'
services:
  lb:
    image: haproxy:latest
    container_name: load_balancer
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
    ports:
      - "80:80"
    restart: unless-stopped
COMPOSE

# 6. Levantar el contenedor
docker compose up -d
