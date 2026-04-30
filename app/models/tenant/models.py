import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Boolean, Integer, Text, Numeric,
    DateTime, ForeignKey, UniqueConstraint,
    Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base

class Grant(Base):
    __tablename__  = "grants"
    __table_args__ = {"schema": "tenant"}

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title          = Column(String(200),    nullable=False)
    description    = Column(Text,           nullable=True)
    budget         = Column(Numeric(12, 2), nullable=True)
    currency       = Column(String(10),     default="EUR", nullable=False)
    deadline       = Column(DateTime(timezone=True), nullable=True)
    max_applicants = Column(Integer,        nullable=True)
    status         = Column(SAEnum(GrantStatus),   default=GrantStatus.DRAFT,  nullable=False)
    applicant_type = Column(SAEnum(ApplicantType), default=ApplicantType.ANY,  nullable=False)
    ai_weight      = Column(Numeric(3, 2),  default=0.60, nullable=False)
    created_by     = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=False)
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class Criteria(Base):
    __tablename__  = "criteria"
    __table_args__ = (
        UniqueConstraint("grant_id", "name", name="uq_grant_criteria_name"),
        {"schema": "tenant"}
    )

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grant_id    = Column(UUID(as_uuid=True), ForeignKey("tenant.grants.id", ondelete="CASCADE"), nullable=False)
    name        = Column(String(100),   nullable=False)
    description = Column(Text,          nullable=True)
    weight      = Column(Numeric(3, 2), nullable=False)
    min_value   = Column(Numeric(5, 2), nullable=True)
    is_required = Column(Boolean,       default=True, nullable=False)


class GrantTag(Base):
    __tablename__  = "grant_tags"
    __table_args__ = (
        UniqueConstraint("grant_id", "tag", name="uq_grant_tag"),
        {"schema": "tenant"}
    )

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grant_id = Column(UUID(as_uuid=True), ForeignKey("tenant.grants.id", ondelete="CASCADE"), nullable=False)
    tag      = Column(String(50), nullable=False)


class ApplicationQuestion(Base):
    __tablename__  = "application_questions"
    __table_args__ = {"schema": "tenant"}

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grant_id      = Column(UUID(as_uuid=True), ForeignKey("tenant.grants.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text,  nullable=False)
    question_type = Column(SAEnum(QuestionType), default=QuestionType.LONG_TEXT, nullable=False)
    is_required   = Column(Boolean, default=True, nullable=False)
    order_no      = Column(Integer, default=1,    nullable=False)


class Application(Base):
    __tablename__  = "applications"
    __table_args__ = (
        UniqueConstraint("grant_id", "user_id", name="uq_application_grant_user"),
        {"schema": "tenant"}
    )

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grant_id          = Column(UUID(as_uuid=True), ForeignKey("tenant.grants.id",  ondelete="CASCADE"), nullable=False)
    user_id           = Column(UUID(as_uuid=True), ForeignKey("public.users.id",   ondelete="CASCADE"), nullable=False)
    status            = Column(SAEnum(ApplicationStatus), default=ApplicationStatus.DRAFT, nullable=False)
    motivation_letter = Column(Text, nullable=True)
    submitted_at      = Column(DateTime(timezone=True), nullable=True)
    decided_by        = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=True)
    decided_at        = Column(DateTime(timezone=True), nullable=True)
    decision_reason   = Column(Text, nullable=True)
    assigned_to       = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=True)
    created_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                               onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ApplicationAnswer(Base):
    __tablename__  = "application_answers"
    __table_args__ = (
        UniqueConstraint("application_id", "question_id", name="uq_application_question_answer"),
        {"schema": "tenant"}
    )

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("tenant.applications.id", ondelete="CASCADE"), nullable=False)
    question_id    = Column(UUID(as_uuid=True), ForeignKey("tenant.application_questions.id", ondelete="CASCADE"), nullable=False)
    answer_text    = Column(Text, nullable=True)
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class CV(Base):
    __tablename__  = "cvs"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_cv_application"),
        {"schema": "tenant"}
    )

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("tenant.applications.id", ondelete="CASCADE"), nullable=False)
    file_path      = Column(String(500), nullable=False)
    file_name      = Column(String(200), nullable=False)
    parsed_text    = Column(Text,        nullable=True)
    uploaded_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Attachment(Base):
    __tablename__  = "attachments"
    __table_args__ = {"schema": "tenant"}

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("tenant.applications.id", ondelete="CASCADE"), nullable=False)
    file_path      = Column(String(500), nullable=False)
    file_name      = Column(String(200), nullable=False)
    file_type      = Column(String(100), nullable=True)
    size_bytes     = Column(Integer,     nullable=True)
    uploaded_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

