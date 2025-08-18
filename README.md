# Depended Chat

A modern chat backend template built with **Python 3.12**, **FastAPI**, and **PostgreSQL**.

## Features

- FastAPI application with modular structure inspired by [`fastapi-best-practices`](https://github.com/zhanymkanov/fastapi-best-practices)
- Asynchronous SQLAlchemy models with PostgreSQL 16+
- Alembic migrations
- RabbitMQ broker integration via `aio-pika`
- Ready for future extensions like media messages and calls

## Development

Install dependencies with [uv](https://github.com/astral-sh/uv):

```bash
uv pip install -r pyproject.toml
```

Run the application:

```bash
uvicorn src.main:app --reload
```

Apply database migrations:

```bash
alembic upgrade head
```
