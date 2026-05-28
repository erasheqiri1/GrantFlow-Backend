from app.core.celery_app import celery_app


@celery_app.task(name="score_application_ai", bind=True, max_retries=3)
def score_application_task(self, application_id: str, schema_name: str) -> dict:
    """
    Celery background task — thirr OpenAI/Groq dhe ruaj score në ai_scores.
    Retry deri 3 herë me interval në rritje (30s, 60s, 120s).
    Nëse të gjitha tentativat dështojnë, ruhet model_used='unavailable'
    dhe commissioner nuk mund të shtojë score derisa AI të jetë aktiv.
    """
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.services.ai_scoring import score_application

    db = SessionLocal()
    try:
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        result = score_application(application_id, db)
        return {
            "status": "completed" if result.model_used != "unavailable" else "unavailable",
            "application_id": application_id,
            "ai_score": float(result.ai_score) if result.ai_score is not None else None,
            "final_score": float(result.final_score) if result.final_score is not None else None,
            "model_used": result.model_used,
        }
    except Exception as exc:
        db.close()
        # Retry me interval në rritje: 30s → 60s → 120s
        retry_count  = self.request.retries
        countdown    = 30 * (2 ** retry_count)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
