import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.services.notification_service import run_meal_agent_tick, run_water_agent_tick

logger = logging.getLogger("app.scheduler")

scheduler = BackgroundScheduler()


def _run_agents_tick() -> None:
    db = SessionLocal()
    try:
        run_water_agent_tick(db)
    except Exception:
        logger.exception("Water agent tick failed")
    try:
        run_meal_agent_tick(db)
    except Exception:
        logger.exception("Meal agent tick failed")
    finally:
        db.close()


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.add_job(_run_agents_tick, "interval", minutes=1, id="agents_tick")
        scheduler.start()
        logger.info("Notification agent scheduler started (1-minute tick)")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
