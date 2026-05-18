import re

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional



class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Minimum 8 karaktere")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Duhet të paktën 1 shkronjë e madhe")
        if not re.search(r"[0-9]", v):
            raise ValueError("Duhet të paktën 1 numër")
        if not re.search(r"[!@#$%^&*]", v):
            raise ValueError("Duhet të paktën 1 karakter special (!@#$%^&*)")
        return v



class RegisterOrgRequest(BaseModel):

    email: EmailStr
    password: str
    first_name: str
    last_name: str

    
    org_name: str
    org_slug: str

    @field_validator("password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Minimum 8 karaktere")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Duhet të paktën 1 shkronjë e madhe")
        if not re.search(r"[0-9]", v):
            raise ValueError("Duhet të paktën 1 numër")
        if not re.search(r"[!@#$%^&*]", v):
            raise ValueError("Duhet të paktën 1 karakter special (!@#$%^&*)")
        return v

    @field_validator("org_slug")
    @classmethod
    def slug_format(cls, v):
        import re
        if not re.match(r'^[a-z0-9\-]+$', v):
            raise ValueError("Slug duhet të përmbajë vetëm shkronja të vogla, numra dhe vizë (-)")
        return v



class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_slug: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_slug: Optional[str] = None




class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    tenant_slug: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Minimum 8 karaktere")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Duhet të paktën 1 shkronjë e madhe")
        if not re.search(r"[0-9]", v):
            raise ValueError("Duhet të paktën 1 numër")
        if not re.search(r"[!@#$%^&*]", v):
            raise ValueError("Duhet të paktën 1 karakter special (!@#$%^&*)")
        return v



class InviteAcceptRequest(BaseModel):
    token: str
    first_name: str
    last_name: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Minimum 8 karaktere")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Duhet të paktën 1 shkronjë e madhe")
        if not re.search(r"[0-9]", v):
            raise ValueError("Duhet të paktën 1 numër")
        if not re.search(r"[!@#$%^&*]", v):
            raise ValueError("Duhet të paktën 1 karakter special (!@#$%^&*)")
        return v




class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    tenant_slug: Optional[str] = None

    class Config:
        from_attributes = True