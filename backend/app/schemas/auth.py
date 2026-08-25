from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    # CAPTCHA (required when REGISTRATION_CAPTCHA_ENABLED)
    captcha_id: str | None = None
    captcha_answer: str | None = None


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    language_pref: str
    is_active: bool

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str