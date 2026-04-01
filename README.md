# Depended Chat

A modern chat backend template built with **Python 3.12**, **FastAPI**, and **PostgreSQL**.

## Features

- FastAPI application with modular structure inspired by [`fastapi-best-practices`](https://github.com/zhanymkanov/fastapi-best-practices)
- Asynchronous SQLAlchemy models with PostgreSQL 16+
- Alembic migrations
- In-process WebSocket connection manager for realtime updates
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

## Docker

Run the application, PostgreSQL database, and Nginx reverse proxy with Docker Compose:

```bash
docker compose up --build
```

The API will be available at [http://localhost](http://localhost).

> ⚠️ Realtime delivery currently uses an **in-process** WebSocket connection manager.
> Run the API with a single Uvicorn worker (`UVICORN_WORKERS=1`) unless you add a shared pub/sub broker.
