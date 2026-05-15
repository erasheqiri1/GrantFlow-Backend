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
            raise ValueError("Fjalëkalimi duhet të ketë të paktën 8 karaktere")
        return v



class RegisterOrgRequest(BaseModel):

    email: EmailStr
    password: str
    first_name: str
    last_name: str

    
    org_name: str
    org_slug: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Fjalëkalimi duhet të ketë të paktën 8 karaktere")
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
            raise ValueError("Fjalëkalimi duhet të ketë të paktën 8 karaktere")
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
            raise ValueError("Fjalëkalimi duhet të ketë të paktën 8 karaktere")
        return v




class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    tenant_slug: Optional[str] = None

    class Config:
        from_attributes = True