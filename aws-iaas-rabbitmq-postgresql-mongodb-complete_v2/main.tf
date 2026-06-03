# 1. RabbitMQ EC2
resource "aws_instance" "rabbitmq" {
  ami               = var.ami_id
  instance_type     = var.instance_type
  key_name          = var.key_name
  subnet_id         = var.subnet_id
  vpc_security_group_ids = [aws_security_group.rabbitmq_sg.id]
  user_data         = file("${path.module}/install_rabbitmq.sh")

  tags = {
    Name    = "RabbitMQ-Server"
    Role    = "MessageBroker"
  }
}

# 2. Docker / API Rest EC2
resource "aws_instance" "api_server" {
  count             = 2
  ami               = var.ami_id
  instance_type     = var.instance_type
  key_name          = var.key_name
  subnet_id         = var.subnet_id
  vpc_security_group_ids = [aws_security_group.api_sg.id]
  user_data         = templatefile("${path.module}/install_api.sh", {
    db_host           = aws_instance.postgres.private_ip
    db_port           = "5432"
    db_name           = "mydb"
    db_user           = "admin"
    db_password       = "password123"
    rabbitmq_host     = aws_instance.rabbitmq.private_ip
    rabbitmq_port     = "5672"
    rabbitmq_user     = "admin"
    rabbitmq_password = "password123"
    rabbitmq_queue_create = "orders_create"
    rabbitmq_queue_delete = "orders_delete"
  })

  tags = {
    Name = "Docker-API-Server-${count.index + 1}"
    Role = "BackendAPI"
  }
}

# 3. HAProxy Load Balancer EC2
resource "aws_instance" "haproxy" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.haproxy_sg.id]
  user_data = templatefile("${path.module}/install_haproxy.sh", {
    api_server_1_ip = aws_instance.api_server[0].private_ip
    api_server_2_ip = aws_instance.api_server[1].private_ip
  })

  tags = {
    Name = "HAProxy-LoadBalancer"
    Role = "LoadBalancer"
  }
}

# 4a. Worker Post EC2 (consumer post - procesa create_order)
resource "aws_instance" "worker_post" {
  ami               = var.ami_id
  instance_type     = var.instance_type
  key_name          = var.key_name
  subnet_id         = var.subnet_id
  vpc_security_group_ids = [aws_security_group.worker_sg.id]
  user_data         = templatefile("${path.module}/install_worker.sh", {
    db_host           = aws_instance.postgres.private_ip
    db_port           = "5432"
    db_name           = "mydb"
    db_user           = "admin"
    db_password       = "password123"
    rabbitmq_host     = aws_instance.rabbitmq.private_ip
    rabbitmq_port     = "5672"
    rabbitmq_user     = "admin"
    rabbitmq_password = "password123"
    rabbitmq_queue    = "orders_create"
  })

  tags = {
    Name = "Worker-Post"
    Role = "ConsumerPost"
  }
}

# 4b. Worker Delete EC2 (worker/consumer delete - procesa delete_order)
resource "aws_instance" "worker_delete" {
  ami               = var.ami_id
  instance_type     = var.instance_type
  key_name          = var.key_name
  subnet_id         = var.subnet_id
  vpc_security_group_ids = [aws_security_group.worker_sg.id]
  user_data         = templatefile("${path.module}/install_worker.sh", {
    db_host           = aws_instance.postgres.private_ip
    db_port           = "5432"
    db_name           = "mydb"
    db_user           = "admin"
    db_password       = "password123"
    rabbitmq_host     = aws_instance.rabbitmq.private_ip
    rabbitmq_port     = "5672"
    rabbitmq_user     = "admin"
    rabbitmq_password = "password123"
    rabbitmq_queue    = "orders_delete"
  })

  tags = {
    Name = "Worker-Delete"
    Role = "ConsumerDelete"
  }
}

# 5. Synthetic Producer EC2
resource "aws_instance" "producer" {
  ami               = var.ami_id
  instance_type     = var.instance_type
  key_name          = var.key_name
  subnet_id         = var.subnet_id
  vpc_security_group_ids = [aws_security_group.producer_sg.id]
  user_data         = file("${path.module}/install_producer.sh")

  tags = {
    Name = "Synthetic-Producer"
    Role = "SyntheticEvents"
  }
}

# 6. PostgreSQL EC2
resource "aws_instance" "postgres" {
  ami               = var.ami_id
  instance_type     = var.instance_type
  key_name          = var.key_name
  subnet_id         = var.subnet_id
  vpc_security_group_ids = [aws_security_group.postgres_sg.id]
  user_data         = templatefile("${path.module}/install_postgres.sh", {
    schema_sql = file("${path.module}/sql/schema.sql")
  })

  tags = {
    Name    = "Postgres-Server"
    Role    = "Database"
  }
}

# ==========================================
# AWS Systems Manager Parameter Store
# ==========================================

resource "aws_ssm_parameter" "rabbitmq_ip" {
  name  = "/message-queue/dev/rabbitmq/public_ip"
  type  = "String"
  value = aws_instance.rabbitmq.public_ip
  description = "Public IP for RabbitMQ Server"
}

resource "aws_ssm_parameter" "api_ip" {
  name  = "/message-queue/dev/api/public_ip"
  type  = "String"
  value = aws_instance.haproxy.public_ip
  description = "Public IP for API Load Balancer"
}

resource "aws_ssm_parameter" "worker_post_ip" {
  name  = "/message-queue/dev/worker-post/public_ip"
  type  = "String"
  value = aws_instance.worker_post.public_ip
  description = "Public IP for Worker Post (consumer post)"
}

resource "aws_ssm_parameter" "worker_delete_ip" {
  name  = "/message-queue/dev/worker-delete/public_ip"
  type  = "String"
  value = aws_instance.worker_delete.public_ip
  description = "Public IP for Worker Delete (consumer delete)"
}

resource "aws_ssm_parameter" "producer_ip" {
  name  = "/message-queue/dev/producer/public_ip"
  type  = "String"
  value = aws_instance.producer.public_ip
  description = "Public IP for Synthetic Producer Server"
}

resource "aws_ssm_parameter" "postgres_ip" {
  name        = "/message-queue/dev/postgres/public_ip"
  type        = "String"
  value       = aws_instance.postgres.public_ip
  description = "Public IP for PostgreSQL Server"
}
