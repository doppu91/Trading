"""APScheduler jobs — regime refresh, morning brief, EOD summary, token refresh."""
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


async def job_weekly_walkforward():
    """Sunday 20:00 IST — self-monitoring strategy-drift check.
    Runs 90-day walk-forward on real Upstox candles and posts results to Telegram.
    """
    try:
        from . import walk_forward as wf
        result = await wf.run_walk_forward(days=90, interval="day")
        if "error" in result:
            await telegram_bot.send_message(
                f"⚠️ <b>Weekly walk-forward FAILED</b>\n{result['error']}"
            )
            return
        await wf.save_result(result)
        text = (
            f"<b>📈 WEEKLY STRATEGY HEALTH — 90d walk-forward</b>\n"
            f"Trades: {result['total_trades']}  Win: {result['win_rate']}%\n"
            f"Gross: ₹{result['gross_pnl']:,.0f}  Charges: -₹{result['total_charges']:,.0f}\n"
            f"<b>Net: ₹{result['net_pnl']:,.0f}</b>  Sharpe {result['sharpe']}\n"
            f"Avg/day: ₹{result['avg_net_per_day']:,.0f}  Target hit: {result['target_hit_rate']}%\n"
            f"Max DD: ₹{result['max_drawdown']:,.0f}"
        )
        await telegram_bot.send_message(text)
    except Exception as e:
        logger.error(f"weekly walk-forward err: {e}")
        try:
            await telegram_bot.send_message(f"⚠️ Weekly walk-forward exception: {e}")
        except Exception:
            pass


async def job_token_refresh():
    try:
        from . import upstox_auth as ua
        result = await ua.auto_login()
        if result.get("ok"):
            await telegram_bot.send_message(
                f"🔓 <b>Daily token refresh OK</b>\n{result.get('token_refreshed_at')}"
            )
        else:
            await telegram_bot.send_message(
                f"⚠️ <b>Token refresh FAILED</b>\n{result.get('error')}\nManual re-auth required."
            )
    except Exception as e:
        logger.error(f"token_refresh err: {e}")
        try:
            await telegram_bot.send_message(f"⚠️ Token refresh exception: {e}")
        except Exception:
            pass


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    sched = AsyncIOScheduler(timezone="Asia/Kolkata")
    sched.add_job(job_token_refresh, CronTrigger(hour=8, minute=0, day_of_week="mon-fri"), id="token_refresh")
    sched.add_job(job_morning_brief, CronTrigger(hour=8, minute=59, day_of_week="mon-fri"), id="morning_brief")
    sched.add_job(job_eod_summary, CronTrigger(hour=15, minute=30, day_of_week="mon-fri"), id="eod_summary")
    sched.add_job(job_weekly_walkforward, CronTrigger(hour=20, minute=0, day_of_week="sun"), id="weekly_walkforward")
    sched.start()
    _scheduler = sched
    logger.info("Scheduler started (IST) — token 08:00, brief 08:59, EOD 15:30, weekly-walkforward Sun 20:00")
    return sched


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
