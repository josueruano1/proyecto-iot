output "rabbitmq_public_ip" {
  value = aws_instance.rabbitmq.public_ip
  description = "IP pública del servidor RabbitMQ"
}

output "api_public_ip" {
  value       = aws_instance.haproxy.public_ip
  description = "IP pública del balanceador de la API"
}

output "api_backend_public_ips" {
  value       = aws_instance.api_server[*].public_ip
  description = "IPs públicas de los servidores API detrás del balanceador"
}

output "load_balancer_public_ip" {
  value       = aws_instance.haproxy.public_ip
  description = "IP pública del balanceador HAProxy"
}

output "worker_post_public_ip" {
  value = aws_instance.worker_post.public_ip
  description = "IP pública del Worker Post (consumer post - create_order)"
}

output "worker_delete_public_ip" {
  value = aws_instance.worker_delete.public_ip
  description = "IP pública del Worker Delete (consumer delete - delete_order)"
}

output "producer_public_ip" {
  value = aws_instance.producer.public_ip
  description = "IP pública del servidor productor sintético"
}

output "postgres_public_ip" {
  value = aws_instance.postgres.public_ip
  description = "IP pública del servidor PostgreSQL"
}
