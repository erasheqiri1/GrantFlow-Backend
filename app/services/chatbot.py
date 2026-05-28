from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException
from openai import OpenAI

from app.models.public.models import Tenant, TenantStatus, ApplicantProfile, User
from app.core.config import settings


def _get_client():
    if settings.OPENAI_API_KEY:
        return OpenAI(api_key=settings.OPENAI_API_KEY), "gpt-4o-mini"
    if settings.GROQ_API_KEY:
        return OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        ), "llama-3.1-8b-instant"
    return None, None


def _get_applicant_profile(user_id: str, db: Session) -> str:
    """Merr profilin e aplikantit nga DB dhe e kthen si tekst për AI."""
    profile = db.query(ApplicantProfile).filter(
        ApplicantProfile.user_id == user_id
    ).first()
    user = db.query(User).filter(User.id == user_id).first()

    if not profile and not user:
        return "Profil i panjohur."

    lines = []
    if user:
        lines.append(f"Emri: {user.first_name} {user.last_name}")

    if profile:
        if profile.applicant_type:
            lines.append(f"Kategoria: {profile.applicant_type}")
        if profile.study_level:
            lines.append(f"Niveli i studimit: {profile.study_level}")
        if profile.study_year:
            lines.append(f"Viti i studimit: {profile.study_year}")
        if profile.faculty:
            lines.append(f"Fakulteti: {profile.faculty}")
        if profile.university:
            lines.append(f"Universiteti: {profile.university}")
        if profile.business_name:
            lines.append(f"Biznesi: {profile.business_name}")
        if profile.business_type:
            lines.append(f"Lloji i biznesit: {profile.business_type}")
        if profile.activity_field:
            lines.append(f"Fusha e aktivitetit: {profile.activity_field}")
        if profile.org_name:
            lines.append(f"Organizata: {profile.org_name}")
        if profile.profession:
            lines.append(f"Profesioni: {profile.profession}")
        if profile.experience_years:
            lines.append(f"Vite eksperience: {profile.experience_years}")
        if profile.description:
            lines.append(f"Përshkrimi: {profile.description}")

    return "\n".join(lines) if lines else "Profil i paplotësuar."


def _get_published_grants(db: Session) -> str:
    """Merr të gjitha grantet PUBLISHED nga të gjitha organizatat."""
    tenants = db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
    now = datetime.now(timezone.utc)
    grants = []

    for tenant in tenants:
        schema = f"tenant_{tenant.slug.replace('-', '_')}"
        try:
            rows = db.execute(text(f"""
                SELECT title, description, applicant_type,
                       grant_value, budget, currency, deadline
                FROM "{schema}".grants
                WHERE status = 'PUBLISHED'
            """)).fetchall()
        except Exception:
            db.rollback()
            continue

        for r in rows:
            deadline_str = ""
            if r.deadline:
                if r.deadline < now:
                    continue  # skip grants me deadline të kaluar
                deadline_str = r.deadline.strftime("%d %B %Y")

            amount = r.grant_value or r.budget
            amount_str = f"{float(amount):,.0f} {r.currency}" if amount else "E papërcaktuar"

            grants.append(
                f"- [{tenant.name}] {r.title} | "
                f"Shuma: {amount_str} | "
                f"Për: {r.applicant_type} | "
                f"Afati: {deadline_str or 'Pa afat'} | "
                f"Përshkrimi: {(r.description or '')[:200]}"
            )

    if not grants:
        return "Aktualisht nuk ka grante të hapura."

    return "\n".join(grants)


def chat(user_id: str, message: str, db: Session, history: list = None) -> str:
    """Thirr AI me kontekstin e aplikantit, historikun e bisedës dhe grantet e disponueshme."""
    client, model = _get_client()
    if not client:
        raise HTTPException(
            status_code=503,
            detail="Shërbimi AI nuk është konfiguruar. Kontakto administratorin."
        )

    applicant_profile = _get_applicant_profile(user_id, db)
    available_grants  = _get_published_grants(db)

    system_prompt = f"""Ti je asistenti i platformës GrantFlow — një platformë për menaxhimin e granteve në Kosovë.

Detyra jote është të ndihmosh aplikantët të gjejnë grantet më të përshtatshme bazuar në profilin e tyre.

PROFILI I APLIKANTIT:
{applicant_profile}

GRANTET E DISPONUESHME TANI:
{available_grants}

RREGULLA:
1. Përgjigju VETËM për tema lidhur me GrantFlow, grantet dhe aplikimet.
2. Nëse pyetja nuk lidhet me grantet ose platformën, thuaj: "Mund të të ndihmoj vetëm për çështje lidhur me grantet dhe GrantFlow."
3. Kur sugjeron grante, shpjego PSE janë të përshtatshme për profilin e aplikantit.
4. Fol në gjuhën shqipe gjithmonë.
5. Mos shpik grante — përdor vetëm ato që janë listuar më sipër.
6. Përgjigjet të jenë të shkurtra dhe të qarta — maksimum 3-4 fjali."""

    # Build messages: system + conversation history + current user message
    messages = [{"role": "system", "content": system_prompt}]

    if history:
        for h in history:
            role = h.get("role", "user")
            # Map frontend role names to OpenAI roles
            if role not in ("user", "assistant"):
                continue
            messages.append({"role": role, "content": h.get("text", "")})

    messages.append({"role": "user", "content": message})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=400,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=503, detail="Gabim gjatë komunikimit me AI.")
