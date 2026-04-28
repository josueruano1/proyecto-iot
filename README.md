# Orders, Tasks, RabbitMQ, and PostgreSQL on AWS EC2

This repository now contains a distributed AWS IaaS project built around these components:
- HAProxy load balancer on its own EC2 instance
- REST API on its own EC2 instance
- REST API replica on its own EC2 instance
- RabbitMQ on its own EC2 instance
- PostgreSQL on its own EC2 instance
- Worker consumer on its own EC2 instance
- Synthetic producer on its own EC2 instance
- Local Docker development environment for building and validating the project

## Functional flow
1. `POST /orders` creates an asynchronous task and returns `202 Accepted` with a `taskId`.
2. Requests enter through the load balancer and are forwarded to one of the API backends.
3. The API stores the task in PostgreSQL and publishes a message to RabbitMQ.
4. The worker consumes the message, creates the order, and updates the task status.
5. `DELETE /orders/{orderId}` follows the same asynchronous pattern.
6. `GET /tasks/{taskId}` lets the client poll the current task status.
7. `GET /orders`, `GET /orders/{orderId}`, and `PUT /orders/{orderId}` are synchronous API operations.

## Main project folders
- [0_dev_environment](c:\Users\josue\Desktop\Decimo\1_basic_lambda_with_deploy\1_basic_lambda_with_deploy\0_dev_environment): official Docker development environment
- [aws-iaas-rabbitmq-postgresql-mongodb-complete_v2](c:\Users\josue\Desktop\Decimo\1_basic_lambda_with_deploy\1_basic_lambda_with_deploy\aws-iaas-rabbitmq-postgresql-mongodb-complete_v2): AWS Terraform, bootstrap scripts, API, worker, producer, and SQL schema
- [3_lambda_ec2](c:\Users\josue\Desktop\Decimo\1_basic_lambda_with_deploy\1_basic_lambda_with_deploy\3_lambda_ec2): previous Lambda exercise, not part of the final distributed architecture

## Local development
Use the Docker environment in [0_dev_environment](c:\Users\josue\Desktop\Decimo\1_basic_lambda_with_deploy\1_basic_lambda_with_deploy\0_dev_environment) as the reproducible local workspace.

## AWS deployment
Use the Terraform and bootstrap scripts in [aws-iaas-rabbitmq-postgresql-mongodb-complete_v2](c:\Users\josue\Desktop\Decimo\1_basic_lambda_with_deploy\1_basic_lambda_with_deploy\aws-iaas-rabbitmq-postgresql-mongodb-complete_v2).

## Notes
- The old Lambda files remain in the repository as previous coursework material.
- The final architecture for this project is EC2-based, not Lambda-based.
- The public entry point for clients is the HAProxy load balancer, not the API backends directly.