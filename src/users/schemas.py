from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
	username: str
	password: str


class UserRead(BaseModel):
	id: UUID
	username: str

	model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
	username: str
	password: str
