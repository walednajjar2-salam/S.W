from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "dev-secret-change-in-production"
    database_path: str = "data/panel.db"
    delivery_interval_seconds: float = 2.0
    delivery_batch_ratio: float = 0.08
    default_user_balance: float = 50.0
    admin_email: str = "walednajjar2@gmail.com"
    admin_password: str = "najjar"

    class Config:
        env_prefix = "SMM_"


settings = Settings()
