# Development Container

This container is part of the project.

Purpose:
- provide a reproducible local development environment
- run AWS CLI and Terraform locally even if they are not installed on the host
- develop and test the API, worker, and support scripts
- validate connectivity to RabbitMQ and PostgreSQL during development

The final system still runs on separate AWS EC2 instances, but this container is the official local workspace.

# Build the image
From the repository root:

```powershell
docker build -t decimo-dev-env .\0_dev_environment
```

Or from inside `0_dev_environment`:

```powershell
docker build -t decimo-dev-env .
```

# Run the container
From the repository root:

```powershell
docker run --rm -it --name decimo-dev -v "${PWD}:/workspace" decimo-dev-env
```

If you want the container to keep running in the background:

```powershell
docker run -d --name decimo-dev -v "${PWD}:/workspace" decimo-dev-env
```

# Open a shell in the running container
```powershell
docker exec -it decimo-dev bash
```

# Working directory inside the container
The project is mounted at:

```text
/workspace
```

Python dependencies are installed in the image, not inside the mounted project folder. This avoids losing packages when the bind mount is attached.

# Included tools
- Python 3.12
- AWS CLI v2
- Terraform
- PostgreSQL client tools
- FastAPI and Uvicorn
- RabbitMQ client library for Python
- Common shell tools for development and debugging

# Configure AWS credentials inside the container
Option 1: configure them manually.

```bash
aws configure
```

Option 2: if your learner lab gives you temporary credentials, copy them into `/root/.aws/credentials` inside the container.

Example check:

```bash
aws sts get-caller-identity
```

# Suggested usage during this project
- edit code from the mounted workspace
- run Terraform commands from `/workspace/aws-iaas-rabbitmq-postgresql-mongodb-complete_v2`
- run API or worker scripts locally before deploying to AWS
- test SQL connectivity with `psql`