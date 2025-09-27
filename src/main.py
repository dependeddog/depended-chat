from fastapi import FastAPI

from src.auth import router as auth_router
from src.chat.router import router as chat_router
from src.core.error_handlers import register_exception_handlers

app = FastAPI(title="Depended Chat")
register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
