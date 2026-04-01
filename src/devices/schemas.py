from pydantic import BaseModel, Field


class FirebaseTokenUpsertRequest(BaseModel):
    token: str = Field(min_length=20, max_length=255)
    device_id: str | None = Field(default=None, max_length=128)
    platform: str | None = Field(default=None, max_length=32)


class FirebaseTokenDeleteRequest(BaseModel):
    token: str = Field(min_length=20, max_length=255)


class FirebaseTokenResponse(BaseModel):
    status: str = "ok"
