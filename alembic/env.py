import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

sys.path.insert(0, BASE_DIR)

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from src.config import settings
from src.models import Base
import src.auth.models  # noqa: F401  (RefreshToken и т.п.)
import src.chat.models  # noqa: F401  (User, Message и т.п.)

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def get_url() -> str:
    return settings.database_url.replace("+asyncpg", "")

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
