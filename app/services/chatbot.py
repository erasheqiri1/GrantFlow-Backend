from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

from app.models.public.models import Tenant, TenantStatus, ApplicantProfile, User
from app.core.ai_client import get_ai_client


class ChatService:

    def __init__(self, db: Session):
        self.db = db

    def _get_applicant_profile(self, user_id: str) -> str:
        profile = self.db.query(ApplicantProfile).filter(
            ApplicantProfile.user_id == user_id
        ).first()
        user = self.db.query(User).filter(User.id == user_id).first()

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

    def _get_published_grants(self) -> str:
        tenants = self.db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
        now = datetime.now(timezone.utc)
        grants = []

        for tenant in tenants:
            schema = f"tenant_{tenant.slug.replace('-', '_')}"
            try:
                rows = self.db.execute(text(f"""
                    SELECT title, description, applicant_type,
                           grant_value, budget, currency, deadline
                    FROM "{schema}".grants
                    WHERE status = 'PUBLISHED'
                """)).fetchall()
            except Exception:
                self.db.rollback()
                continue

            for r in rows:
                deadline_str = ""
                if r.deadline:
                    if r.deadline < now:
                        continue
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

    def chat(self, user_id: str, message: str, history: list = None) -> str:
        client, model = get_ai_client()
        if not client:
            raise HTTPException(
                status_code=503,
                detail="Shërbimi AI nuk është konfiguruar. Kontakto administratorin."
            )

        applicant_profile = self._get_applicant_profile(user_id)
        available_grants  = self._get_published_grants()

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

        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for h in history:
                role = h.get("role", "user")
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
        except Exception:
            raise HTTPException(status_code=503, detail="Gabim gjatë komunikimit me AI.")
