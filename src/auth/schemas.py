from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # секунд до истечения


class TokenPayload(BaseModel):
    sub: str
    iat: int
    nbf: int
    exp: int
    jti: str
    iss: str
    aud: str
    type: str  # "access" или "refresh"
    id: int
    username: str


class TokenPair(BaseModel):
    access_token: str
    access_expires_in: int
    refresh_token: str
