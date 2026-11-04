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
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, BufferedInputFile, MenuButtonWebApp, ForceReply
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from .db import Database
from .domain import validate_init_data, normalize_unit, report, next_weekly, audit_details, eligible
from .i18n import t, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from .monday import Monday
from .pdf import parse_pdf
from .scheduler import scheduler, refresh_groups, send, execute_job

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
    schedule_time: str | None = None
    timezone: str | None = None
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
        if self.timezone:
            try:
                ZoneInfo(self.timezone)
            except (ValueError, ZoneInfoNotFoundError):
                raise ValueError("Vaqt zonasi noto'g'ri")
        if self.schedule_time:
            try:
                tz = ZoneInfo(self.timezone or "Asia/Tashkent")
                dt = datetime.fromisoformat(self.schedule_time)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=tz)
                self.due = dt.timestamp()
            except Exception:
                raise ValueError("Sana va vaqt formati noto'g'ri")
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
            db.execute("INSERT OR IGNORE INTO admins(id, role, created_at) VALUES(?, 'superadmin', ?)", (int(uid), time.time()))
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

        # Auto-resolve missing usernames and names from Telegram
        for admin in db.rows("SELECT a.id, a.name, u.username FROM admins a LEFT JOIN users u ON u.id=a.id WHERE u.username IS NULL OR u.username=''"):
            try:
                chat = await bot.get_chat(admin["id"])
                if chat.username:
                    db.execute("INSERT INTO users(id, username, lang) VALUES(?,?, 'uz') ON CONFLICT(id) DO UPDATE SET username=excluded.username", (admin["id"], chat.username.lower()))
                if chat.full_name and not admin.get("name"):
                    db.execute("UPDATE admins SET name=? WHERE id=?", (chat.full_name, admin["id"]))
            except Exception:
                pass
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
    app.state.dp = dp
    app.state.db = db

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
        return {"groups": db.groups(), "jobs": db.jobs(), "timezone": os.getenv("TIMEZONE", "Asia/Tashkent"), "lang": db.get_lang(uid)}

    class LangInput(BaseModel):
        lang: str

    @app.get("/api/user/lang")
    async def get_user_lang(uid=Depends(auth)):
        return {"lang": db.get_lang(uid)}

    @app.post("/api/user/lang")
    async def set_user_lang(data: LangInput, uid=Depends(auth)):
        db.set_lang(uid, data.lang)
        return {"lang": db.get_lang(uid), "ok": True}

    @app.get("/api/admins")
    async def admins(uid=Depends(auth)):
        return db.rows("SELECT a.id, a.name, a.role, a.created_at, u.username FROM admins a LEFT JOIN users u ON u.id=a.id ORDER BY a.id")

    class AdminInput(BaseModel):
        identifier: str | int | None = None
        user_id: int | None = None
        name: str | None = None
        role: str | None = "admin"

    class AdminUpdate(BaseModel):
        name: str | None = None
        role: str | None = None

    @app.post("/api/admins")
    async def create_admin(data: AdminInput, uid=Depends(auth)):
        role = (data.role or "admin").strip().lower()
        if role not in ("superadmin", "admin"):
            role = "admin"

        target_id = None
        if data.user_id and data.user_id > 0:
            target_id = data.user_id
        elif data.identifier is not None:
            raw = str(data.identifier).strip()
            if raw.isdigit() and int(raw) > 0:
                target_id = int(raw)
                if not db.rows("SELECT username FROM users WHERE id=? AND username!=''", (target_id,)):
                    if bot:
                        try:
                            chat = await bot.get_chat(target_id)
                            if chat.username:
                                db.execute("INSERT INTO users(id, username, lang) VALUES(?,?, 'uz') ON CONFLICT(id) DO UPDATE SET username=excluded.username", (target_id, chat.username.lower()))
                            if chat.full_name and not data.name:
                                data.name = chat.full_name
                        except Exception:
                            pass
            else:
                uname = raw.lstrip("@").lower()
                users = db.rows("SELECT id FROM users WHERE lower(username)=?", (uname,))
                if users:
                    target_id = users[0]["id"]
                else:
                    active_bot = bot
                    if active_bot:
                        try:
                            chat = await active_bot.get_chat(f"@{uname}")
                            target_id = chat.id
                            db.execute("INSERT INTO users(id, username, lang) VALUES(?,?, 'uz') ON CONFLICT(id) DO UPDATE SET username=excluded.username", (target_id, uname))
                        except Exception:
                            pass
                if not target_id:
                    raise HTTPException(404, f"@{uname} foydalanuvchisi topilmadi. Foydalanuvchi avval botga /start yuborgan bo'lishi yoki to'g'ri Telegram ID kiriting.")
        else:
            raise HTTPException(422, "Telegram ID yoki @username kiritilishi shart")

        now = time.time()
        db.execute(
            "INSERT INTO admins(id, name, role, created_at) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name=coalesce(excluded.name, admins.name), role=coalesce(excluded.role, admins.role)",
            (target_id, data.name, role, now)
        )
        return {"id": target_id, "name": data.name, "role": role, "created_at": now}

    @app.put("/api/admins/{admin_id}")
    async def update_admin(admin_id: int, data: AdminUpdate, uid=Depends(auth)):
        existing = db.rows("SELECT id FROM admins WHERE id=?", (admin_id,))
        if not existing:
            raise HTTPException(404, "Administrator topilmadi")
        role = (data.role or "").strip().lower() if data.role else None
        if role and role not in ("superadmin", "admin"):
            role = "admin"
        if data.name is not None and role is not None:
            db.execute("UPDATE admins SET name=?, role=? WHERE id=?", (data.name, role, admin_id))
        elif data.name is not None:
            db.execute("UPDATE admins SET name=? WHERE id=?", (data.name, admin_id))
        elif role is not None:
            db.execute("UPDATE admins SET role=? WHERE id=?", (role, admin_id))
        return {"id": admin_id, "ok": True}

    @app.delete("/api/admins/{admin_id}")
    async def delete_admin(admin_id: int, uid=Depends(auth)):
        admins_list = db.rows("SELECT id FROM admins")
        if len(admins_list) <= 1:
            raise HTTPException(400, "Oxirgi administratorni o'chirib bo'lmaydi")
        existing = db.rows("SELECT id FROM admins WHERE id=?", (admin_id,))
        if not existing:
            raise HTTPException(404, "Administrator topilmadi")
        db.execute("DELETE FROM admins WHERE id=?", (admin_id,))
        return {"ok": True, "id": admin_id}

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
        status: str | None = None

    class GroupStatusUpdate(BaseModel):
        status: str

    @app.put("/api/groups/{chat_id}/status")
    async def set_group_status_api(chat_id: int, data: GroupStatusUpdate, uid=Depends(auth)):
        st = data.status.strip().lower()
        if st not in ("active", "inactive"):
            raise HTTPException(400, "Status faqat 'active' yoki 'inactive' bo'lishi mumkin")
        cur = db.set_group_status(chat_id, st)
        if not cur.rowcount:
            raise HTTPException(404, "Guruh topilmadi")
        return {"ok": True, "chat_id": chat_id, "status": st}

    @app.put("/api/groups/{chat_id}")
    async def bind(chat_id: int, binding: Binding, uid=Depends(auth)):
        if not db.rows("SELECT id FROM groups WHERE id=?", (chat_id,)):
            raise HTTPException(404, "Guruh topilmadi")
        if binding.status:
            st = binding.status.strip().lower()
            if st not in ("active", "inactive"):
                raise HTTPException(400, "Status faqat 'active' yoki 'inactive' bo'lishi mumkin")
            db.set_group_status(chat_id, st)
        if binding.unit is not None:
            unit = normalize_unit(binding.unit) if binding.unit else None
            if unit:
                try:
                    trucks = await monday.trucks()
                except Exception as exc:
                    raise HTTPException(502, str(exc))
                if unit not in {t["unit"] for t in trucks}:
                    raise HTTPException(400, "Unit maqsadli Monday guruhlarida topilmadi")
            db.execute("UPDATE groups SET manual_unit=? WHERE id=?", (unit, chat_id))
        fresh = db.rows("SELECT status, manual_unit, unit FROM groups WHERE id=?", (chat_id,))[0]
        return {"ok": True, "chat_id": chat_id, "status": fresh.get("status", "active"), "manual_unit": fresh["manual_unit"]}

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
            tz_str = w.get("timezone") or payload.timezone or "Asia/Tashkent"
            return next_weekly(datetime.now(timezone.utc), w["weekday"], w["hour"], w["minute"], ZoneInfo(tz_str))
        if payload.due is not None:
            return payload.due
        if payload.schedule_time:
            tz = ZoneInfo(payload.timezone or "Asia/Tashkent")
            dt = datetime.fromisoformat(payload.schedule_time)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return dt.timestamp()
        return time.time()

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
            lang_code = (message.from_user.language_code or "uz")[:2].lower()
            default_lang = lang_code if lang_code in ("uz", "ru", "en") else "uz"
            existing = db.rows("SELECT lang FROM users WHERE id=?", (message.from_user.id,))
            user_lang = existing[0]["lang"] if (existing and existing[0].get("lang")) else default_lang
            db.execute(
                "INSERT INTO users(id, username, lang) VALUES(?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET username=excluded.username",
                (message.from_user.id, (message.from_user.username or "").lower(), user_lang)
            )
        return message.chat.type == "private" and message.from_user and db.is_admin(message.from_user.id)

    async def text_chunks(message, text, reply_markup=None):
        chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
        for idx, chunk in enumerate(chunks):
            markup = reply_markup if idx == len(chunks) - 1 else None
            await message.answer(chunk, reply_markup=markup)

    def build_main_text(lang="uz"):
        return t("main_title", lang)

    def build_main_markup(lang="uz"):
        webapp_url = os.getenv("WEBAPP_URL", "")
        rows = []
        if webapp_url.startswith("https://"):
            rows.append([InlineKeyboardButton(text=t("btn_webapp", lang), web_app=WebAppInfo(url=webapp_url))])
        rows.append([
            InlineKeyboardButton(text=t("btn_broadcast", lang), callback_data="adm:broadcast_info"),
            InlineKeyboardButton(text=t("btn_sync", lang), callback_data="adm:sync"),
        ])
        rows.append([
            InlineKeyboardButton(text=t("btn_audits", lang), callback_data="adm:audits"),
            InlineKeyboardButton(text=t("btn_jobs", lang), callback_data="adm:jobs"),
        ])
        rows.append([
            InlineKeyboardButton(text=t("btn_admins", lang), callback_data="adm:admins"),
            InlineKeyboardButton(text=t("btn_lang", lang), callback_data="adm:lang"),
        ])
        rows.append([
            InlineKeyboardButton(text=t("btn_help", lang), callback_data="adm:help"),
        ])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def build_lang_markup():
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="adm:lang:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="adm:lang:ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="adm:lang:en"),
            ],
            [InlineKeyboardButton(text="🔙 Bosh menyu / Главное / Main", callback_data="adm:main")]
        ])

    def build_groups_view(conflicts_only=False, filter_mode="all", lang="uz"):
        groups = db.groups()
        present_groups = [g for g in groups if g.get("present")]
        active_groups = [g for g in present_groups if (g.get("status") == "active" if g.get("status") else eligible(g.get("title", ""), bool(g.get("photo"))))]
        inactive_groups = [g for g in present_groups if g not in active_groups]
        conflicts = [g for g in present_groups if not (g.get("manual_unit") or g.get("unit"))]
        matched = len(present_groups) - len(conflicts)

        lines = [
            t("groups_title", lang) + "\n",
            f"📊 *Jami:* {len(groups)} ta (🟢 Faol: {len(active_groups)} | ⏸ Faol emas: {len(inactive_groups)})\n"
            f"🔗 *Bog'langan:* {matched} ta | ⚠️ *Konfliktlar:* {len(conflicts)} ta\n",
        ]

        if filter_mode == "conflicts" or conflicts_only:
            target_list = conflicts
            lines.append("⚠️ *Faqat konfliktli guruhlar:*\n")
            if not conflicts:
                lines.append("🎉 Barcha guruhlar muvaffaqiyatli bog'langan!")
        elif filter_mode == "active":
            target_list = active_groups
            lines.append("🟢 *Faqat faol (Active) guruhlar:*\n")
            if not active_groups:
                lines.append("Faol guruhlar mavjud emas.")
        elif filter_mode == "inactive":
            target_list = inactive_groups
            lines.append("⏸ *Faqat faol emas (Inactive) guruhlar:*\n")
            if not inactive_groups:
                lines.append("Faol emas guruhlar mavjud emas.")
        else:
            target_list = present_groups
            lines.append("👥 *Barcha guruhlar ro'yxati:*\n")
            if not present_groups:
                lines.append(t("groups_no_active", lang))

        for g in target_list[:20]:
            title = g.get("title") or "Nomsiz"
            unit = g.get("manual_unit") or g.get("unit")
            is_act = (g.get("status") == "active" if g.get("status") else eligible(g.get("title", ""), bool(g.get("photo"))))
            st_icon = "🟢" if is_act else "⏸"
            if unit:
                manual = " (manual)" if g.get("manual_unit") else ""
                lines.append(f"• {st_icon} `{title}` → Unit *{unit}*{manual}")
            else:
                lines.append(f"• {st_icon} ⚠️ `{title}` → *KONFLIKT*")

        if len(target_list) > 20:
            lines.append(t("groups_more", lang, count=len(target_list) - 20))

        rows = []
        webapp_url = os.getenv("WEBAPP_URL", "")
        if webapp_url.startswith("https://"):
            rows.append([InlineKeyboardButton(text=t("btn_manage_miniapp", lang), web_app=WebAppInfo(url=webapp_url))])

        rows.append([
            InlineKeyboardButton(text=f"🟢 Faol ({len(active_groups)})", callback_data="adm:groups:active"),
            InlineKeyboardButton(text=f"⏸ Faol emas ({len(inactive_groups)})", callback_data="adm:groups:inactive"),
        ])
        rows.append([
            InlineKeyboardButton(text="📋 Barchasi", callback_data="adm:groups:all"),
            InlineKeyboardButton(text=f"⚠️ Konflikt ({len(conflicts)})", callback_data="adm:groups:conflicts"),
        ])
        rows.append([
            InlineKeyboardButton(text=t("btn_sync", lang), callback_data="adm:sync"),
            InlineKeyboardButton(text=t("btn_main", lang), callback_data="adm:main"),
        ])
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)

    def build_audits_view(lang="uz"):
        audits = db.rows("SELECT * FROM audits ORDER BY id DESC LIMIT 5")
        if not audits:
            text = t("audits_empty", lang)
        else:
            tz_str = os.getenv("TIMEZONE", "Asia/Tashkent")
            try:
                tz = ZoneInfo(tz_str)
            except Exception:
                tz = timezone.utc
            lines = [t("audits_title", lang) + "\n"]
            for a in audits:
                try:
                    dt = datetime.fromtimestamp(a["created"], tz=timezone.utc).astimezone(tz).strftime("%d.%m.%Y %H:%M")
                except Exception:
                    dt = "-"
                st = a.get("state")
                icon = "✅" if st == "done" else ("⏳" if st == "processing" else "❌")
                fname = a.get("filename") or "PDF"
                lines.append(f"{icon} *Audit #{a['id']}* — `{fname}`\n🕒 {dt} | Holat: `{st}`\n")
            text = "\n".join(lines)

        rows = []
        webapp_url = os.getenv("WEBAPP_URL", "")
        if webapp_url.startswith("https://"):
            rows.append([InlineKeyboardButton(text=t("btn_webapp", lang), web_app=WebAppInfo(url=webapp_url))])
        rows.append([
            InlineKeyboardButton(text=t("btn_refresh", lang), callback_data="adm:audits"),
            InlineKeyboardButton(text=t("btn_main", lang), callback_data="adm:main")
        ])
        return text, InlineKeyboardMarkup(inline_keyboard=rows)

    def build_jobs_view(lang="uz"):
        jobs = db.jobs()
        active_jobs = [j for j in jobs if j.get("state") in ("pending", "running")]
        tz_str = os.getenv("TIMEZONE", "Asia/Tashkent")
        try:
            tz = ZoneInfo(tz_str)
        except Exception:
            tz = timezone.utc

        rows = []
        if not jobs:
            text = t("jobs_empty", lang)
        else:
            lines = [
                t("jobs_title", lang) + f" ({len(jobs)}):\n"
            ]
            for j in jobs[:6]:
                st = j.get("state")
                icon = "⏳" if st == "pending" else ("🚀" if st == "running" else ("✅" if st == "done" else "🚫"))
                try:
                    dt = datetime.fromtimestamp(j.get("due", 0), tz=timezone.utc).astimezone(tz).strftime("%d.%m.%Y %H:%M")
                except Exception:
                    dt = "-"
                kind = j.get("kind", "text")
                lines.append(f"{icon} *Vazifa #{j['id']}* — `{kind.upper()}`\n🕒 {dt} | Holat: `{st}`\n")
            text = "\n".join(lines)

            for aj in active_jobs[:3]:
                rows.append([InlineKeyboardButton(text=t("btn_cancel_job", lang, id=aj['id']), callback_data=f"adm:cancel:{aj['id']}")])

        webapp_url = os.getenv("WEBAPP_URL", "")
        if webapp_url.startswith("https://"):
            rows.append([InlineKeyboardButton(text=t("btn_new_broadcast", lang), web_app=WebAppInfo(url=webapp_url))])
        rows.append([
            InlineKeyboardButton(text=t("btn_refresh", lang), callback_data="adm:jobs"),
            InlineKeyboardButton(text=t("btn_main", lang), callback_data="adm:main")
        ])
        return text, InlineKeyboardMarkup(inline_keyboard=rows)

    def build_admins_view(lang="uz"):
        admins = db.rows("SELECT a.id, a.name, a.role, a.created_at, u.username FROM admins a LEFT JOIN users u ON u.id=a.id ORDER BY a.id")
        lines = [t("admins_title", lang, total=len(admins)) + "\n"]
        role_icons = {"superadmin": "👑", "admin": "👮‍♂️"}
        for a in admins:
            uname = f"@{a['username']}" if a.get("username") else f"`{a['id']}`"
            name_str = f" ({a['name']})" if a.get("name") else ""
            r = a.get("role") or "admin"
            icon = role_icons.get(r, "👤")
            id_info = f" — `{a['id']}`" if a.get("username") else ""
            lines.append(f"• {icon} *{uname}*{id_info}{name_str} `[{r}]`")
        lines.append(t("admins_guide", lang))

        rows = []
        webapp_url = os.getenv("WEBAPP_URL", "")
        if webapp_url.startswith("https://"):
            rows.append([InlineKeyboardButton(text=t("btn_manage_miniapp", lang), web_app=WebAppInfo(url=webapp_url))])

        rows.append([InlineKeyboardButton(text=t("btn_add_admin", lang), callback_data="adm:add_admin_prompt")])

        if len(admins) > 1:
            del_buttons = []
            for a in admins:
                label = f"@{a['username']}" if a.get("username") else (a.get("name") or f"#{a['id']}")
                if len(label) > 18:
                    label = label[:16] + "…"
                del_buttons.append(InlineKeyboardButton(text=f"🗑 {label}", callback_data=f"adm:del_admin_confirm:{a['id']}"))
            for i in range(0, len(del_buttons), 2):
                rows.append(del_buttons[i:i+2])

        rows.append([
            InlineKeyboardButton(text=t("btn_refresh", lang), callback_data="adm:admins"),
            InlineKeyboardButton(text=t("btn_main", lang), callback_data="adm:main")
        ])
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)

    def build_broadcast_info_view(lang="uz"):
        groups = db.groups()
        present = [g for g in groups if g.get("present")]
        eligible_groups = [g for g in present if eligible(g.get("title", ""), bool(g.get("photo")))]

        text = (
            t("broadcast_info_title", lang) + "\n\n" +
            t("broadcast_info_stats", lang, total=len(present), eligible=len(eligible_groups)) + "\n\n" +
            t("broadcast_info_desc", lang)
        )
        rows = []
        webapp_url = os.getenv("WEBAPP_URL", "")
        if webapp_url.startswith("https://"):
            rows.append([InlineKeyboardButton(text=t("btn_new_broadcast", lang), web_app=WebAppInfo(url=webapp_url))])
        rows.append([
            InlineKeyboardButton(text=t("btn_groups_status", lang), callback_data="adm:groups"),
            InlineKeyboardButton(text=t("btn_jobs_list", lang), callback_data="adm:jobs"),
        ])
        rows.append([InlineKeyboardButton(text=t("btn_main", lang), callback_data="adm:main")])
        return text, InlineKeyboardMarkup(inline_keyboard=rows)

    def build_help_view(lang="uz"):
        text = t("help_title", lang) + "\n\n" + t("help_desc", lang)
        rows = [
            [InlineKeyboardButton(text=t("btn_lang", lang), callback_data="adm:lang")],
            [InlineKeyboardButton(text=t("btn_main", lang), callback_data="adm:main")]
        ]
        return text, InlineKeyboardMarkup(inline_keyboard=rows)

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
        lang = db.get_lang(message.from_user.id)
        url = os.getenv("WEBAPP_URL", "")
        if url.startswith("https://"):
            with contextlib.suppress(Exception):
                await bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=MenuButtonWebApp(
                    text="Mini App", web_app=WebAppInfo(url=url)))
        await message.answer(build_main_text(lang), reply_markup=build_main_markup(lang), parse_mode="Markdown")

    @dp.message(Command("lang", "language", "til"))
    async def language_command(message: Message):
        if not await known_user(message):
            return
        lang = db.get_lang(message.from_user.id)
        await message.answer(t("lang_select_title", lang), reply_markup=build_lang_markup(), parse_mode="Markdown")

    @dp.message(Command("add_admin"))
    async def add_admin(message: Message):
        if not await known_user(message):
            return
        parts = (message.text or "").split(maxsplit=3)
        if len(parts) < 2:
            await message.answer(
                "ℹ️ *Admin qo'shish sintaksisi:*\n"
                "`/add_admin ID [ism] [rol]` yoki `/add_admin @username [ism] [rol]`\n\n"
                "Rollar: `admin`, `superadmin`\n"
                "Misol: `/add_admin 123456789 Jasur admin`",
                parse_mode="Markdown"
            )
            return
        value = parts[1].strip()
        name = parts[2].strip() if len(parts) > 2 else None
        role = parts[3].strip().lower() if len(parts) > 3 else "admin"
        if role not in ("superadmin", "admin"):
            role = "admin"

        if value.startswith("@"):
            users = db.rows("SELECT id FROM users WHERE username=?", (value[1:].lower(),))
            if len(users) != 1:
                await message.answer("Username aniqlanmadi. Foydalanuvchi avval botga /start yuborsin yoki raqamli Telegram User ID kiriting.")
                return
            uid = users[0]["id"]
        elif value.isdigit() and int(value) > 0:
            uid = int(value)
        else:
            await message.answer("Musbat Telegram User ID yoki @username kiriting.")
            return

        db.execute(
            "INSERT INTO admins(id, name, role, created_at) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name=coalesce(excluded.name, admins.name), role=coalesce(excluded.role, admins.role)",
            (uid, name, role, time.time())
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Adminlar ro'yxati", callback_data="adm:admins")],
            [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")]
        ])
        info = f"✅ Administrator qo'shildi: `{uid}`"
        if name:
            info += f" ({name})"
        info += f" | Rol: `{role}`"
        await message.answer(info, parse_mode="Markdown", reply_markup=markup)

    @dp.message(Command("del_admin", "remove_admin"))
    async def del_admin(message: Message):
        if not await known_user(message):
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("ℹ️ *Adminni o'chirish:*\n`/del_admin ID` yoki `/del_admin @username`", parse_mode="Markdown")
            return
        val = parts[1].strip()
        if val.startswith("@"):
            users = db.rows("SELECT id FROM users WHERE username=?", (val[1:].lower(),))
            if not users:
                await message.answer("Foydalanuvchi topilmadi.")
                return
            target_id = users[0]["id"]
        elif val.isdigit():
            target_id = int(val)
        else:
            await message.answer("Telegram User ID yoki @username kiriting.")
            return

        admins = db.rows("SELECT id FROM admins")
        if len(admins) <= 1:
            await message.answer("⚠️ Oxirgi administratorni o'chirib bo'lmaydi!")
            return
        if not any(a["id"] == target_id for a in admins):
            await message.answer(f"Administrator `#{target_id}` topilmadi.", parse_mode="Markdown")
            return

        db.execute("DELETE FROM admins WHERE id=?", (target_id,))
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Adminlar ro'yxati", callback_data="adm:admins")],
            [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")]
        ])
        await message.answer(f"✅ Administrator `#{target_id}` o'chirildi.", parse_mode="Markdown", reply_markup=markup)

    @dp.message(Command("edit_admin"))
    async def edit_admin(message: Message):
        if not await known_user(message):
            return
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("ℹ️ *Adminni tahrirlash:*\n`/edit_admin ID Yangi Ism`", parse_mode="Markdown")
            return
        val, new_name = parts[1].strip(), parts[2].strip()
        if not val.isdigit():
            await message.answer("Telegram User ID raqam bo'lishi kerak.")
            return
        target_id = int(val)
        if not db.rows("SELECT id FROM admins WHERE id=?", (target_id,)):
            await message.answer(f"Administrator `#{target_id}` topilmadi.", parse_mode="Markdown")
            return
        db.execute("UPDATE admins SET name=? WHERE id=?", (new_name, target_id))
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Adminlar ro'yxati", callback_data="adm:admins")],
            [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")]
        ])
        await message.answer(f"✅ Administrator `#{target_id}` ma'lumotlari yangilandi: *{new_name}*", parse_mode="Markdown", reply_markup=markup)

    @dp.message(Command("set_group_status"))
    async def set_group_status_cmd(message: Message):
        if not await known_user(message):
            return
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3:
            await message.answer(
                "ℹ️ *Guruh statusini o'zgartirish:*\n"
                "`/set_group_status CHAT_ID active` yoki `inactive`\n"
                "Misol: `/set_group_status -100123456789 active`",
                parse_mode="Markdown"
            )
            return
        chat_val, status_val = parts[1].strip(), parts[2].strip().lower()
        if status_val not in ("active", "inactive"):
            await message.answer("Status faqat `active` yoki `inactive` bo'lishi mumkin.")
            return
        try:
            cid = int(chat_val)
        except ValueError:
            await message.answer("To'g'ri raqamli Chat ID kiriting.")
            return
        cur = db.set_group_status(cid, status_val)
        if not cur.rowcount:
            await message.answer("Guruh topilmadi.")
            return
        st_text = "🟢 Faol (Active)" if status_val == "active" else "⏸ Faol emas (Inactive)"
        await message.answer(f"✅ Guruh `#{cid}` statusi o'zgartirildi: *{st_text}*", parse_mode="Markdown")

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
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📋 Guruhlar", callback_data="adm:groups"),
                    InlineKeyboardButton(text="🔄 Qayta sinxronlash", callback_data="adm:sync")
                ],
                [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")]
            ])
            await text_chunks(message, "\n".join(lines), reply_markup=markup)
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
            coi_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Guruhlar holati", callback_data="adm:groups")],
                [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")]
            ])
            await text_chunks(message, result, reply_markup=coi_markup)
        except Exception as exc:
            db.execute("UPDATE audits SET state='failed',error=? WHERE id=?", (str(exc),audit_id))
            log.exception("COI check failed")
            await message.answer(f"COI tekshiruvi bajarilmadi: {exc}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")]
            ]))

    @dp.message(Command("check_coi"))
    async def coi_command(message: Message):
        if not await known_user(message):
            return
        document = message.reply_to_message.document if message.reply_to_message else None
        if not document:
            await message.answer("PDF faylga reply qilib /check_coi yuboring")
            return
        await check_coi(message, document)

    @dp.message(Command("broadcast", "tarqatish"))
    async def broadcast_command(message: Message):
        if not await known_user(message):
            return
        arg = (message.text or "").split(maxsplit=1)
        if len(arg) < 2 or not arg[1].strip():
            await message.answer(
                "ℹ️ *Xabar tarqatish buyrug'i:*\n\n"
                "`/broadcast Xabar matni`\n\n"
                "• *Barcha guruhlarga* tezkor matn yuborish uchun xabarni kiriting.\n"
                "• *Guruhlarni tanlab* va *vaqt zonasi (Asia / USA)* bo'yicha rejalash uchun Mini App'dan foydalaning.",
                parse_mode="Markdown"
            )
            return
        text_to_send = arg[1].strip()
        groups = db.groups()
        eligible_groups = [g for g in groups if g.get("present") and eligible(g.get("title", ""), bool(g.get("photo")))]
        if not eligible_groups:
            await message.answer("⚠️ Botda xabar yuborish uchun faol guruhlar mavjud emas.")
            return

        cursor = db.execute("INSERT INTO jobs(owner,payload,due,state) VALUES(?,?,?,'pending')",
                            (message.from_user.id, json.dumps({"kind": "text", "text": text_to_send, "recipients": None}), time.time()))
        job_id = cursor.lastrowid
        confirm_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Ha, barchasiga yuborilsin ({len(eligible_groups)} ta)", callback_data=f"adm:send_now:{job_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"adm:cancel:{job_id}")]
        ])
        await message.answer(
            f"⚠️ *Tarqatmani tasdiqlang:*\n\n"
            f"📢 *Qabul qiluvchilar:* Barcha faol guruhlar ({len(eligible_groups)} ta)\n"
            f"📝 *Xabar matni:*\n{text_to_send}\n\n"
            "_Darhol yuborilsinmi?_",
            reply_markup=confirm_markup,
            parse_mode="Markdown"
        )

    @dp.message(Command("source"))
    async def source(message: Message):
        if not await known_user(message):
            return
        if message.reply_to_message:
            webapp_url = os.getenv("WEBAPP_URL", "")
            rows = []
            if webapp_url.startswith("https://"):
                rows.append([InlineKeyboardButton(text="📱 Mini Appda ochish", web_app=WebAppInfo(url=webapp_url))])
            rows.append([InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")])
            await message.answer(
                f"📋 *Manba xabar ma'lumotlari:*\n\n`source_chat`: `{message.chat.id}`\n`source_message`: `{message.reply_to_message.message_id}`\n\n_Mini App 'Nusxa' (copy) rejimida ushbu parametrlarni kiriting._",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
            )
        else:
            await message.answer("Manba xabarga reply qiling: /source")

    @dp.message()
    async def private_message(message: Message):
        if not await known_user(message):
            return

        if message.reply_to_message and "Yangi administrator qo'shish" in (message.reply_to_message.text or ""):
            text_val = (message.text or "").strip()
            parts = text_val.split(maxsplit=2)
            if not parts:
                await message.answer("⚠️ ID yoki @username kiritilmadi.")
                return
            target_val = parts[0]
            name = parts[1] if len(parts) > 1 else None
            role = parts[2].lower() if len(parts) > 2 else "admin"
            if role not in ("superadmin", "admin"):
                role = "admin"

            uid = None
            if target_val.isdigit() and int(target_val) > 0:
                uid = int(target_val)
            else:
                uname = target_val.lstrip("@").lower()
                users = db.rows("SELECT id FROM users WHERE lower(username)=?", (uname,))
                if users:
                    uid = users[0]["id"]
                else:
                    active_bot = bot or message.bot
                    try:
                        chat = await active_bot.get_chat(f"@{uname}")
                        uid = chat.id
                        db.execute("INSERT INTO users(id, username, lang) VALUES(?,?, 'uz') ON CONFLICT(id) DO UPDATE SET username=excluded.username", (uid, uname))
                    except Exception:
                        await message.answer(f"❌ `@{uname}` foydalanuvchisi topilmadi.\nFoydalanuvchi avval botga /start yuborgan bo'lishi yoki to'g'ri Telegram ID kiriting.", parse_mode="Markdown")
                        return

            db.execute(
                "INSERT INTO admins(id, name, role, created_at) VALUES(?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=coalesce(excluded.name, admins.name), role=coalesce(excluded.role, admins.role)",
                (uid, name, role, time.time())
            )
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👥 Adminlar ro'yxati", callback_data="adm:admins")],
                [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")]
            ])
            info = f"✅ Administrator muvaffaqiyatli qo'shildi: `{uid}`"
            if name:
                info += f" ({name})"
            info += f" | Rol: `{role}`"
            await message.answer(info, parse_mode="Markdown", reply_markup=markup)
            return
        if message.document and (message.document.file_name or "").lower().endswith(".pdf"):
            await check_coi(message, message.document)
        for kind in KINDS - {"text", "copy"}:
            media = getattr(message, kind, None)
            if media:
                file_id = media[-1].file_id if kind == "photo" else media.file_id
                db.execute("INSERT OR REPLACE INTO media VALUES(?,?,?)", (file_id, message.from_user.id, kind))
                webapp_url = os.getenv("WEBAPP_URL", "")
                rows = []
                if webapp_url.startswith("https://"):
                    rows.append([InlineKeyboardButton(text="📱 Mini Appda tarqatish", web_app=WebAppInfo(url=webapp_url))])
                rows.append([InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")])
                await message.answer(
                    f"📎 *Media saqlandi!*\n\n• Turi: `{kind}`\n• `file_id`: `{file_id}`\n\n_Bu file_id'dan Mini App orqali tarqatishda foydalanishingiz mumkin._",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                    parse_mode="Markdown"
                )
                break

    @dp.callback_query()
    async def callback(query):
        data = query.data or ""
        if data.startswith("adm:"):
            user_lang = db.get_lang(query.from_user.id) if query.from_user else "uz"
            if not query.from_user or not db.is_admin(query.from_user.id):
                await query.answer(t("no_permission", user_lang), show_alert=True)
                return

            lang = user_lang

            if data == "adm:lang":
                await query.answer()
                with contextlib.suppress(Exception):
                    await query.message.edit_text(t("lang_select_title", lang), reply_markup=build_lang_markup(), parse_mode="Markdown")
                return

            if data.startswith("adm:lang:"):
                chosen_lang = data.split(":")[-1]
                db.set_lang(query.from_user.id, chosen_lang)
                await query.answer(t("lang_changed", chosen_lang), show_alert=True)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(build_main_text(chosen_lang), reply_markup=build_main_markup(chosen_lang), parse_mode="Markdown")
                return

            if data == "adm:main":
                await query.answer()
                with contextlib.suppress(Exception):
                    await query.message.edit_text(build_main_text(lang), reply_markup=build_main_markup(lang), parse_mode="Markdown")
                return

            if data == "adm:sync":
                await query.answer("🔄 Sinxronlanmoqda...", show_alert=False)
                try:
                    trucks = await monday.trucks()
                    failures = await refresh_groups(bot, db)
                    db.remap(trucks)
                    groups = db.groups()
                    present_groups = [g for g in groups if g.get("present")]
                    conflicts = [g for g in present_groups if not (g.get("manual_unit") or g.get("unit"))]
                    matched = len(present_groups) - len(conflicts)

                    lines = [
                        "✅ *Sinxronlash muvaffaqiyatli yakunlandi!*\n",
                        f"🚛 *Monday yuk mashinalari:* {len(trucks)} ta",
                        f"👥 *Faol Telegram guruhlar:* {len(present_groups)} ta",
                        f"🔗 *Bog'langan Unitlar:* {matched} ta",
                        f"⚠️ *Konfliktli guruhlar:* {len(conflicts)} ta",
                    ]
                    if failures:
                        lines.append(f"❌ *Yangilanmagan chatlar:* {len(failures)} ta")

                    rows = []
                    webapp_url = os.getenv("WEBAPP_URL", "")
                    if webapp_url.startswith("https://"):
                        rows.append([InlineKeyboardButton(text="📱 Mini Appda ko'rish", web_app=WebAppInfo(url=webapp_url))])
                    rows.append([
                        InlineKeyboardButton(text="📋 Guruhlar holati", callback_data="adm:groups"),
                        InlineKeyboardButton(text="⚠️ Faqat konfliktlar", callback_data="adm:groups:conflicts"),
                    ])
                    rows.append([
                        InlineKeyboardButton(text="🔄 Qayta sinxronlash", callback_data="adm:sync"),
                        InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main"),
                    ])
                    with contextlib.suppress(Exception):
                        await query.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
                except Exception as exc:
                    log.exception("Sync callback failed")
                    with contextlib.suppress(Exception):
                        await query.message.edit_text(
                            f"❌ *Sinxronlash xatosi:*\n`{exc}`",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔄 Qayta urinish", callback_data="adm:sync")],
                                [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")]
                            ]),
                            parse_mode="Markdown"
                        )
                return

            if data in ("adm:groups", "adm:groups:all"):
                await query.answer()
                text, markup = build_groups_view(filter_mode="all", lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

            if data == "adm:groups:active":
                await query.answer()
                text, markup = build_groups_view(filter_mode="active", lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

            if data == "adm:groups:inactive":
                await query.answer()
                text, markup = build_groups_view(filter_mode="inactive", lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

            if data == "adm:groups:conflicts":
                await query.answer()
                text, markup = build_groups_view(filter_mode="conflicts", lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

            if data == "adm:audits":
                await query.answer()
                text, markup = build_audits_view(lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

            if data == "adm:jobs":
                await query.answer()
                text, markup = build_jobs_view(lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

            if data.startswith("adm:cancel:"):
                job_id = int(data.split(":")[-1])
                cur = db.execute("UPDATE jobs SET state='cancelled' WHERE id=? AND state IN ('pending','running')", (job_id,))
                if cur.rowcount:
                    await query.answer(f"✅ #{job_id} vazifa bekor qilindi", show_alert=True)
                else:
                    await query.answer("Vazifa topilmadi yoki allaqachon yakunlangan", show_alert=True)
                text, markup = build_jobs_view(lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

            if data == "adm:admins":
                await query.answer()
                active_bot = bot or query.bot
                if active_bot:
                    for a in db.rows("SELECT a.id, a.name, u.username FROM admins a LEFT JOIN users u ON u.id=a.id WHERE u.username IS NULL OR u.username=''"):
                        try:
                            chat = await active_bot.get_chat(a["id"])
                            if chat.username:
                                db.execute("INSERT INTO users(id, username, lang) VALUES(?,?, 'uz') ON CONFLICT(id) DO UPDATE SET username=excluded.username", (a["id"], chat.username.lower()))
                            if chat.full_name and not a.get("name"):
                                db.execute("UPDATE admins SET name=? WHERE id=?", (chat.full_name, a["id"]))
                        except Exception:
                            pass
                text, markup = build_admins_view(lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

            if data == "adm:add_admin_prompt":
                await query.answer()
                prompt_text = t("admin_add_prompt_title", lang)
                if query.message:
                    await query.message.answer(prompt_text, parse_mode="Markdown", reply_markup=ForceReply(selective=True))
                else:
                    active_bot = bot or query.bot
                    if active_bot:
                        await active_bot.send_message(query.from_user.id, prompt_text, parse_mode="Markdown", reply_markup=ForceReply(selective=True))
                return

            if data.startswith("adm:del_admin_confirm:"):
                target_id = int(data.split(":")[-1])
                admins = db.rows("SELECT id FROM admins")
                if len(admins) <= 1:
                    await query.answer(t("admin_last_error", lang), show_alert=True)
                    return
                admin_row = db.rows("SELECT a.id, a.name, u.username FROM admins a LEFT JOIN users u ON u.id=a.id WHERE a.id=?", (target_id,))
                target_name = f"@{admin_row[0]['username']}" if (admin_row and admin_row[0].get("username")) else f"#{target_id}"
                await query.answer()
                confirm_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text=t("btn_confirm_yes", lang), callback_data=f"adm:del_admin_do:{target_id}"),
                        InlineKeyboardButton(text=t("btn_confirm_no", lang), callback_data="adm:admins"),
                    ]
                ])
                confirm_msg = {
                    "uz": f"⚠️ *Haqiqatan ham {target_name} administratorni o'chirmoqchimisiz?*",
                    "ru": f"⚠️ *Вы действительно хотите удалить администратора {target_name}?*",
                    "en": f"⚠️ *Are you sure you want to delete administrator {target_name}?*"
                }.get(lang, f"⚠️ *Haqiqatan ham {target_name} administratorni o'chirmoqchimisiz?*")
                with contextlib.suppress(Exception):
                    await query.message.edit_text(
                        confirm_msg,
                        reply_markup=confirm_markup,
                        parse_mode="Markdown"
                    )
                return

            if data.startswith("adm:del_admin_do:"):
                target_id = int(data.split(":")[-1])
                admins = db.rows("SELECT id FROM admins")
                if len(admins) <= 1:
                    await query.answer(t("admin_last_error", lang), show_alert=True)
                    return
                admin_row = db.rows("SELECT a.id, u.username FROM admins a LEFT JOIN users u ON u.id=a.id WHERE a.id=?", (target_id,))
                deleted_name = f"@{admin_row[0]['username']}" if (admin_row and admin_row[0].get("username")) else f"#{target_id}"
                db.execute("DELETE FROM admins WHERE id=?", (target_id,))
                await query.answer(f"✅ {deleted_name} o'chirildi", show_alert=True)
                text, markup = build_admins_view(lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

            if data == "adm:broadcast_info":
                await query.answer()
                text, markup = build_broadcast_info_view(lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

            if data.startswith("adm:send_now:"):
                job_id = int(data.split(":")[-1])
                row = db.rows("SELECT * FROM jobs WHERE id=? AND state='pending'", (job_id,))
                if not row:
                    await query.answer("Vazifa topilmadi yoki allaqachon bajarilgan", show_alert=True)
                    return
                await query.answer("🚀 Xabar yuborilmoqda...", show_alert=False)
                db.execute("UPDATE jobs SET state='running' WHERE id=?", (job_id,))
                active_bot = bot or query.bot
                asyncio.create_task(execute_job(active_bot, db, row[0]))
                with contextlib.suppress(Exception):
                    await query.message.edit_text(
                        f"🚀 *#{job_id} tarqatish boshlandi!*\n\nNatijalarni `⏰ Rejalar` bo'limida kuzatishingiz mumkin.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="⏰ Rejalar ro'yxati", callback_data="adm:jobs")],
                            [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="adm:main")]
                        ]),
                        parse_mode="Markdown"
                    )
                return

            if data == "adm:help":
                await query.answer()
                text, markup = build_help_view(lang=lang)
                with contextlib.suppress(Exception):
                    await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
                return

        # Callback buttons may be used by drivers; no privileged action is attached.
        await query.answer("Qabul qilindi")

    return app
