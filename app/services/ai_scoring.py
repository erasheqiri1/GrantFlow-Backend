import json
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from openai import OpenAI

from app.models.tenant.models import (
    Application, ApplicationAnswer, AIScore,
    Grant, Criteria
)


def _get_client():

    from app.core.config import settings
    if settings.OPENAI_API_KEY:
        return OpenAI(api_key=settings.OPENAI_API_KEY), "gpt-4o-mini"
    if settings.GROQ_API_KEY:
        return OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        ), "llama-3.1-8b-instant"
    return None, "heuristic-fallback"


def _parse_attachment_text(file_path: str) -> str:

    try:
        # file_path është si "/uploads/attachments/uuid.pdf"
        local_path = file_path.lstrip("/")
        import os
        if not os.path.exists(local_path):
            return ""

        ext = os.path.splitext(local_path)[1].lower()

        if ext == ".pdf":
            import pdfplumber
            text_parts = []
            with pdfplumber.open(local_path) as pdf:
                for page in pdf.pages[:5]:  # max 5 faqe
                    t = page.extract_text()
                    if t:
                        text_parts.append(t.strip())
            return "\n".join(text_parts)[:2000]

        # Formatet e tjera (JPG, PNG, DOC) nuk mund të lexohen pa library shtesë
        return ""
    except Exception:
        return ""


def score_application(application_id: str, db: Session) -> AIScore:
    """
    Vlereson nje aplikim me AI dhe ruan rezultatin në tabelen ai_scores.
    """
    import uuid
    try:
        aid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="ID e pavlefshme")

    # Kontrollon cache
    existing = db.query(AIScore).filter(AIScore.application_id == aid).first()
    if existing and existing.ai_score is not None:
        existing.is_cached = True
        return existing

    # Merr aplikimin
    app = db.query(Application).filter(Application.id == aid).first()
    if not app:
        raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")

    # Merr grantin dhe kriteret
    from app.models.tenant.models import Attachment
    grant       = db.query(Grant).filter(Grant.id == app.grant_id).first()
    criteria    = db.query(Criteria).filter(Criteria.grant_id == app.grant_id).all()
    answers     = db.query(ApplicationAnswer).filter(ApplicationAnswer.application_id == aid).all()
    attachments = db.query(Attachment).filter(Attachment.application_id == aid).all()

    doc_texts = []
    for att in attachments:
        text = _parse_attachment_text(att.file_path)
        if text:
            doc_texts.append(f"[{att.file_name}]\n{text}")

    client, model_name = _get_client()

    ai_score_val  = 0.0
    justification = ""

    if client is not None:
        try:
            prompt   = _build_prompt(app, grant, criteria, answers, doc_texts or None)
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
            # Nëse AI jep < 15 për gibberish, e rregullojmë në 0
            if ai_score_val < 15:
                ai_score_val = 0.0
        except Exception as e:
            # Fallback nëse thirrja dështon
            ai_score_val, justification = _heuristic_score(app, answers, criteria)
            model_name = "heuristic-fallback"
    else:
        ai_score_val, justification = _heuristic_score(app, answers, criteria)
        model_name = "heuristic-fallback"

    # Llogarit final_score
    ai_weight        = float(grant.ai_weight) if grant and grant.ai_weight else 0.6
    commissioner_val = float(existing.commissioner_score) if existing and existing.commissioner_score is not None else 0.0
    final_score      = round(ai_score_val * ai_weight + commissioner_val * (1 - ai_weight), 2)

    # Ruan ose perditeson
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
        db.add(existing)

    db.commit()
    return existing


def set_commissioner_score(application_id: str, commissioner_score: float, db: Session) -> AIScore:

    import uuid
    from app.models.tenant.models import Grant
    try:
        aid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="ID e pavlefshme")

    if not (0 <= commissioner_score <= 100):
        raise HTTPException(status_code=422, detail="Pikët duhet të jenë 0-100")

    score_row = db.query(AIScore).filter(AIScore.application_id == aid).first()

    # Gjej ai_weight nga granti
    app = db.query(Application).filter(Application.id == aid).first()
    if not app:
        raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")
    grant = db.query(Grant).filter(Grant.id == app.grant_id).first()
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
        db.add(score_row)

    # Funksioni kalon aplikimin në UNDER_REVIEW
    from app.models.tenant.models import ApplicationStatus, GrantStatus
    if app.status == ApplicationStatus.SUBMITTED:
        app.status = ApplicationStatus.UNDER_REVIEW

    db.commit()

    # Auto-finalize kontrollon nëse të gjitha aplikimet janë vlerësuar
    _check_auto_finalize(grant, app, db)

    return score_row


def _check_auto_finalize(grant, scored_app, db: Session) -> None:

    try:
        from datetime import datetime, timezone
        from app.models.tenant.models import ApplicationStatus, GrantStatus, Application

        if not grant:
            return

        now = datetime.now(timezone.utc)
        deadline_passed = grant.deadline is not None and grant.deadline < now
        is_closed       = grant.status == GrantStatus.CLOSED

        if not (deadline_passed or is_closed):
            return  # Deadline nuk ka kaluar ende

        # Funksioni merr të gjitha aplikimet aktive
        active_apps = db.query(Application).filter(
            Application.grant_id == grant.id,
            Application.status.in_([ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW])
        ).all()

        if not active_apps:
            return

        # Funksioni kontrollon nëse të gjitha kanë commissioner_score
        all_scored = all(
            db.query(AIScore).filter(
                AIScore.application_id == a.id,
                AIScore.commissioner_score.isnot(None)
            ).first() is not None
            for a in active_apps
        )

        if not all_scored:
            return

        from app.services.grants import finalize_grant
        system_user = {"user_id": str(scored_app.user_id), "tenant_id": None}
        finalize_grant(str(grant.id), system_user, db)
        print(f"[auto-finalize] Grant {grant.id} u finalizua automatikisht.")

    except Exception as e:
        print(f"[auto-finalize] dështoi: {e}")


def get_score(application_id: str, db: Session) -> AIScore | None:
    import uuid
    try:
        aid = uuid.UUID(application_id)
    except ValueError:
        return None
    return db.query(AIScore).filter(AIScore.application_id == aid).first()


def _heuristic_score(app, answers, criteria) -> tuple[float, str]:
    import random
    score = 40.0

    if app.motivation_letter:
        score += min(25, len(app.motivation_letter.strip()) / 40)

    answered = sum(1 for a in answers if a.answer_text and a.answer_text.strip())
    if answers:
        score += (answered / len(answers)) * 25

    required = sum(1 for c in criteria if c.is_required)
    if required > 0:
        score += min(10, 10 * (answered / max(required, 1)))

    score = round(min(100, max(0, score + random.uniform(-3, 3))), 2)

    parts = []
    if app.motivation_letter and len(app.motivation_letter) > 200:
        parts.append("Letra motivuese eshte e detajuar")
    elif app.motivation_letter:
        parts.append("Letra motivuese eshte e shkurter")
    else:
        parts.append("Mungon letra motivuese")

    if answers:
        parts.append(f"{answered}/{len(answers)} pyetje te pergjigjetura")

    justification = ". ".join(parts) + f". Score bazuar ne analize heuristike ({score:.0f}/100)."
    return score, justification


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
