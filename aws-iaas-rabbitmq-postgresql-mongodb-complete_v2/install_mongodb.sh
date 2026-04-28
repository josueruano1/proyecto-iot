#!/bin/bash
# Amazon Linux 2023 - Instalar MongoDB 7.0 + Configuración de Admin

# 1. Agregar el repositorio oficial de MongoDB para Amazon Linux (CentOS/RHEL)
sudo bash -c 'cat <<EOF > /etc/yum.repos.d/mongodb-org-7.0.repo
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/amazon/2023/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-7.0.asc
EOF'

# 2. Instalación de MongoDB
sudo dnf install -y mongodb-org

# 3. Configuración inicial de red (Bind IP)
sudo sed -i 's/bindIp: 127.0.0.1/bindIp: 0.0.0.0/' /etc/mongod.conf

# 4. Iniciar servicio
sudo systemctl daemon-reload
sudo systemctl enable mongod
sudo systemctl start mongod

# 5. Esperar a que MongoDB esté listo para recibir comandos
until sudo mongosh --eval "db.adminCommand('ping')" &>/dev/null; do
  echo "Esperando a MongoDB..."
  sleep 2
done

# 6. Crear usuario administrador
sudo mongosh admin --eval "
  db.createUser({
    user: 'admin',
    pwd: 'password123',
    roles: [ { role: 'userAdminAnyDatabase', db: 'admin' }, 'readWriteAnyDatabase' ]
  })
"

# 7. Activar la autenticación en el archivo de configuración
cat <<EOF >> /etc/mongod.conf
security:
  authorization: enabled
EOF

# 8. Reiniciar para aplicar seguridad
sudo systemctl restart mongod

echo "MongoDB instalado y securizado con usuario 'admin' a las $(date)" >> /var/log/mongodb_setup.log
