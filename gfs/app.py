import asyncio
import contextlib
import io
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, BufferedInputFile, MenuButtonWebApp
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from .db import Database
from .domain import validate_init_data, normalize_unit, report, next_weekly, audit_details
from .monday import Monday
from .pdf import parse_pdf
from .scheduler import scheduler, refresh_groups, send

load_dotenv()
log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
KINDS = {"text", "photo", "video", "document", "sticker", "animation", "audio", "voice", "video_note", "copy"}


class Broadcast(BaseModel):
    text: str = ""
    kind: str = "text"
    file_id: str | None = None
    parse_mode: str | None = None
    buttons: list[list[dict[str, str]]] = Field(default_factory=list)
    due: float | None = None
    weekly: dict | None = None
    recipients: list[int] | None = None
    source_chat: int | None = None
    source_message: int | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.recipients is not None:
            self.recipients = list(dict.fromkeys(self.recipients))
            if not self.recipients or len(self.recipients) > 10000:
                raise ValueError("Kamida bitta guruh tanlang")
        if self.kind not in KINDS or self.parse_mode not in (None, "HTML", "MarkdownV2"):
            raise ValueError("Xabar turi yoki format noto'g'ri")
        if self.kind == "text" and not 1 <= len(self.text) <= 4096:
            raise ValueError("Matn 1–4096 belgi bo'lsin")
        if self.kind not in ("text", "copy") and not self.file_id:
            raise ValueError("Media kerak")
        if self.kind not in ("text", "copy") and len(self.text) > 1024:
            raise ValueError("Media izohi 1024 belgidan oshmasin")
        if self.kind == "copy" and not (self.source_chat and self.source_message):
            raise ValueError("Manba xabarni tanlang")
        if len(self.buttons) > 10:
            raise ValueError("Ko'pi bilan 10 qator tugma")
        for row in self.buttons:
            if not 1 <= len(row) <= 8:
                raise ValueError("Qatorda 1–8 tugma bo'lsin")
            for button in row:
                if set(button) not in ({"text", "url"}, {"text", "callback_data"}) or not button.get("text"):
                    raise ValueError("Tugma: text va url yoki callback_data")
                if "url" in button and not button["url"].startswith(("https://", "http://", "tg://")):
                    raise ValueError("Tugma URL noto'g'ri")
                if "callback_data" in button and not 1 <= len(button["callback_data"].encode()) <= 64:
                    raise ValueError("callback_data 1–64 bayt bo'lsin")
        if self.due is not None and not time.time() - 60 <= self.due <= time.time() + 366 * 86400:
            raise ValueError("Vaqt kelgusi bir yil ichida bo'lsin")
        if self.weekly:
            w = self.weekly
            if not (isinstance(w.get("weekday"), int) and 0 <= w["weekday"] <= 6 and isinstance(w.get("hour"), int) and 0 <= w["hour"] <= 23 and isinstance(w.get("minute"), int) and 0 <= w["minute"] <= 59):
                raise ValueError("Haftalik vaqt noto'g'ri")
            try:
                ZoneInfo(w.get("timezone", ""))
            except (ValueError, ZoneInfoNotFoundError):
                raise ValueError("Vaqt zonasi noto'g'ri")
        return self


def create_app():
    db = Database(os.getenv("DB_PATH", "data/gfs.sqlite3"))
    for uid in os.getenv("ADMIN_IDS", "").split(","):
        if uid.strip():
            db.execute("INSERT OR IGNORE INTO admins VALUES(?)", (int(uid),))
    token = os.getenv("BOT_TOKEN", "")
    monday = Monday(os.getenv("MONDAY_TOKEN", ""), os.getenv("MONDAY_BOARD_ID", ""), os.getenv("MONDAY_API_VERSION", "2026-10"))
    dp = Dispatcher()
    bot = None

    @asynccontextmanager
    async def lifespan(app):
        nonlocal bot
        if not token:
            raise RuntimeError("BOT_TOKEN ni .env fayliga kiriting")
        if not db.rows("SELECT id FROM admins"):
            raise RuntimeError("ADMIN_IDS ga kamida bitta Telegram ID kiriting")
        bot = Bot(token)
        webapp_url = os.getenv("WEBAPP_URL", "")
        if webapp_url.startswith("https://"):
            for admin in db.rows("SELECT id FROM admins"):
                try:
                    await bot.set_chat_menu_button(chat_id=admin["id"], menu_button=MenuButtonWebApp(
                        text="Mini App", web_app=WebAppInfo(url=webapp_url)))
                except Exception:
                    log.warning("Could not set Mini App menu for an admin")
        tasks = [asyncio.create_task(dp.start_polling(bot, handle_signals=False)), asyncio.create_task(scheduler(bot, db))]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await bot.session.close()
            db.conn.close()

    app = FastAPI(title="GFS Speaker", lifespan=lifespan)

    async def auth(authorization: str = Header(default="")):
        try:
            uid = validate_init_data(authorization.removeprefix("tma "), token)
            if not db.is_admin(uid):
                raise ValueError("Access denied")
            return uid
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            raise HTTPException(403, "Telegram orqali oching. Kirish ruxsati yoki sessiya muddati tugagan.")

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "web" / "index.html")

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/api/state")
    async def state(uid=Depends(auth)):
        return {"groups": db.groups(), "jobs": db.jobs(), "timezone": os.getenv("TIMEZONE", "Asia/Tashkent")}

    @app.get("/api/admins")
    async def admins(uid=Depends(auth)):
        return db.rows("SELECT a.id,u.username FROM admins a LEFT JOIN users u ON u.id=a.id ORDER BY a.id")

    class AdminInput(BaseModel):
        user_id: int = Field(gt=0)

    @app.post("/api/admins")
    async def create_admin(data: AdminInput, uid=Depends(auth)):
        db.execute("INSERT OR IGNORE INTO admins VALUES(?)", (data.user_id,))
        return {"id": data.user_id}

    @app.get("/api/audits")
    async def audits(uid=Depends(auth)):
        return db.rows("SELECT * FROM audits ORDER BY id DESC LIMIT 100")

    @app.post("/api/sync")
    async def sync(uid=Depends(auth)):
        try:
            trucks = await monday.trucks()
            failures = await refresh_groups(bot, db)
            db.remap(trucks)
            return {"trucks": trucks, "refresh_failures": failures}
        except Exception as exc:
            log.exception("Sync failed")
            raise HTTPException(502, str(exc))

    class Binding(BaseModel):
        unit: str | None = None

    @app.put("/api/groups/{chat_id}")
    async def bind(chat_id: int, binding: Binding, uid=Depends(auth)):
        if not db.rows("SELECT id FROM groups WHERE id=?", (chat_id,)):
            raise HTTPException(404, "Guruh topilmadi")
        unit = normalize_unit(binding.unit) if binding.unit else None
        if unit:
            try:
                trucks = await monday.trucks()
            except Exception as exc:
                raise HTTPException(502, str(exc))
            if unit not in {t["unit"] for t in trucks}:
                raise HTTPException(400, "Unit maqsadli Monday guruhlarida topilmadi")
        db.execute("UPDATE groups SET manual_unit=? WHERE id=?", (unit, chat_id))
        return {"ok": True}

    @app.post("/api/media")
    async def upload(kind: str, file: UploadFile = File(...), uid=Depends(auth)):
        if kind not in KINDS - {"text", "copy"}:
            raise HTTPException(400, "Media turi noto'g'ri")
        content = await file.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(413, "Media 20 MB dan oshmasin")
        try:
            message = await getattr(bot, f"send_{kind}")(uid, **{kind: BufferedInputFile(content, filename=file.filename or "media")})
        except Exception as exc:
            raise HTTPException(400, str(exc))
        media = getattr(message, kind)
        file_id = media[-1].file_id if kind == "photo" else media.file_id
        db.execute("INSERT OR REPLACE INTO media VALUES(?,?,?)", (file_id, uid, kind))
        return {"file_id": file_id}

    def check_source(payload, uid):
        if payload.recipients is not None:
            known = {g["id"] for g in db.groups() if g["present"]}
            if not set(payload.recipients) <= known:
                raise HTTPException(400, "Tanlangan guruh mavjud emas")
        if payload.kind == "copy" and payload.source_chat != uid:
            raise HTTPException(400, "Faqat bot bilan o'z shaxsiy chatingizdan nusxalang")
        if payload.file_id and not db.rows("SELECT id FROM media WHERE id=? AND owner=? AND kind=?", (payload.file_id, uid, payload.kind)):
            raise HTTPException(400, "Avval media faylni yuklang yoki botga yuboring")

    @app.post("/api/preview")
    async def preview(payload: Broadcast, uid=Depends(auth)):
        check_source(payload, uid)
        try:
            await send(bot, uid, payload.model_dump())
        except Exception as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True}

    def schedule_payload(payload):
        if payload.weekly:
            w = payload.weekly
            return next_weekly(datetime.now(timezone.utc), w["weekday"], w["hour"], w["minute"], ZoneInfo(w["timezone"]))
        return payload.due or time.time()

    @app.post("/api/jobs")
    async def add_job(payload: Broadcast, uid=Depends(auth)):
        check_source(payload, uid)
        cursor = db.execute("INSERT INTO jobs(owner,payload,due) VALUES(?,?,?)", (uid, payload.model_dump_json(), schedule_payload(payload)))
        return {"id": cursor.lastrowid}

    @app.put("/api/jobs/{job_id}")
    async def edit_job(job_id: int, payload: Broadcast, uid=Depends(auth)):
        check_source(payload, uid)
        cur = db.execute("UPDATE jobs SET payload=?,due=? WHERE id=? AND state='pending'", (payload.model_dump_json(), schedule_payload(payload), job_id))
        if not cur.rowcount:
            raise HTTPException(409, "Faqat kutilayotgan vazifa tahrirlanadi")
        return {"ok": True}

    @app.delete("/api/jobs/{job_id}")
    async def cancel_job(job_id: int, uid=Depends(auth)):
        cur = db.execute("UPDATE jobs SET state='cancelled' WHERE id=? AND state IN ('pending','running')", (job_id,))
        if not cur.rowcount:
            raise HTTPException(409, "Faol vazifa topilmadi")
        return {"ok": True}

    async def known_user(message):
        if message.from_user:
            db.execute("INSERT INTO users VALUES(?,?) ON CONFLICT(id) DO UPDATE SET username=excluded.username", (message.from_user.id, (message.from_user.username or "").lower()))
        return message.chat.type == "private" and message.from_user and db.is_admin(message.from_user.id)

    async def text_chunks(message, text):
        for i in range(0, len(text), 3900):
            await message.answer(text[i:i + 3900])

    @dp.my_chat_member()
    async def membership(event):
        if event.chat.type not in ("group", "supergroup"):
            return
        present = event.new_chat_member.status not in ("left", "kicked")
        if present:
            db.save_group(await bot.get_chat(event.chat.id))
        else:
            db.execute("UPDATE groups SET present=0 WHERE id=?", (event.chat.id,))

    @dp.message(F.chat.type.in_({"group", "supergroup"}))
    async def group_event(message: Message):
        if message.migrate_to_chat_id:
            old = db.rows("SELECT * FROM groups WHERE id=?", (message.chat.id,))
            db.execute("UPDATE groups SET present=0 WHERE id=?", (message.chat.id,))
            db.save_group(await bot.get_chat(message.migrate_to_chat_id))
            if old:
                db.execute("UPDATE groups SET manual_unit=? WHERE id=?", (old[0]["manual_unit"], message.migrate_to_chat_id))
            return
        db.save_group(await bot.get_chat(message.chat.id))

    @dp.message(Command("start", "help"))
    async def start(message: Message):
        if not await known_user(message):
            return
        url = os.getenv("WEBAPP_URL", "")
        if url.startswith("https://"):
            await bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=MenuButtonWebApp(
                text="Mini App", web_app=WebAppInfo(url=url)))
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="GFS Speaker", web_app=WebAppInfo(url=url))]]) if url.startswith("https://") else None
        await message.answer("GFS Speaker\nCOI PDF yuboring yoki /check_coi ni PDFga reply qiling.\n/sync — Monday va guruhlar\n/groups — guruhlar\n/add_admin ID yoki @username\nMedia/stiker yuboring: tarqatma uchun file_id olinadi.\nIstalgan xabarni /source bilan reply qiling: nusxa yuborish manbasi.", reply_markup=markup)

    @dp.message(Command("add_admin"))
    async def add_admin(message: Message):
        if not await known_user(message):
            return
        arg = (message.text or "").split(maxsplit=1)
        if len(arg) < 2:
            await message.answer("/add_admin 123456789 yoki @username")
            return
        value = arg[1].strip()
        if value.startswith("@"):
            users = db.rows("SELECT id FROM users WHERE username=?", (value[1:].lower(),))
            if len(users) != 1:
                await message.answer("Username aniqlanmadi. Foydalanuvchi avval /start yuborsin yoki raqamli Telegram User ID kiriting.")
                return
            uid = users[0]["id"]
        elif value.isdigit() and int(value) > 0:
            uid = int(value)
        else:
            await message.answer("Musbat Telegram User ID yoki @username kiriting.")
            return
        db.execute("INSERT OR IGNORE INTO admins VALUES(?)", (uid,))
        await message.answer(f"Administrator qo'shildi: {uid}")

    @dp.message(Command("sync", "groups"))
    async def sync_command(message: Message):
        if not await known_user(message):
            return
        try:
            trucks = await monday.trucks()
            failures = await refresh_groups(bot, db)
            db.remap(trucks)
            lines = [f"Monday: {len(trucks)} yozuv. Yangilanmagan chatlar: {len(failures)}."]
            for g in db.groups():
                if not g["present"]:
                    continue
                lines.append(f'{g["title"]} → {g["manual_unit"] or g["unit"] or "KONFLIKT"}')
            await text_chunks(message, "\n".join(lines))
        except Exception as exc:
            log.exception("Sync command failed")
            await message.answer(f"Sinxronlash xatosi: {exc}")

    async def check_coi(message, document):
        if (document.file_size or 0) > 20 * 1024 * 1024:
            await message.answer("PDF 20 MB dan oshmasin")
            return
        audit_id = db.execute("INSERT INTO audits(owner,created,filename,state) VALUES(?,?,?,'processing')",
                              (message.from_user.id,time.time(),document.file_name)).lastrowid
        await message.answer("COI tekshirilmoqda…")
        try:
            content = io.BytesIO()
            await bot.download(document.file_id, destination=content)
            vins = await asyncio.to_thread(parse_pdf, content.getvalue(), os.getenv("OCR_ENABLED", "false").lower() == "true")
            trucks = await monday.trucks()
            failures = await refresh_groups(bot, db)
            if failures:
                raise ValueError(f"{len(failures)} guruh holatini yangilab bo'lmadi. Auditni keyin qayta bajaring.")
            db.remap(trucks)
            result = report(vins, trucks, db.groups())
            details = audit_details(vins, trucks, db.groups())
            db.execute("UPDATE audits SET state='done',result=?,details=? WHERE id=?",
                       (result,json.dumps(details),audit_id))
            await text_chunks(message, result)
        except Exception as exc:
            db.execute("UPDATE audits SET state='failed',error=? WHERE id=?", (str(exc),audit_id))
            log.exception("COI check failed")
            await message.answer(f"COI tekshiruvi bajarilmadi: {exc}")

    @dp.message(Command("check_coi"))
    async def coi_command(message: Message):
        if not await known_user(message):
            return
        document = message.reply_to_message.document if message.reply_to_message else None
        if not document:
            await message.answer("PDF faylga reply qilib /check_coi yuboring")
            return
        await check_coi(message, document)

    @dp.message(Command("source"))
    async def source(message: Message):
        if not await known_user(message):
            return
        if message.reply_to_message:
            await message.answer(f"Mini App: source_chat={message.chat.id}, source_message={message.reply_to_message.message_id}")
        else:
            await message.answer("Manba xabarga reply qiling: /source")

    @dp.message()
    async def private_message(message: Message):
        if not await known_user(message):
            return
        if message.document and (message.document.file_name or "").lower().endswith(".pdf"):
            await check_coi(message, message.document)
        for kind in KINDS - {"text", "copy"}:
            media = getattr(message, kind, None)
            if media:
                file_id = media[-1].file_id if kind == "photo" else media.file_id
                db.execute("INSERT OR REPLACE INTO media VALUES(?,?,?)", (file_id, message.from_user.id, kind))
                await message.answer(f"Media turi: {kind}\nfile_id: {file_id}")
                break

    @dp.callback_query()
    async def callback(query):
        # Callback buttons may be used by drivers; no privileged action is attached.
        await query.answer("Qabul qilindi")

    return app
