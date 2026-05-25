"""tenant schema tables (grants, applications, scores, criteria, etc.)

Revision ID: b8e2f1a94c30
Revises: f7a3c9e1b402
Create Date: 2026-05-24 12:00:00.000000

NOTE: Tenant schemas are created dynamically at runtime via
create_tenant_schema() when a SUPER_ADMIN approves a new organization.
This migration documents the full tenant schema structure so that all
15 tenant-schema models have corresponding migration coverage.
Each real tenant schema is named tenant_<slug> and is provisioned
automatically — this migration defines the canonical table structure.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8e2f1a94c30"
down_revision: Union[str, None] = "f7a3c9e1b402"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Placeholder schema used only in this migration file to document structure.
# Real tenant schemas are provisioned dynamically by create_tenant_schema().
SCHEMA = "tenant_template"


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')

    # 1. grants
    op.create_table(
        "grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("budget", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(10), nullable=False, server_default="EUR"),
        sa.Column("grant_value", sa.Numeric(12, 2)),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column("max_applicants", sa.Integer),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("applicant_type", sa.String(50), nullable=False, server_default="ANY"),
        sa.Column("ai_weight", sa.Numeric(5, 2), nullable=False, server_default="0.60"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        schema=SCHEMA,
    )

    # 2. criteria
    op.create_table(
        "criteria",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.grants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False),
        sa.Column("min_value", sa.Numeric(5, 2)),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="TRUE"),
        sa.UniqueConstraint("grant_id", "name", name="uq_grant_criteria_name"),
        schema=SCHEMA,
    )

    # 3. grant_tags
    op.create_table(
        "grant_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.grants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag", sa.String(50), nullable=False),
        sa.UniqueConstraint("grant_id", "tag", name="uq_grant_tag"),
        schema=SCHEMA,
    )

    # 4. application_questions
    op.create_table(
        "application_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.grants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("question_type", sa.String(50), nullable=False, server_default="LONG_TEXT"),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="TRUE"),
        sa.Column("order_no", sa.Integer, nullable=False, server_default="1"),
        schema=SCHEMA,
    )

    # 5. applications
    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.grants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("motivation_letter", sa.Text),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_reason", sa.Text),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("grant_id", "user_id", name="uq_application_grant_user"),
        schema=SCHEMA,
    )

    # 6. application_answers
    op.create_table(
        "application_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.application_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_text", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("application_id", "question_id", name="uq_application_question_answer"),
        schema=SCHEMA,
    )

    # 7. cvs
    op.create_table(
        "cvs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(200), nullable=False),
        sa.Column("parsed_text", sa.Text),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("application_id", name="uq_cv_application"),
        schema=SCHEMA,
    )

    # 8. attachments
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(200), nullable=False),
        sa.Column("file_type", sa.String(100)),
        sa.Column("size_bytes", sa.Integer),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        schema=SCHEMA,
    )

    # 9. ai_scores
    op.create_table(
        "ai_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_score", sa.Numeric(5, 2)),
        sa.Column("justification", sa.Text),
        sa.Column("commissioner_score", sa.Numeric(5, 2)),
        sa.Column("final_score", sa.Numeric(5, 2)),
        sa.Column("rank_position", sa.Integer),
        sa.Column("model_used", sa.String(100)),
        sa.Column("is_cached", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("scored_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("application_id", name="uq_ai_score_application"),
        schema=SCHEMA,
    )

    # 10. commissioner_scores
    op.create_table(
        "commissioner_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commissioner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id"), nullable=False),
        sa.Column("criteria_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.criteria.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("application_id", "criteria_id", name="uq_commissioner_score"),
        schema=SCHEMA,
    )

    # 11. commissioner_decisions
    op.create_table(
        "commissioner_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commissioner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id"), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("application_id", name="uq_decision_application"),
        schema=SCHEMA,
    )

    # 12. commissioner_workload
    op.create_table(
        "commissioner_workload",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("commissioner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("commissioner_id", name="uq_commissioner_workload"),
        schema=SCHEMA,
    )

    # 13. invitations
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.roles.id"), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id"), nullable=False),
        sa.Column("token", sa.Text, nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        schema=SCHEMA,
    )

    # 14. email_logs
    op.create_table(
        "email_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("to_email", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        schema=SCHEMA,
    )

    # 15. application_status_updates
    op.create_table(
        "application_status_updates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("old_status", sa.String(50), nullable=False),
        sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("public.users.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("application_status_updates", schema=SCHEMA)
    op.drop_table("email_logs",                 schema=SCHEMA)
    op.drop_table("invitations",                schema=SCHEMA)
    op.drop_table("commissioner_workload",      schema=SCHEMA)
    op.drop_table("commissioner_decisions",     schema=SCHEMA)
    op.drop_table("commissioner_scores",        schema=SCHEMA)
    op.drop_table("ai_scores",                  schema=SCHEMA)
    op.drop_table("attachments",                schema=SCHEMA)
    op.drop_table("cvs",                        schema=SCHEMA)
    op.drop_table("application_answers",        schema=SCHEMA)
    op.drop_table("applications",               schema=SCHEMA)
    op.drop_table("application_questions",      schema=SCHEMA)
    op.drop_table("grant_tags",                 schema=SCHEMA)
    op.drop_table("criteria",                   schema=SCHEMA)
    op.drop_table("grants",                     schema=SCHEMA)
    op.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}"')
