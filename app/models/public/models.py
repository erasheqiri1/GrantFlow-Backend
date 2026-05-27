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

class ApplicantType(str, enum.Enum):
    STUDENT      = "STUDENT"
    BUSINESS     = "BUSINESS"
    ORGANIZATION = "ORGANIZATION"
    INDIVIDUAL   = "INDIVIDUAL"
    OTHER        = "OTHER"

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
    logo_path = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)

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

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email          = Column(String(200), unique=True, nullable=False)
    password_hash  = Column(String(500), nullable=False)
    first_name     = Column(String(100), nullable=False)
    last_name      = Column(String(100), nullable=False)
    is_active      = Column(Boolean, default=True,  nullable=False)
    email_verified = Column(Boolean, default=True,  nullable=False)
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at     = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

class UserProfile(Base):
    __tablename__  = "user_profiles"
    __table_args__ = {"schema": "public"}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("public.users.id",
                             ondelete="CASCADE"), unique=True, nullable=False)
    phone           = Column(String(50),  nullable=True)
    profile_picture = Column(String(500), nullable=True)
    address         = Column(String(300), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ApplicantProfile(Base):
    __tablename__  = "applicant_profiles"
    __table_args__ = {"schema": "public"}
    #te perbashketat
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id             = Column(UUID(as_uuid=True), ForeignKey("public.users.id",
                                 ondelete="CASCADE"), unique=True, nullable=False)
    personal_id         = Column(String(20),  nullable=True)
    applicant_type     = Column(SAEnum(ApplicantType), nullable=True)
    has_prev_grant      = Column(Boolean, nullable=True)
    description         = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)



    #per student
    study_level         = Column(String(50),  nullable=True)
    study_status        = Column(String(50),  nullable=True)
    study_year          = Column(Integer,     nullable=True)
    faculty             = Column(String(200), nullable=True)
    study_program       = Column(String(200), nullable=True)
    university          = Column(String(200), nullable=True)


    #per biznes
    business_name       = Column(String(200), nullable=True)
    business_type       = Column(String(100), nullable=True)
    activity_field      = Column(String(200), nullable=True)
    num_employees       = Column(String(50),  nullable=True)
    founded_year        = Column(Integer,     nullable=True)


    #per ojq
    org_name            = Column(String(200), nullable=True)
    org_type            = Column(String(100), nullable=True)
    org_field           = Column(String(200), nullable=True)
    num_staff           = Column(String(50),  nullable=True)
    org_founded_year    = Column(Integer,     nullable=True)
    reg_number          = Column(String(100), nullable=True)


    # per individ ( per njerez me pune)
    profession          = Column(String(200), nullable=True)
    experience_years    = Column(String(50),  nullable=True)
    key_skills          = Column(Text,        nullable=True)
    portfolio_url       = Column(String(300), nullable=True)
    cv_path             = Column(String(500), nullable=True)


    #qe nuk i perkasin asnje kategorie-tjeter
    role_title          = Column(String(200), nullable=True)
    interest_field      = Column(String(200), nullable=True)
    relevant_link       = Column(String(300), nullable=True)


class PasswordResetToken(Base):
    __tablename__  = "password_reset_tokens"
    __table_args__ = {"schema": "public"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    token      = Column(String(200), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used    = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class EmailVerificationToken(Base):
    __tablename__  = "email_verification_tokens"
    __table_args__ = {"schema": "public"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    token      = Column(String(200), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

#qikjo eshte implementimi i RBAC

class Role(Base):
    __tablename__  = "roles"
    __table_args__ = {"schema": "public"}

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(SAEnum(RoleName), unique=True, nullable=False)

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

class UserRole(Base):
        __tablename__ = "user_roles"
        __table_args__ = (
            UniqueConstraint("user_id", "role_id", "tenant_id", name="uq_user_role_tenant"),
            {"schema": "public"}
        )

        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        user_id = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
        role_id = Column(UUID(as_uuid=True), ForeignKey("public.roles.id", ondelete="CASCADE"), nullable=False)
        tenant_id = Column(UUID(as_uuid=True), ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=True)
        created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)