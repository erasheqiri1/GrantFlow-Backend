import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Boolean, Integer, Text,
    DateTime, ForeignKey, UniqueConstraint,
    Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class TenantStatus(str, enum.Enum):
    PENDING  = "PENDING"
    ACTIVE   = "ACTIVE"
    REJECTED = "REJECTED"


class RoleName(str, enum.Enum):
    SUPER_ADMIN  = "SUPER_ADMIN"
    ORG_ADMIN    = "ORG_ADMIN"
    COMMISSIONER = "COMMISSIONER"
    APPLICANT    = "APPLICANT"


class Tenant(Base):
    __tablename__  = "tenants"
    __table_args__ = {"schema": "public"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug       = Column(String(100), unique=True, nullable=False)
    name       = Column(String(200), nullable=False)
    status     = Column(SAEnum(TenantStatus), default=TenantStatus.PENDING, nullable=False)
    email      = Column(String(200), nullable=False)
    nipt       = Column(String(50),  nullable=True)
    doc_path   = Column(String(500), nullable=True)
    website    = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class User(Base):
    __tablename__  = "users"
    __table_args__ = {"schema": "public"}

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email         = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(500), nullable=False)
    first_name    = Column(String(100), nullable=False)
    last_name     = Column(String(100), nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at    = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class UserProfile(Base):
    __tablename__  = "user_profiles"
    __table_args__ = {"schema": "public"}

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id             = Column(
        UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    bio                 = Column(Text,        nullable=True)
    profile_picture     = Column(String(500), nullable=True)
    phone               = Column(String(50),  nullable=True)
    country             = Column(String(100), nullable=True)
    city                = Column(String(100), nullable=True)
    applicant_type      = Column(String(50),  nullable=True)
    university          = Column(String(200), nullable=True)
    field_of_study      = Column(String(200), nullable=True)
    graduation_year     = Column(Integer,     nullable=True)
    organization_name   = Column(String(200), nullable=True)
    organization_number = Column(String(100), nullable=True)
    skills              = Column(Text,        nullable=True)
    education           = Column(Text,        nullable=True)
    experience          = Column(Text,        nullable=True)
    linkedin_url        = Column(String(300), nullable=True)
    portfolio_url       = Column(String(300), nullable=True)
    website_url         = Column(String(300), nullable=True)
    created_at          = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at          = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class PasswordResetToken(Base):
    __tablename__  = "password_reset_tokens"
    __table_args__ = {"schema": "public"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    token      = Column(String(200), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used    = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Role(Base):
    __tablename__  = "roles"
    __table_args__ = {"schema": "public"}

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(SAEnum(RoleName), unique=True, nullable=False)
    description = Column(String(200), nullable=True)


class Permission(Base):
    __tablename__  = "permissions"
    __table_args__ = {"schema": "public"}

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codename = Column(String(100), unique=True, nullable=False)
    resource = Column(String(50),  nullable=False)
    action   = Column(String(50),  nullable=False)


class RolePermission(Base):
    __tablename__  = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
        {"schema": "public"}
    )

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id       = Column(UUID(as_uuid=True), ForeignKey("public.roles.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("public.permissions.id", ondelete="CASCADE"), nullable=False)