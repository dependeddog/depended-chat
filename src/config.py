from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,  # ENV имена ищутся без учета регистра
    )

    # Обязательные из окружения
    jwt_secret_key: SecretStr = Field(
        ...,
        validation_alias=AliasChoices("JWT_SECRET_KEY", "JWT_SECRET"),
        description="Секрет для подписи JWT",
    )
    jwt_algorithm: str = Field(
        ...,
        validation_alias="JWT_ALGORITHM"
    )
    access_token_expire_minutes: int = Field(
        ...,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(
        ...,
        validation_alias="REFRESH_TOKEN_EXPIRE_DAYS"
    )
    jwt_issuer: str = Field(
        ...,
        validation_alias="JWT_ISSUER"
    )
    jwt_audience: str = Field(
        ...,
        validation_alias="JWT_AUDIENCE"
    )

    database_url: str = Field(
        ...,
        validation_alias=AliasChoices("DATABASE_URL", "DB_URL"),
        description="DSN Postgres",
    )

    rabbitmq_url: str = Field(
        ...,
        validation_alias="RABBITMQ_URL"
    )

    @property
    def jwt_secret(self) -> str:
        return self.jwt_secret_key.get_secret_value()


settings = Settings()
