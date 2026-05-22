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
    """
    Lazy init — lexon settings në momentin e thirrjes,
    kështu GROQ_API_KEY nga .env është gjithmonë i disponueshëm.
    Prioritet: OpenAI → Groq → heuristic fallback.
    Kthehet (client, model_name).
    """
    from app.core.config import settings
    if settings.OPENAI_API_KEY:
        return OpenAI(api_key=settings.OPENAI_API_KEY), "gpt-4o-mini"
    if settings.GROQ_API_KEY:
        return OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        ), "llama-3.1-8b-instant"
    return None, "heuristic-fallback"


def score_application(application_id: str, db: Session) -> AIScore:
    """
    Vlerëson një aplikim me AI dhe ruan rezultatin në tabelën ai_scores.
    Nëse aplikimi është vlerësuar tashmë, kthen rezultatin e ruajtur (cache).
    """
    import uuid
    try:
        aid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="ID e pavlefshme")

    # Kontrollo cache
    existing = db.query(AIScore).filter(AIScore.application_id == aid).first()
    if existing and existing.ai_score is not None:
        existing.is_cached = True
        return existing

    # Merr aplikimin
    app = db.query(Application).filter(Application.id == aid).first()
    if not app:
        raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")

    # Merr grantin dhe kriteret
    grant    = db.query(Grant).filter(Grant.id == app.grant_id).first()
    criteria = db.query(Criteria).filter(Criteria.grant_id == app.grant_id).all()
    answers  = db.query(ApplicationAnswer).filter(ApplicationAnswer.application_id == aid).all()

    # Lazy-init client (lexon .env nëpërmjet settings)
    client, model_name = _get_client()

    ai_score_val  = 0.0
    justification = ""

    if client is not None:
        try:
            prompt   = _build_prompt(app, grant, criteria, answers)
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
    ai_weight   = float(grant.ai_weight) if grant and grant.ai_weight else 0.6
    final_score = round(ai_score_val * ai_weight, 2)

    # Ruaj ose përditëso
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
    """
    Komisioner jep pikët e tij (0-100).
    Rillogarit final_score = (ai_score × ai_weight) + (commissioner_score × (1 - ai_weight)).
    Nëse nuk ka ai_score akoma, final_score = commissioner_score × (1 - ai_weight).
    """
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

    # Kalo aplikimin në UNDER_REVIEW — komisioner e ka shqyrtuar
    from app.models.tenant.models import ApplicationStatus
    if app.status == ApplicationStatus.SUBMITTED:
        app.status = ApplicationStatus.UNDER_REVIEW

    db.commit()
    return score_row


def get_score(application_id: str, db: Session) -> AIScore | None:
    """Merr rezultatin ekzistues pa e rillogaritur."""
    import uuid
    try:
        aid = uuid.UUID(application_id)
    except ValueError:
        return None
    return db.query(AIScore).filter(AIScore.application_id == aid).first()


def _heuristic_score(app, answers, criteria) -> tuple[float, str]:
    """Score lokal kur AI nuk është i disponueshëm."""
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


def _build_prompt(app, grant, criteria, answers) -> str:
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

    lines.append("\nJep nje vleresim te drejte 0-100 dhe arsyetim te shkurter ne shqip.")
    return "\n".join(lines)
