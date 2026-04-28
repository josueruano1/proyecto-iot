# Infrastructure Module

This Terraform module is the base AWS IaaS setup for the project.

Current scope:
- HAProxy load balancer on its own EC2 instance
- RabbitMQ on its own EC2 instance
- Two REST API backend instances behind the load balancer
- Worker on its own EC2 instance
- Synthetic producer on its own EC2 instance
- PostgreSQL on its own EC2 instance

Out of scope for the current delivery:
- MongoDB
- HAProxy / external load balancer

# 1. Discover your AWS network values
aws ec2 describe-subnets --query "Subnets[*].[SubnetId, VpcId, AvailabilityZone]" --output text

# 2. Update variables.tf
- Set vpc_id
- Set subnet_id
- Set key_name
- Adjust instance_type if needed for your learner lab quota

# 3. Initialize and apply
## With Terraform
terraform init
terraform plan -out=project.tfplan
terraform apply project.tfplan

## With OpenTofu
tofu init
tofu plan -out=project.tfplan
tofu apply project.tfplan

# 4. Destroy when finished
terraform destroy

## Or with OpenTofu
tofu destroy

# 5. Optional targeted apply examples
tofu apply -target=aws_instance.rabbitmq
tofu apply -target=aws_instance.haproxy
tofu apply -target=aws_instance.api_server
tofu apply -target=aws_instance.worker
tofu apply -target=aws_instance.producer
tofu apply -target=aws_instance.postgres

# 6. Useful checks after deployment
## API
http://[API_PUBLIC_IP]/health

## Load balancer
The public API endpoint now resolves to the HAProxy instance, which forwards requests to both API backends.

## RabbitMQ management UI
http://[RABBITMQ_PUBLIC_IP]:15672/

## Synthetic producer
The producer runs automatically on its EC2 instance and exercises:
- POST /orders
- GET /tasks/{taskId}
- GET /orders/{orderId}
- PUT /orders/{orderId}
- GET /orders
- DELETE /orders/{orderId}

## PostgreSQL
Connect with your preferred PostgreSQL client using the deployed EC2 public IP.

# 7. Notes
- The API is the public HTTP entry point in this version.
- Public HTTP traffic enters through HAProxy and only the load balancer accepts internet traffic on port 80.
- RabbitMQ AMQP and PostgreSQL are restricted to the API and Worker security groups.
- The producer is intended to generate synthetic traffic from inside AWS.
- AWS SSM Parameter Store is used to publish the public IPs of the core services.



