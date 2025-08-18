FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg pydantic-settings alembic aio-pika

# Copy project files
COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
