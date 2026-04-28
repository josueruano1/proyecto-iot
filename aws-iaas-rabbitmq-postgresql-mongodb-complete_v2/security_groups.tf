# ==========================================
# Security Group: RabbitMQ
# ==========================================
resource "aws_security_group" "rabbitmq_sg" {
  name        = "rabbitmq_sg"
  description = "Allow SSH, AMQP from app services, and RabbitMQ management UI"
  vpc_id      = var.vpc_id

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # RabbitMQ AMQP
  ingress {
    from_port   = 5672
    to_port     = 5672
    protocol    = "tcp"
    security_groups = [aws_security_group.api_sg.id, aws_security_group.worker_sg.id]
  }

  # RabbitMQ Management API
  ingress {
    from_port   = 15672
    to_port     = 15672
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "rabbitmq_sg"
  }
}

# ==========================================
# Security Group: HAProxy Load Balancer EC2
# ==========================================
resource "aws_security_group" "haproxy_sg" {
  name        = "haproxy_sg"
  description = "Allow SSH and public HTTP to the HAProxy load balancer"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "haproxy_sg"
  }
}

# ==========================================
# Security Group: Docker / REST API
# ==========================================
resource "aws_security_group" "api_sg" {
  name        = "api_sg"
  description = "Allow SSH and HTTP only from the HAProxy load balancer"
  vpc_id      = var.vpc_id

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTP solo desde el balanceador
  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.haproxy_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "api_sg"
  }
}

# ==========================================
# Security Group: Async Worker
# ==========================================
resource "aws_security_group" "worker_sg" {
  name        = "worker_sg"
  description = "Allow SSH only for Worker (Initiates outbound connections)"
  vpc_id      = var.vpc_id

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # El Worker consume mensajes (Conexión saliente hacia RabbitMQ/Postgres)
  # por ende no necesita puertos Ingress extra.
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "worker_sg"
  }
}

# ==========================================
# Security Group: Synthetic Producer
# ==========================================
resource "aws_security_group" "producer_sg" {
  name        = "producer_sg"
  description = "Allow SSH only for the synthetic producer"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "producer_sg"
  }
}

# ==========================================
# Security Group: PostgreSQL
# ==========================================
resource "aws_security_group" "postgres_sg" {
  name        = "postgres_sg"
  description = "Allow SSH and PostgreSQL from app services"
  vpc_id      = var.vpc_id

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # PostgreSQL
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.api_sg.id, aws_security_group.worker_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "postgres_sg"
  }
}
