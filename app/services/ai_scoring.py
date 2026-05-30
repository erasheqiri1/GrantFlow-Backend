import json
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.tenant.models import (
    Application, ApplicationAnswer, AIScore,
    Grant, Criteria
)
from app.core.ai_client import get_ai_client

# Alias për backward compatibility me testet (pjesa tjetër shtohet pas klasës)
_get_client = get_ai_client


class AIScoreService:
    """Shërbimi për vlerësimin AI të aplikimeve."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _parse_attachment_text(file_path: str) -> str:
        try:
            local_path = file_path.lstrip("/")
            import os
            if not os.path.exists(local_path):
                return ""
            ext = os.path.splitext(local_path)[1].lower()
            if ext == ".pdf":
                import pdfplumber
                text_parts = []
                with pdfplumber.open(local_path) as pdf:
                    for page in pdf.pages[:5]:
                        t = page.extract_text()
                        if t:
                            text_parts.append(t.strip())
                return "\n".join(text_parts)[:2000]
            return ""
        except Exception:
            return ""

    @staticmethod
    def _build_prompt(app, grant, criteria, answers, doc_texts=None) -> str:
        lines = []
        lines.append(f"GRANT: {grant.title if grant else 'Pa titull'}")
        if grant and grant.description:
            lines.append(f"Pershkrimi: {grant.description[:500]}")

        if criteria:
            lines.append("\nKRITERET E VLERESIMIT:")
            for c in criteria:
                weight_pct = round(float(c.weight) * 100) if c.weight else 0
                req = "e detyrueshme" if c.is_required else "opsionale"
                lines.append(f"  - {c.name} ({weight_pct}%, {req})")
        else:
            lines.append("\nNuk ka kritere specifike — vlerëso bazuar ne cilesine e pergjithshme.")

        lines.append("\nAPLIKIMI:")
        if app.motivation_letter:
            lines.append(f"Letra motivuese:\n{app.motivation_letter[:1000]}")

        if answers:
            lines.append("\nPergjigjet:")
            for i, a in enumerate(answers, 1):
                lines.append(f"  {i}. {a.answer_text or '(pa pergjigje)'}")

        if doc_texts:
            lines.append("\nDOKUMENTET E NGARKUARA:")
            for doc in doc_texts:
                lines.append(doc[:1000])

        lines.append("\nJep nje vleresim te drejte 0-100 dhe arsyetim te shkurter ne shqip.")
        return "\n".join(lines)

    def score_application(self, application_id: str) -> AIScore:
        """Vlerëson një aplikim me AI dhe ruan rezultatin në tabelën ai_scores."""
        import uuid
        try:
            aid = uuid.UUID(application_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="ID e pavlefshme")

        existing = self.db.query(AIScore).filter(AIScore.application_id == aid).first()
        if existing and existing.ai_score is not None:
            existing.is_cached = True
            return existing

        app = self.db.query(Application).filter(Application.id == aid).first()
        if not app:
            raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")

        from app.models.tenant.models import Attachment
        grant       = self.db.query(Grant).filter(Grant.id == app.grant_id).first()
        criteria    = self.db.query(Criteria).filter(Criteria.grant_id == app.grant_id).all()
        answers     = self.db.query(ApplicationAnswer).filter(ApplicationAnswer.application_id == aid).all()
        attachments = self.db.query(Attachment).filter(Attachment.application_id == aid).all()

        doc_texts = []
        for att in attachments:
            text = self._parse_attachment_text(att.file_path)
            if text:
                doc_texts.append(f"[{att.file_name}]\n{text}")

        client, model_name = get_ai_client()

        ai_score_val  = None
        justification = ""
        ai_available  = False

        if client is not None:
            try:
                prompt   = self._build_prompt(app, grant, criteria, answers, doc_texts or None)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a strict expert grant evaluator. "
                                "Evaluate the application objectively based on the grant criteria. "
                                "Be very critical: random text, gibberish, or very short answers must score 0-15. "
                                "Incomplete or vague answers score 15-40. Only well-written, detailed, relevant "
                                "applications score above 60. "
                                "Return ONLY a valid JSON object with keys: "
                                "'score' (integer 0-100) and 'justification' (string, max 300 chars, in Albanian)."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500,
                    response_format={"type": "json_object"},
                )
                result        = json.loads(response.choices[0].message.content)
                ai_score_val  = float(result.get("score", 0))
                justification = str(result.get("justification", ""))
                if ai_score_val < 15:
                    ai_score_val = 0.0
                ai_available = True
            except Exception:
                model_name    = "unavailable"
                justification = "Shërbimi AI ishte i padisponueshëm gjatë vlerësimit."
        else:
            model_name    = "unavailable"
            justification = "Shërbimi AI nuk është konfiguruar."

        ai_weight        = float(grant.ai_weight) if grant and grant.ai_weight else 0.6
        commissioner_val = float(existing.commissioner_score) if existing and existing.commissioner_score is not None else 0.0

        if ai_available and ai_score_val is not None:
            final_score = round(ai_score_val * ai_weight + commissioner_val * (1 - ai_weight), 2)
        else:
            final_score = None

        now = datetime.now(timezone.utc)
        if existing:
            existing.ai_score      = ai_score_val
            existing.justification = justification
            existing.final_score   = final_score
            existing.model_used    = model_name
            existing.scored_at     = now
            existing.is_cached     = False
        else:
            existing = AIScore(
                application_id = aid,
                ai_score       = ai_score_val,
                justification  = justification,
                final_score    = final_score,
                model_used     = model_name,
                scored_at      = now,
                is_cached      = False,
            )
            self.db.add(existing)

        self.db.commit()
        return existing

    def set_commissioner_score(self, application_id: str, commissioner_score: float) -> AIScore:
        import uuid
        from app.models.tenant.models import Grant
        try:
            aid = uuid.UUID(application_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="ID e pavlefshme")

        if not (0 <= commissioner_score <= 100):
            raise HTTPException(status_code=422, detail="Pikët duhet të jenë 0-100")

        score_row = self.db.query(AIScore).filter(AIScore.application_id == aid).first()

        if not score_row or score_row.ai_score is None:
            raise HTTPException(
                status_code=409,
                detail="Vlerësimi AI nuk është kompletuar për këtë aplikim. "
                       "Provo sërish kur shërbimi AI të jetë aktiv ose kontakto administratorin."
            )

        app = self.db.query(Application).filter(Application.id == aid).first()
        if not app:
            raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")
        grant = self.db.query(Grant).filter(Grant.id == app.grant_id).first()
        ai_weight = float(grant.ai_weight) if grant and grant.ai_weight else 0.6

        ai_val = float(score_row.ai_score) if score_row and score_row.ai_score is not None else 0.0
        final  = round((ai_val * ai_weight) + (commissioner_score * (1 - ai_weight)), 2)

        if score_row:
            score_row.commissioner_score = commissioner_score
            score_row.final_score        = final
            score_row.is_cached          = False
        else:
            score_row = AIScore(
                application_id     = aid,
                ai_score           = None,
                commissioner_score = commissioner_score,
                final_score        = final,
                model_used         = "commissioner-only",
                is_cached          = False,
            )
            self.db.add(score_row)

        from app.models.tenant.models import ApplicationStatus, GrantStatus
        if app.status == ApplicationStatus.SUBMITTED:
            app.status = ApplicationStatus.UNDER_REVIEW

        self.db.commit()
        self._check_auto_finalize(grant, app)
        return score_row

    def _check_auto_finalize(self, grant, scored_app) -> None:
        try:
            from datetime import datetime, timezone
            from app.models.tenant.models import ApplicationStatus, GrantStatus, Application

            if not grant:
                return

            now = datetime.now(timezone.utc)
            deadline_passed = grant.deadline is not None and grant.deadline < now
            is_closed       = grant.status == GrantStatus.CLOSED

            if grant.status == GrantStatus.FINALIZED:
                return

            if not (deadline_passed or is_closed):
                return

            active_apps = self.db.query(Application).filter(
                Application.grant_id == grant.id,
                Application.status.in_([ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW])
            ).all()

            if not active_apps:
                return

            all_scored = all(
                self.db.query(AIScore).filter(
                    AIScore.application_id == a.id,
                    AIScore.commissioner_score.isnot(None)
                ).first() is not None
                for a in active_apps
            )

            if not all_scored:
                return

            from app.services.grants import GrantService
            system_user = {"user_id": str(scored_app.user_id), "tenant_id": None}
            GrantService(self.db).finalize_grant(str(grant.id), system_user)
            print(f"[auto-finalize] Grant {grant.id} u finalizua automatikisht.")

        except Exception as e:
            print(f"[auto-finalize] dështoi: {e}")

    def get_score(self, application_id: str) -> AIScore | None:
        import uuid
        try:
            aid = uuid.UUID(application_id)
        except ValueError:
            return None
        return self.db.query(AIScore).filter(AIScore.application_id == aid).first()


# Alias pas klasës — për backward compatibility me testet dhe Celery tasks
_build_prompt = AIScoreService._build_prompt


def score_application(application_id: str, db) -> AIScore:
    """Wrapper funksion për Celery task — thirr AIScoreService.score_application."""
    return AIScoreService(db).score_application(application_id)
