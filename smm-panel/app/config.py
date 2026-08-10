from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "dev-secret-change-in-production"
    data_dir: str = "data"
    database_path: str = ""
    public_base_url: str = "http://localhost:8080"
    delivery_interval_seconds: float = 2.0
    delivery_batch_ratio: float = 0.08
    default_user_balance: float = 50.0
    admin_email: str = "walednajjar2@gmail.com"
    admin_password: str = "najjar"
    instagram_client_id: str = ""
    instagram_client_secret: str = ""
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    payment_phone: str = "+96871924089"
    payment_account: str = "70202010390101"
    payment_bank: str = "صحار الإسلامي"
    payment_holder: str = "Waleed Mohammed Abdu"
    payment_iban: str = "OM390380070202010390101"
    payment_swift: str = "BSHROMRUISL"

    class Config:
        env_prefix = "SMM_"

    @property
    def db_path(self) -> str:
        if self.database_path.strip():
            return self.database_path.strip()
        return f"{self.data_dir.rstrip('/')}/panel.db"


settings = Settings()
