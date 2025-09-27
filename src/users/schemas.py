from uuid import UUID

from pydantic import BaseModel


class UserCreate(BaseModel):
	username: str
	password: str


class UserRead(BaseModel):
	id: UUID
	username: str

	class Config:
		from_attributes = True


class UserLogin(BaseModel):
	username: str
	password: str
