#!/bin/bash
set -euo pipefail

# Amazon Linux 2023 - Instalar PostgreSQL 15
sudo dnf update -y
sudo dnf install -y postgresql15-server

# Inicializar la base de datos
sudo postgresql-setup --initdb

# Configurar Postgres para aceptar conexiones externas
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" /var/lib/pgsql/data/postgresql.conf

# Permitir conexiones IPv4 en pg_hba.conf para el bloque 0.0.0.0/0
echo "host    all             all             0.0.0.0/0               scram-sha-256" | sudo tee -a /var/lib/pgsql/data/pg_hba.conf

# Habilitar y reiniciar Postgres
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Crear base de datos y usuario del proyecto de forma idempotente
sudo -u postgres psql <<'SQL'
DO
$$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin') THEN
		CREATE ROLE admin LOGIN PASSWORD 'password123';
	ELSE
		ALTER ROLE admin WITH LOGIN PASSWORD 'password123';
	END IF;
END
$$;
SQL

sudo -u postgres psql <<'SQL'
SELECT 'CREATE DATABASE mydb OWNER admin'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'mydb')
\gexec
GRANT ALL PRIVILEGES ON DATABASE mydb TO admin;
SQL

cat <<'SQL' | sudo tee /tmp/project_schema.sql >/dev/null
${schema_sql}
SQL

sudo -u postgres psql -d mydb -f /tmp/project_schema.sql
