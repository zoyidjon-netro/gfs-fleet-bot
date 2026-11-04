"""Create a consistent SQLite backup while the bot is running."""
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
source = Path(os.getenv("DB_PATH", "data/gfs.sqlite3"))
if not source.is_file():
    raise SystemExit("Bot bazasi topilmadi")
destination_dir = Path("data/backups")
destination_dir.mkdir(parents=True, exist_ok=True)
destination = destination_dir / f"gfs-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3"
with sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True) as original:
    with sqlite3.connect(destination) as backup:
        original.backup(backup)
        if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup tekshiruvi muvaffaqiyatsiz")
print(f"Backup: {destination}")
