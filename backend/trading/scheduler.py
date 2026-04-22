"""APScheduler jobs — regime refresh, morning brief, EOD summary."""
from __future__ import annotations
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from . import regime, signals, market_data, paper_trader, telegram_bot
from .config import TARGET_GROSS_DAILY, WATCHLIST

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def job_morning_brief():
    try:
        reg = regime.get_current_regime()
        cues = market_data.get_global_cues()
        sigs = [signals.get_signal_for_symbol(s, cues) for s in WATCHLIST]
        text = telegram_bot.morning_brief(reg, cues, sigs, TARGET_GROSS_DAILY)
        await telegram_bot.send_message(text)
    except Exception as e:
        logger.error(f"morning_brief err: {e}")


async def job_eod_summary():
    try:
        s = await paper_trader.today_summary()
        text = telegram_bot.eod_summary(s)
        await telegram_bot.send_message(text)
    except Exception as e:
        logger.error(f"eod_summary err: {e}")


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    sched = AsyncIOScheduler(timezone="Asia/Kolkata")
    sched.add_job(job_morning_brief, CronTrigger(hour=8, minute=59, day_of_week="mon-fri"), id="morning_brief")
    sched.add_job(job_eod_summary, CronTrigger(hour=15, minute=30, day_of_week="mon-fri"), id="eod_summary")
    sched.start()
    _scheduler = sched
    logger.info("Scheduler started (IST)")
    return sched


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
