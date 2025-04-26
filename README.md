# Tariqi - Traffic Incident Reporting System

## Overview
Tariqi is a system for collecting, verifying, and distributing traffic incident reports in Palestine using Telegram.

## Running Locally (Using Docker)

### Prerequisites
- Docker installed and running
- A `.env` file created in the project root directory (see below)
- A PostgreSQL database (local or cloud)

### 1. Create `.env` File
Create a file named `.env` in the root of the project and add the following environment variables, replacing the placeholder values with your actual credentials:

```env
# Database (Connection string for your PostgreSQL database)
DATABASE_URL=postgresql://user:password@host:port/dbname

# Telegram (API credentials for Telethon client and Bot Token)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_GROUP_IDS=[123,456]  # JSON array of group IDs to monitor
TELEGRAM_PHONE_NUMBER=+1234567890

# Webhook (URL for FastAPI endpoint - use placeholder for local polling)
WEBHOOK_URL=http://localhost:8000/webhook/telegram

# Scheduler (Interval for the verification pipeline)
PIPELINE_RUN_INTERVAL_MINUTES=5
```

### 2. Build Docker Image
Open your terminal in the project root directory and run:
```bash
docker build -t tariqi .
```

### 3. Run Services
Run the API and Scheduler services in separate containers:

```bash
# Run the API service (Listens on port 8000)
docker run -d \
  --name tariqi-api \
  -p 8000:8000 \
  --env-file .env \
  -e SERVICE_TYPE=api \
  tariqi

# Run the Scheduler service (Runs background verification pipeline)
docker run -d \
  --name tariqi-scheduler \
  --env-file .env \
  -e SERVICE_TYPE=scheduler \
  tariqi
```

### 4. Accessing the API
The API will be available at `http://localhost:8000`.

### 5. Checking Logs
View logs for each service:
```bash
docker logs tariqi-api -f
docker logs tariqi-scheduler -f
```
(Press `Ctrl+C` to stop viewing logs)

## Deployment Guide (Using Docker & Railway Example)

This guide assumes deployment to Railway, but the principles apply to other container hosting platforms.

### 1. Database Setup
1. Create a PostgreSQL database on your preferred hosting provider (Railway, Neon, Aiven, etc.).
2. Obtain the database connection string.

### 2. GitHub Actions Secrets
Add the following secrets to your GitHub repository (`Settings -> Secrets and variables -> Actions`):
- `RAILWAY_TOKEN`: Your Railway API token.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE_NUMBER`: Your Telegram credentials.
- `DATABASE_URL`: Your production database connection string.
- `WEBHOOK_URL`: The public URL where your API will be hosted (needed for setting the Telegram webhook in production later).
- `PIPELINE_RUN_INTERVAL_MINUTES` (optional): Default is 5.
- `TELEGRAM_GROUP_IDS`: JSON string array, e.g., `"[12345, 67890]"`.
- `CODECOV_TOKEN` (optional): If using Codecov for coverage reports.

### 3. Railway Project Setup
1. Create a new Railway project.
2. Link it to your GitHub repository.
3. Railway will likely detect the `Dockerfile` and set up a deployment service. You may need to configure two separate services based on the same image, overriding the `SERVICE_TYPE` environment variable for each:
   - Service 1 (`tariqi-api`): Set `SERVICE_TYPE` to `api`.
   - Service 2 (`tariqi-scheduler`): Set `SERVICE_TYPE` to `scheduler`.
4. Configure environment variables in Railway, referencing the GitHub secrets or adding them directly.

### 4. GitHub Actions Workflow
The `.github/workflows/ci-cd.yml` workflow handles:
- Running tests on push/PR.
- Building and pushing the Docker image to GitHub Container Registry (`ghcr.io`).
- Deploying the latest image to Railway services (`tariqi-api` and `tariqi-scheduler`) on pushes to `main`.

### 5. Database Migrations
The `create_tables.py` script is intended to create tables if they don't exist. In a production environment, you might manage migrations more formally using tools like Alembic if schema changes become frequent.
For manual creation:
```bash
# Connect to your production environment (e.g., using Railway CLI or Docker exec)
python app/db/create_tables.py
```

### 6. Monitoring
- Use Railway's built-in logging and metrics.
- Monitor application logs via Railway or other configured logging services.

## AWS Lambda Scraper (Not Used in Current Docker Setup)

The initial plan ([TASK.md](./docs/TASK.md)) included an AWS Lambda function using Telethon to scrape messages. While the necessary code might exist (`app/services/scraper/handler.py` - *confirm path*), the current Docker setup uses a different approach where the Telethon client runs within the main application or a dedicated container if needed.

If you were to use the Lambda approach:

1.  **Deployment:** Package the scraper code and dependencies (using `serverless` framework or manually creating a zip file) and deploy it to AWS Lambda.
2.  **Environment Variables:** Configure Lambda environment variables for `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_NAME`, `TELEGRAM_GROUP_IDS`, `DATABASE_URL`, etc., securely using AWS Secrets Manager or Lambda environment variable encryption.
3.  **Triggers:** Set up an AWS EventBridge (CloudWatch Events) rule to trigger the Lambda function on a schedule (e.g., every 5 minutes).
4.  **Permissions:** Ensure the Lambda function has an IAM role with necessary permissions (e.g., VPC access if the database is private, permissions to write logs to CloudWatch).
5.  **Monitoring:** Monitor the Lambda function's execution via AWS CloudWatch Logs and Metrics.

## Development Guide

### Running the Verification Pipeline Scheduler Locally (Without Docker)
```bash
# Ensure .env file exists and Python environment is activated
python app/scheduler.py
```

### Running Tests
```bash
# Ensure .env file exists for test environment variables
pytest --cov=app
``` 