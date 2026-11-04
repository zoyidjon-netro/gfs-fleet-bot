import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .domain import eligible, next_weekly

log = logging.getLogger(__name__)


async def refresh_groups(bot, db):
    failures = []
    for group in db.groups():
        if not group["present"]:
            continue
        try:
            chat = await bot.get_chat(group["id"])
            db.save_group(chat)
        except TelegramForbiddenError:
            db.execute("UPDATE groups SET present=0 WHERE id=?", (group["id"],))
        except Exception:
            failures.append(group["id"])
            log.exception("Group refresh failed: %s", group["id"])
    return failures


def keyboard(payload):
    rows = payload.get("buttons", [])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(**b) for b in row] for row in rows]) if rows else None


async def send(bot, chat_id, payload):
    kind = payload["kind"]
    markup = keyboard(payload)
    if kind == "copy":
        return await bot.copy_message(chat_id, payload["source_chat"], payload["source_message"], reply_markup=markup)
    if kind == "text":
        return await bot.send_message(chat_id, payload["text"], parse_mode=payload.get("parse_mode"), reply_markup=markup)
    kwargs = {kind: payload["file_id"], "reply_markup": markup}
    if kind not in ("sticker", "video_note"):
        kwargs.update(caption=payload.get("text") or None, parse_mode=payload.get("parse_mode"))
    return await getattr(bot, f"send_{kind}")(chat_id, **kwargs)


async def execute_job(bot, db, job):
    payload = json.loads(job["payload"])
    occurrence = job["due"]
    for group in db.groups():
        selected = payload.get("recipients")
        if selected is not None and group["id"] not in selected:
            continue
        if not group["present"]:
            continue
        previous = db.rows("SELECT state FROM deliveries WHERE job=? AND occurrence=? AND chat=?",
                           (job["id"], occurrence, group["id"]))
        if previous:  # 'sending' is uncertain after a crash; never blindly duplicate it.
            continue
        if db.rows("SELECT state FROM jobs WHERE id=?", (job["id"],))[0]["state"] == "cancelled":
            return
        state, error = "failed", None
        try:
            # Fresh title/photo immediately before every actual send. Fail closed on API errors.
            chat = await bot.get_chat(group["id"])
            db.save_group(chat)
            fresh_rows = db.rows("SELECT * FROM groups WHERE id=?", (group["id"],))
            fresh = fresh_rows[0] if fresh_rows else group
            group_active = (fresh.get("status") == "active") if fresh.get("status") else eligible(chat.title or "", bool(chat.photo))

            # If recipient was specifically selected by user, send it!
            # If broadcast had no selection (send to all), only deliver to active groups.
            if selected is None and (not group_active or not eligible(chat.title or "", bool(chat.photo))):
                state = "skipped"
            else:
                db.execute("INSERT INTO deliveries(job,occurrence,chat,state) VALUES(?,?,?,'sending')",
                           (job["id"], occurrence, group["id"]))
                for attempt in range(4):
                    try:
                        await send(bot, group["id"], payload)
                        state = "sent"
                        break
                    except TelegramRetryAfter as exc:
                        if attempt == 3:
                            raise
                        await asyncio.sleep(exc.retry_after + 1)
                    except TelegramBadRequest as exc:
                        if getattr(exc, "migrate_to_chat_id", None):
                            raise
                        raise
                await asyncio.sleep(0.06)
        except TelegramForbiddenError as exc:
            db.execute("UPDATE groups SET present=0 WHERE id=?", (group["id"],))
            error = str(exc)
        except Exception as exc:
            log.exception("Delivery failure: job=%s chat=%s", job["id"], group["id"])
            error = str(exc)
        db.execute('''INSERT INTO deliveries(job,occurrence,chat,state,error) VALUES(?,?,?,?,?)
          ON CONFLICT(job,occurrence,chat) DO UPDATE SET state=excluded.state,error=excluded.error''',
          (job["id"], occurrence, group["id"], state, error))
    repeat = payload.get("weekly")
    if repeat:
        due = next_weekly(datetime.now(timezone.utc), repeat["weekday"], repeat["hour"], repeat["minute"], ZoneInfo(repeat["timezone"]))
        db.execute("UPDATE jobs SET due=?,state='pending' WHERE id=? AND state='running'", (due, job["id"]))
    else:
        db.execute("UPDATE jobs SET state='done' WHERE id=? AND state='running'", (job["id"],))


async def scheduler(bot, db):
    db.execute("UPDATE jobs SET state='pending' WHERE state='running'")
    while True:
        try:
            for job in db.rows("SELECT * FROM jobs WHERE state='pending' AND due<=? ORDER BY due", (time.time(),)):
                claim = db.execute("UPDATE jobs SET state='running',last_error=NULL WHERE id=? AND state='pending'", (job["id"],))
                if claim.rowcount:
                    try:
                        await execute_job(bot, db, job)
                    except Exception as exc:
                        log.exception("Job failed: %s", job["id"])
                        db.execute("UPDATE jobs SET state='failed',last_error=? WHERE id=? AND state='running'", (str(exc), job["id"]))
        except Exception:
            log.exception("Scheduler iteration failed")
        await asyncio.sleep(2)
