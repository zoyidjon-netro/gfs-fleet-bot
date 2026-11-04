"""Single-instance Windows background supervisor for the local bot and HTTPS tunnel."""
import logging
from logging.handlers import RotatingFileHandler
import msvcrt
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
os.chdir(ROOT)
handler = RotatingFileHandler(DATA / 'supervisor.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
logging.basicConfig(handlers=[handler], level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('supervisor')
PYTHON = str(Path(sys.executable).with_name('python.exe'))
FLAGS = subprocess.CREATE_NO_WINDOW


def spawn(args, output):
    with open(output, 'ab', buffering=0) as stream:
        return subprocess.Popen(args, cwd=ROOT, stdout=stream, stderr=stream, creationflags=FLAGS)


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def save_url(url):
    path = ROOT / '.env'
    text = path.read_text(encoding='utf-8-sig')
    updated, count = re.subn(r'^WEBAPP_URL=.*$', 'WEBAPP_URL=' + url, text, flags=re.M)
    if not count:
        updated += '\nWEBAPP_URL=' + url + '\n'
    temporary = ROOT / '.env.tmp'
    temporary.write_text(updated, encoding='utf-8')
    temporary.replace(path)


def main():
    lock = open(DATA / 'supervisor.lock', 'a+b')
    lock.seek(0)
    if not lock.read(1):
        lock.write(b'0')
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return
    (DATA / 'supervisor.pid').write_text(str(os.getpid()), encoding='ascii')
    log.info('Background supervisor started')
    tunnel = bot = None
    next_backup = 0
    try:
        while True:
            try:
                config = dotenv_values(ROOT / '.env')
                port = int(config.get('PORT') or 8000)
                cloudflared = shutil.which('cloudflared') or r'C:\Program Files (x86)\cloudflared\cloudflared.exe'
                tunnel_log = DATA / 'managed-tunnel.log'
                tunnel_log.write_text('', encoding='utf-8')
                tunnel = spawn([cloudflared, 'tunnel', '--url', f'http://127.0.0.1:{port}', '--no-autoupdate'], tunnel_log)
                url = None
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline and tunnel.poll() is None:
                    urls = re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', tunnel_log.read_text(encoding='utf-8', errors='replace'))
                    if urls:
                        url = urls[-1]
                        break
                    time.sleep(2)
                if not url:
                    raise RuntimeError('HTTPS tunnel did not become ready')
                save_url(url)
                log.info('HTTPS URL updated; starting bot')
                bot = spawn([PYTHON, str(ROOT / 'main.py')], DATA / 'managed-bot.log')
                while tunnel.poll() is None:
                    if bot.poll() is not None:
                        log.warning('Bot exited; restarting in 10 seconds')
                        time.sleep(10)
                        bot = spawn([PYTHON, str(ROOT / 'main.py')], DATA / 'managed-bot.log')
                    if time.time() >= next_backup:
                        try:
                            with open(DATA / 'backup.log', 'ab') as output:
                                result = subprocess.run([PYTHON, str(ROOT / 'backup_db.py')], cwd=ROOT,
                                                        stdout=output, stderr=output, creationflags=FLAGS, timeout=120)
                            next_backup = time.time() + (86400 if result.returncode == 0 else 300)
                            log.info('Backup finished with exit code %s', result.returncode)
                        except (OSError, subprocess.TimeoutExpired):
                            next_backup = time.time() + 300
                            log.exception('Backup failed; retrying in five minutes')
                    time.sleep(5)
                log.warning('Tunnel exited; recreating tunnel and bot')
            except Exception:
                log.exception('Supervisor cycle failed')
            finally:
                stop(bot)
                stop(tunnel)
                bot = tunnel = None
            time.sleep(10)
    finally:
        stop(bot)
        stop(tunnel)
        lock.close()


if __name__ == '__main__':
    main()
