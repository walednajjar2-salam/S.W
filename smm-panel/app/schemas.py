from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=2, max_length=80)
    invite_code: str = Field(default="", max_length=40)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ServiceCreate(BaseModel):
    platform: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    min_qty: int = Field(ge=1)
    max_qty: int = Field(ge=1)
    price_per_1000: float = Field(gt=0)
    active: bool = True

    @field_validator("max_qty")
    @classmethod
    def max_gte_min(cls, v: int, info):
        min_qty = info.data.get("min_qty")
        if min_qty is not None and v < min_qty:
            raise ValueError("max_qty must be >= min_qty")
        return v


class ServiceUpdate(BaseModel):
    platform: Optional[str] = Field(default=None, min_length=2, max_length=40)
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    min_qty: Optional[int] = Field(default=None, ge=1)
    max_qty: Optional[int] = Field(default=None, ge=1)
    price_per_1000: Optional[float] = Field(default=None, gt=0)
    active: Optional[bool] = None


class OrderCreate(BaseModel):
    service_id: int
    target_url: str = Field(min_length=5, max_length=500)
    quantity: int = Field(ge=1)

    @field_validator("target_url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        return v.strip()


class WalletTopUp(BaseModel):
    amount: float = Field(gt=0, le=10000)


class BalanceAdjust(BaseModel):
    amount: float = Field(ge=-10000, le=10000)
    note: str = Field(default="", max_length=200)


class SocialLinkRequest(BaseModel):
    platform: str = Field(min_length=2, max_length=40)
    username: str = Field(min_length=1, max_length=80)

    @field_validator("platform")
    @classmethod
    def platform_allowed(cls, v: str) -> str:
        p = v.strip().lower()
        if p not in ("instagram", "tiktok"):
            raise ValueError("المنصة المدعومة: instagram أو tiktok")
        return p

    @field_validator("username")
    @classmethod
    def clean_username(cls, v: str) -> str:
        return v.strip().lstrip("@")

    @model_validator(mode="after")
    def extract_handle(self):
        from app.platforms import extract_username, is_valid_social_username

        handle = extract_username(self.username, self.platform)
        if not handle or not is_valid_social_username(handle):
            raise ValueError("أدخل اسم مستخدم صالح أو رابط حساب إنستجرام/تيك توك")
        self.username = handle
        return self


class OAuthConfigUpdate(BaseModel):
    public_base_url: Optional[str] = Field(default=None, max_length=300)
    instagram_client_id: Optional[str] = Field(default=None, max_length=200)
    instagram_client_secret: Optional[str] = Field(default=None, max_length=300)
    tiktok_client_key: Optional[str] = Field(default=None, max_length=200)
    tiktok_client_secret: Optional[str] = Field(default=None, max_length=300)


class UrlValidateRequest(BaseModel):
    url: str = Field(min_length=5, max_length=500)
    platform: Optional[str] = Field(default=None, max_length=40)


class AdminCreateUser(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=2, max_length=80)
    balance: float = Field(default=0, ge=0, le=10000)


class GenerateUsersRequest(BaseModel):
    count: int = Field(ge=1, le=100)
    email_prefix: str = Field(default="user", min_length=1, max_length=32)
    email_domain: str = Field(default="example.com", min_length=3, max_length=80)
    name_prefix: str = Field(default="عميل", min_length=1, max_length=40)
    password: str = Field(default="", max_length=128)
    balance: float = Field(default=0, ge=0, le=10000)


class InviteCodeCreate(BaseModel):
    max_uses: int = Field(default=1, ge=1, le=1000)
    note: str = Field(default="", max_length=200)
