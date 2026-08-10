from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=2, max_length=80)


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


class UrlValidateRequest(BaseModel):
    url: str = Field(min_length=5, max_length=500)
    platform: Optional[str] = Field(default=None, max_length=40)
