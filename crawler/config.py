from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações do projeto carregadas via variáveis de ambiente."""

    database_url: str = Field(default="sqlite+aiosqlite:///./cvc_feed.db", alias="DATABASE_URL")
    cvc_base_url: str = Field(default="https://www.cvc.com.br/lp/promocoes", alias="CVC_BASE_URL")
    crawler_interval_min: int = Field(default=30, alias="CRAWLER_INTERVAL_MIN")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    request_timeout_sec: int = Field(default=30, alias="REQUEST_TIMEOUT_SEC")
    headless: bool = Field(default=True, alias="HEADLESS")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_secret_key: str = Field(default="troque_esta_chave_em_producao", alias="API_SECRET_KEY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
