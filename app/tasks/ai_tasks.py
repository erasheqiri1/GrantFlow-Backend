from app.core.celery_app import celery_app


@celery_app.task(name="score_application_ai", bind=True, max_retries=2)
def score_application_task(self, application_id: str, schema_name: str) -> dict:
    """
    Celery background task — thirr OpenAI/Groq dhe ruaj score në ai_scores.
    Kthehet automatikisht deri 2 herë nëse dështon.
    """
    try:
        from sqlalchemy import text
        from app.core.database import SessionLocal
        from app.services.ai_scoring import score_application

        db = SessionLocal()
        try:
            db.execute(text(f'SET search_path TO "{schema_name}", public'))
            result = score_application(application_id, db)
            return {
                "status": "completed",
                "application_id": application_id,
                "ai_score": float(result.ai_score) if result.ai_score else None,
                "final_score": float(result.final_score) if result.final_score else None,
                "model_used": result.model_used,
            }
        finally:
            db.close()

    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)
