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

class GrantStatus(str, enum.Enum):
    DRAFT      = "DRAFT"
    PUBLISHED  = "PUBLISHED"
    CLOSED     = "CLOSED"

class ApplicantType(str, enum.Enum):
    ANY          = "ANY"
    STUDENT      = "STUDENT"
    BUSINESS     = "BUSINESS"
    ORGANIZATION = "ORGANIZATION"
    INDIVIDUAL   = "INDIVIDUAL"


class ApplicationStatus(str, enum.Enum):
    DRAFT        = "DRAFT"
    SUBMITTED    = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED     = "APPROVED"
    REJECTED     = "REJECTED"

#forma qe munet org_admini te +kritere
class QuestionType(str, enum.Enum):
    TEXT      = "TEXT"
    LONG_TEXT = "LONG_TEXT"
    NUMBER    = "NUMBER"
    FILE      = "FILE"
    YES_NO    = "YES_NO"

class NotificationType(str, enum.Enum):
    APPLICATION_STATUS = "APPLICATION_STATUS"
    DEADLINE           = "DEADLINE"
    INVITE             = "INVITE"
    SYSTEM             = "SYSTEM"

class EmailStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT    = "SENT"
    FAILED  = "FAILED"

class DecisionType(str, enum.Enum):
        APPROVE = "APPROVE"
        REJECT = "REJECT"




class Grant(Base):
    __tablename__  = "grants"
    __table_args__ = {"schema": "tenant"}

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title          = Column(String(200),    nullable=False)
    description    = Column(Text,           nullable=True)
    budget         = Column(Numeric(12, 2), nullable=True)
    currency       = Column(String(10),     default="EUR", nullable=False)
    grant_value    = Column(Numeric(12, 2), nullable=True)
    deadline       = Column(DateTime(timezone=True), nullable=True)
    max_applicants = Column(Integer,        nullable=True)
    status         = Column(SAEnum(GrantStatus),   default=GrantStatus.DRAFT,  nullable=False)
    applicant_type = Column(SAEnum(ApplicantType), default=ApplicantType.ANY,  nullable=False)
    ai_weight      = Column(Numeric(5,2), default=0.60, nullable=False)
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
    weight      = Column(Numeric(5, 2), nullable=False)
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
    parsed_text    = Column(Text,        nullable=True)  # text i nxjerr qe AI ta lexoj
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


class AIScore(Base):
    __tablename__  = "ai_scores"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_ai_score_application"),
        {"schema": "tenant"}
    )

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("tenant.applications.id", ondelete="CASCADE"), nullable=False)
    ai_score       = Column(Numeric(5, 2), nullable=True)
    justification  = Column(Text,          nullable=True)
    final_score    = Column(Numeric(5, 2), nullable=True)
    rank_position  = Column(Integer,       nullable=True)
    model_used     = Column(String(100),   nullable=True)
    is_cached      = Column(Boolean, default=False, nullable=False)
    scored_at      = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class CommissionerScore(Base):
    __tablename__  = "commissioner_scores"
    __table_args__ = (
        UniqueConstraint("application_id", "criteria_id", name="uq_commissioner_score"),
        {"schema": "tenant"}
    )

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id  = Column(UUID(as_uuid=True), ForeignKey("tenant.applications.id", ondelete="CASCADE"), nullable=False)
    commissioner_id = Column(UUID(as_uuid=True), ForeignKey("public.users.id"),        nullable=False)
    criteria_id     = Column(UUID(as_uuid=True), ForeignKey("tenant.criteria.id",      ondelete="CASCADE"), nullable=False)
    score           = Column(Integer, nullable=False)
    comment         = Column(Text,    nullable=True)
    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class CommissionerDecision(Base):
    __tablename__  = "commissioner_decisions"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_decision_application"),
        {"schema": "tenant"}
    )

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id  = Column(UUID(as_uuid=True), ForeignKey("tenant.applications.id", ondelete="CASCADE"), nullable=False)
    commissioner_id = Column(UUID(as_uuid=True), ForeignKey("public.users.id"),        nullable=False)
    decision        = Column(SAEnum(DecisionType), nullable=False)
    reason          = Column(Text,       nullable=True)
    decided_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

#qikjo osht per me i shpernda ne menyre automatike kontrollin e aplikmeve tek komisioneret
class CommissionerWorkload(Base):
    __tablename__  = "commissioner_workload"
    __table_args__ = (
        UniqueConstraint("commissioner_id", name="uq_commissioner_workload"),
        {"schema": "tenant"}
    )

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commissioner_id = Column(UUID(as_uuid=True), ForeignKey("public.users.id",
                             ondelete="CASCADE"), nullable=False)
    assigned_count  = Column(Integer, default=0, nullable=False)
    completed_count = Column(Integer, default=0, nullable=False)
    updated_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class Invitation(Base):
    __tablename__  = "invitations"
    __table_args__ = {"schema": "tenant"}

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email       = Column(String(200), nullable=False)
    role_id     = Column(UUID(as_uuid=True), ForeignKey("public.roles.id"), nullable=False)
    invited_by  = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=False)
    token       = Column(String(200), unique=True, nullable=False)
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    is_used     = Column(Boolean, default=False, nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=True)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Notification(Base):
    __tablename__  = "notifications"
    __table_args__ = {"schema": "tenant"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    title      = Column(String(200), nullable=False)
    message    = Column(Text,        nullable=False)
    type       = Column(SAEnum(NotificationType), nullable=False)
    is_read    = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class EmailLog(Base):
    __tablename__  = "email_logs"
    __table_args__ = {"schema": "tenant"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    to_email   = Column(String(200), nullable=False)
    subject    = Column(String(300), nullable=False)
    body       = Column(Text,        nullable=True)
    status     = Column(SAEnum(EmailStatus), default=EmailStatus.PENDING, nullable=False)
    sent_at    = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class ApplicationStatusUpdate(Base):
    __tablename__  = "application_status_updates"
    __table_args__ = {"schema": "tenant"}

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("tenant.applications.id", ondelete="CASCADE"), nullable=False)
    old_status = Column(SAEnum(ApplicationStatus), nullable=False)
    new_status = Column(SAEnum(ApplicationStatus), nullable=False)
    changed_by     = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=False)
    changed_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
