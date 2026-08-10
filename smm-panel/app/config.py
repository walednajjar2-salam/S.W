from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "dev-secret-change-in-production"
    data_dir: str = "data"
    database_path: str = ""
    delivery_interval_seconds: float = 2.0
    delivery_batch_ratio: float = 0.08
    default_user_balance: float = 50.0
    admin_email: str = "walednajjar2@gmail.com"
    admin_password: str = "najjar"

    class Config:
        env_prefix = "SMM_"

    @property
    def db_path(self) -> str:
        if self.database_path.strip():
            return self.database_path.strip()
        return f"{self.data_dir.rstrip('/')}/panel.db"


settings = Settings()
