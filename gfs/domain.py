"""Pure business rules, independent of Telegram and Monday."""
import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qsl

VIN = re.compile(r"(?<![A-Z0-9])[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])", re.I)
ALLOWED_GROUPS = {"TRUCKS IN USAGE", "owner operators", "upcoming"}
BAD_STATUSES = {"SHOP", "INACTIVE", "AVAILIBLE", "AVAILABLE"}


def normalize_unit(value):
    value = str(value).strip()
    return str(int(value)) if value.isdigit() else value


def eligible(title, has_photo):
    return not (re.search(r"\bINACTIVE\b", title, re.I) and not has_photo)


def resolve_unit(title, units):
    matches = {normalize_unit(x) for x in re.findall(r"\d+", title)} & set(units)
    return next(iter(matches)) if len(matches) == 1 else None


def extract_vins(text):
    return {m.upper() for m in VIN.findall(text)}


def validate_init_data(raw, token, now=None):
    pairs = parse_qsl(raw, keep_blank_values=True)
    if len(dict(pairs)) != len(pairs):
        raise ValueError("Duplicate auth fields")
    data = dict(pairs)
    received = data.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    age = (now or time.time()) - int(data.get("auth_date", 0))
    if not hmac.compare_digest(received, expected) or not -30 <= age <= 3600:
        raise ValueError("Invalid or expired Telegram authentication")
    return int(json.loads(data["user"])["id"])


def next_weekly(after, weekday, hour, minute, zone):
    local = after.astimezone(zone)
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    candidate += timedelta(days=(weekday - local.weekday()) % 7)
    if candidate <= local:
        candidate += timedelta(days=7)
    return candidate.timestamp()


def report(vins, trucks, groups):
    known = {t["vin"] for t in trucks if t["vin"]}
    missing = sorted(vins - known)
    blocks = [f"COI: {len(vins)} VIN. Monday: {len(trucks)} ta yozuv."]
    if missing:
        blocks.append("Активны в COI, но отсутствуют в рабочих группах Monday:\n" + "\n".join(missing))
    warnings = []
    for group in groups:
        if not group["present"] or not eligible(group["title"], group["photo"]):
            continue
        unit = group["manual_unit"] or group["unit"]
        for truck in trucks:
            if truck["unit"] == unit and truck["status"].strip().upper() in BAD_STATUSES:
                warnings.append(f'Трак {unit} едет (чат {group["title"]} активен), но в Monday указан статус {truck["status"]}. Требуется обновить доску Monday.')
    if warnings:
        blocks.append("Физически активны (живой чат), но неверный статус в Monday:\n" + "\n".join(warnings))
    if not missing and not warnings:
        blocks.append("Tafovutlar topilmadi.")
    unresolved = [g["title"] for g in groups if g["present"] and not (g["manual_unit"] or g["unit"])]
    if unresolved:
        blocks.append("Unit aniqlanmagan (Mini App orqali belgilang):\n" + "\n".join(unresolved))
    return "\n\n".join(blocks)


def audit_details(vins, trucks, groups):
    """Structured audit facts for the Mini App, independent of report wording."""
    known = {t["vin"] for t in trucks if t["vin"]}
    warnings = []
    for group in groups:
        if not group["present"] or not eligible(group["title"], group["photo"]):
            continue
        unit = group["manual_unit"] or group["unit"]
        for truck in trucks:
            if truck["unit"] == unit and truck["status"].strip().upper() in BAD_STATUSES:
                warnings.append({"chat_id": group["id"], "title": group["title"],
                                 "unit": unit, "status": truck["status"]})
    return {"vin_count": len(vins), "monday_count": len(trucks),
            "missing_vins": sorted(vins - known), "warnings": warnings}
