from fastapi import FastAPI

from src.chat.router import router as chat_router

app = FastAPI(title="Depended Chat")
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
