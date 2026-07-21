"""
SHACKOBOT Watchdog
==================
Starts and monitors all 55 bots automatically.
Restarts any crashed bot within 5 seconds.
Sends Telegram alerts on crash and restart.

Usage:
    python watchdog.py              ← start ALL bots + monitor
    python watchdog.py --monitor    ← monitor already-running bots only
    python watchdog.py --list       ← just show which bots would run

Place this file in your SHACKOBOT folder (same level as dashboard.py).
"""

import subprocess, os, sys, time, re, json, threading, signal, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════
SHACKOBOT_DIR   = Path(__file__).parent
PYTHON          = sys.executable
# ── Telegram credentials (paste your values here) ────────────
TG_TOKEN_OVERRIDE = ""     # ← paste your bot token  e.g. "123456:ABC-xyz..."
TG_CHAT_OVERRIDE  = ""     # ← paste your chat ID    e.g. "-1001234567890"

CHECK_EVERY     = 15       # seconds between health checks
RESTART_DELAY   = 5        # seconds to wait before restarting a crashed bot
MAX_CRASHES     = 5        # max crashes in CRASH_WINDOW before pausing bot
CRASH_WINDOW    = 600      # 10 minutes — crash count window
PAUSE_DURATION  = 300      # 5 min pause after too many crashes
START_DELAY     = 1.5      # seconds between starting each bot (avoid API flood)

# Bot subdirectories to scan
BOT_DIRS = ["CRYPTO", "STOCK", "COMMOD", "."]

# Files to skip (not bots)
SKIP_FILES = {
    "dashboard.py", "watchdog.py", "remote_access.py",
    "backtest.py", "setup.py", "install.py"
}

# ═══════════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════════
_tg_token = None
_tg_chat  = None

def _load_telegram():
    global _tg_token, _tg_chat

    # 1. Hardcoded overrides (set TG_TOKEN_OVERRIDE / TG_CHAT_OVERRIDE above)
    if TG_TOKEN_OVERRIDE.strip() and TG_CHAT_OVERRIDE.strip():
        _tg_token = TG_TOKEN_OVERRIDE.strip()
        _tg_chat  = TG_CHAT_OVERRIDE.strip()
        return True

    # 2. Environment variables
    _tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "8257147358:AAEonxFQTMP8wwQwR21qMPOlVR1_q24wUM4").strip()
    _tg_chat  = os.environ.get("TELEGRAM_CHAT_ID",   "5984757072").strip()
    if _tg_token and _tg_chat:
        return True

    # 3. Fallback: scan bot files for hardcoded literal values
    for d in BOT_DIRS:
        folder = SHACKOBOT_DIR / d
        if not folder.is_dir(): continue
        for f in sorted(folder.glob("*.py")):
            if f.name in SKIP_FILES: continue
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
                tok = (re.search(r'TELEGRAM_BOT_TOKEN\s*=\s*["\']([^"\']+)["\']', txt) or
                       re.search(r'TG_TOKEN\s*=\s*["\']([^"\']+)["\']', txt))
                cht = (re.search(r'TELEGRAM_CHAT_ID\s*=\s*["\']([^"\']+)["\']', txt) or
                       re.search(r'TG_CHAT\b\s*=\s*["\']([^"\']+)["\']', txt))
                if tok and cht:
                    _tg_token = tok.group(1)
                    _tg_chat  = cht.group(1)
                    return True
            except: pass
    return False

def tg(msg):
    """Send Telegram message (non-blocking)"""
    def _send():
        if not _tg_token or not _tg_chat: return
        try:
            payload = json.dumps({"chat_id": _tg_chat, "text": msg,
                                  "parse_mode": "Markdown"}).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{_tg_token}/sendMessage",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
        except: pass
    threading.Thread(target=_send, daemon=True).start()

# ═══════════════════════════════════════════════════════════════════
# BOT PROCESS
# ═══════════════════════════════════════════════════════════════════
class BotProcess:
    def __init__(self, path: Path):
        self.path     = path
        self.name     = path.stem.upper()   # "AAVE", "BTC", "AAPL"
        raw_cat = path.parent.name.upper() if path.parent != SHACKOBOT_DIR else "BOT"
        nm = path.stem.upper()
        COMMOD_NAMES = {"XAG","XAU","CL","SILVER","GOLD","OIL"}
        STOCK_NAMES  = {"AAPL","AMD","GOOGL","INTC","MSFT","NVDA","ORCL","QQQ","SPY","TSLA","AMZN","META","NFLX","COIN","NOKIA","SPCX"}
        if nm in COMMOD_NAMES:    self.category = "COMMOD"
        elif nm in STOCK_NAMES:   self.category = "STOCK"
        else:                     self.category = raw_cat
        self.proc     = None
        self.crashes  = []     # timestamps of recent crashes
        self.paused_until   = None
        self.total_restarts = 0
        self.started_at     = None
        self.last_crash_at  = None
        self.exit_code      = None

    # ── Process control ─────────────────────────────────────────
    def start(self):
        """Start the bot subprocess"""
        # Write stderr to a small crash log so failures are diagnosable
        err_log = SHACKOBOT_DIR / f"{self.name.lower()}_crash.log"
        self._err_file = open(err_log, "a", encoding="utf-8")
        # Force UTF-8 in the subprocess so box-drawing chars in the startup
        # banner don't crash on Windows cp1252 console encoding
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        self.proc = subprocess.Popen(
            [PYTHON, str(self.path)],
            cwd=str(self.path.parent),
            stdout=subprocess.DEVNULL,
            stderr=self._err_file,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        self.started_at = datetime.now()
        return self.proc

    def stop(self):
        """Gracefully stop the bot"""
        if self.proc:
            try: self.proc.terminate()
            except: pass
            try: self.proc.wait(timeout=5)
            except:
                try: self.proc.kill()
                except: pass

    def restart(self):
        """Stop and restart the bot"""
        self.stop()
        time.sleep(RESTART_DELAY)
        self.total_restarts += 1
        return self.start()

    # ── Status ──────────────────────────────────────────────────
    def is_alive(self):
        if not self.proc: return False
        rc = self.proc.poll()
        if rc is not None: self.exit_code = rc
        return rc is None

    def is_paused(self):
        if self.paused_until and datetime.now() < self.paused_until:
            return True
        self.paused_until = None
        return False

    def record_crash(self) -> bool:
        """Record a crash. Returns True if bot should be paused."""
        now = datetime.now()
        self.last_crash_at = now
        self.crashes.append(now)
        # Prune old crashes outside window
        cutoff = now - timedelta(seconds=CRASH_WINDOW)
        self.crashes = [c for c in self.crashes if c > cutoff]
        if len(self.crashes) >= MAX_CRASHES:
            self.paused_until = now + timedelta(seconds=PAUSE_DURATION)
            return True
        return False

    @property
    def uptime(self):
        if not self.started_at or not self.is_alive(): return "—"
        s = int((datetime.now() - self.started_at).total_seconds())
        if s < 60:   return f"{s}s"
        if s < 3600: return f"{s//60}m{s%60:02d}s"
        return f"{s//3600}h{(s%3600)//60:02d}m"

    @property
    def status_icon(self):
        if self.is_paused(): return "⏸"
        if self.is_alive():  return "✓"
        return "✗"

    @property
    def status_text(self):
        if self.is_paused():
            rem = int((self.paused_until - datetime.now()).total_seconds())
            return f"PAUSED {rem}s"
        if self.is_alive(): return f"RUNNING  uptime={self.uptime}"
        return f"DOWN  exit={self.exit_code}"

# ═══════════════════════════════════════════════════════════════════
# BOT DISCOVERY
# ═══════════════════════════════════════════════════════════════════
SELF_FILE = Path(__file__).resolve()

def discover_bots() -> list:
    """Open every .py file inside the CRYPTO, STOCK, and COMMOD folders."""
    found = []
    seen  = set()

    for d in ["CRYPTO", "STOCK", "COMMOD"]:
        folder = SHACKOBOT_DIR / d
        if not folder.is_dir():
            continue
        for f in sorted(folder.glob("*.py")):
            if f.resolve() == SELF_FILE:
                continue
            key = f.stem.lower()
            if key in seen:
                continue
            found.append(BotProcess(f))
            seen.add(key)

    return found

# ═══════════════════════════════════════════════════════════════════
# DISPLAY
# ═══════════════════════════════════════════════════════════════════
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def render_status(bots: list, events: list):
    clear()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alive  = sum(1 for b in bots if b.is_alive())
    paused = sum(1 for b in bots if b.is_paused())
    down   = sum(1 for b in bots if not b.is_alive() and not b.is_paused())

    print(f"""
  ╔══════════════════════════════════════════════════════════╗
  ║  SHACKOBOT WATCHDOG  │  {now}            ║
  ╠══════════════════════════════════════════════════════════╣
  ║  Bots: {len(bots):<4} │ ✓ Running: {alive:<4} │ ✗ Down: {down:<4} │ ⏸ Paused: {paused:<3}║
  ╚══════════════════════════════════════════════════════════╝
""")

    # Group by category
    cats = {}
    for b in bots:
        cats.setdefault(b.category, []).append(b)

    for cat, group in sorted(cats.items()):
        print(f"  {'─'*56}")
        print(f"  {cat}")
        print(f"  {'─'*56}")
        for b in group:
            icon = b.status_icon
            rst  = f"restarts={b.total_restarts}" if b.total_restarts else ""
            print(f"  {icon}  {b.name:<12}  {b.status_text:<30}  {rst}")

    print(f"\n  {'─'*56}")
    print(f"  Recent Events (last 10):")
    for e in events[-10:]:
        print(f"  {e}")
    print(f"\n  Ctrl+C to stop all bots and exit")

# ═══════════════════════════════════════════════════════════════════
# MAIN WATCHDOG LOOP
# ═══════════════════════════════════════════════════════════════════
def run_watchdog(bots: list, monitor_only: bool = False):
    events = []
    _restart_lock = threading.Lock()  # prevent simultaneous restart spam

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        events.append(f"[{ts}] {msg}")

    def restart_bot(b):
        """Restart a single bot in a background thread — non-blocking."""
        with _restart_lock:
            time.sleep(RESTART_DELAY)
            try:
                b.restart()
                log(f"♻️ {b.name} restarted (#{b.total_restarts}) PID={b.proc.pid}")
                tg(f"♻️ *{b.name} restarted* (restart #{b.total_restarts})")
            except Exception as e:
                log(f"✗ {b.name} failed to restart: {e}")
                tg(f"❌ *{b.name}* could not restart: {e}")

    # Start all bots
    if not monitor_only:
        print(f"\n  Starting {len(bots)} bots...")
        started, failed = [], []
        for i, b in enumerate(bots):
            try:
                b.start()
                print(f"  [{i+1:02d}/{len(bots)}] ▶ {b.name:<12} PID={b.proc.pid}")
                log(f"▶ {b.name} started (PID {b.proc.pid})")
                started.append(b.name)
                time.sleep(START_DELAY)
            except Exception as e:
                print(f"  [{i+1:02d}/{len(bots)}] ✗ {b.name:<12} FAILED: {e}")
                log(f"✗ {b.name} failed to start: {e}")
                failed.append(b.name)

        # One Telegram summary with all bots listed
        crypto = [b for b in bots if b.category=="CRYPTO" and b.name in started]
        stock  = [b for b in bots if b.category=="STOCK"  and b.name in started]
        commod = [b for b in bots if b.category=="COMMOD" and b.name in started]
        msg  = f"🚀 *SHACKOBOT Watchdog started*\n"
        msg += f"✅ {len(started)}/{len(bots)} bots running\n\n"
        if crypto: msg += f"₿ *CRYPTO* ({len(crypto)}): " + " ".join(b.name for b in crypto) + "\n"
        if stock:  msg += f"📈 *STOCK* ({len(stock)}): "  + " ".join(b.name for b in stock)  + "\n"
        if commod: msg += f"🥇 *COMMOD* ({len(commod)}): "+ " ".join(b.name for b in commod) + "\n"
        if failed: msg += f"\n❌ Failed: {', '.join(failed)}"
        msg += f"\n\n🔄 Auto-restart ON  │  Check every {CHECK_EVERY}s"
        tg(msg)

        # Wait long enough for ALL bots to finish their startup sequence
        # (clock sync + Bybit spec fetch + state load can take 10-20s each).
        # Without this, the first monitor pass catches bots mid-init and
        # misreads them as crashed.
        startup_wait = len(bots) * START_DELAY + 30
        print(f"\n  All bots launched. Waiting {startup_wait:.0f}s for startup to settle...")
        time.sleep(startup_wait)

    # Monitor loop
    while True:
        time.sleep(CHECK_EVERY)
        for b in bots:
            if b.is_paused(): continue
            if not b.is_alive():
                down_time = ""
                if b.last_crash_at:
                    s = int((datetime.now() - b.last_crash_at).total_seconds())
                    down_time = f" (down {s}s)"

                paused = b.record_crash()
                msg = f"💀 *{b.name} CRASHED*{down_time}\nExit code: {b.exit_code}"

                if paused:
                    msg += f"\n⏸ Too many crashes — paused {PAUSE_DURATION//60}min"
                    log(f"⏸ {b.name} paused after {MAX_CRASHES} crashes")
                    tg(msg)
                else:
                    log(f"💀 {b.name} crashed — restarting in {RESTART_DELAY}s...")
                    tg(msg + f"\n♻️ Restarting in {RESTART_DELAY}s...")
                    # Non-blocking restart — doesn't hold up the rest of the loop
                    threading.Thread(target=restart_bot, args=(b,), daemon=True).start()

        render_status(bots, events)

# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    args = sys.argv[1:]

    print("""
  ╔══════════════════════════════════════════════════════════╗
  ║            SHACKOBOT WATCHDOG                            ║
  ╚══════════════════════════════════════════════════════════╝
""")

    # Load Telegram config
    if _load_telegram():
        print(f"  [Telegram] Loaded — alerts enabled ✓")
    else:
        print(f"  [Telegram] Not found — no alerts (bots still watched)")

    # Discover bots
    bots = discover_bots()
    print(f"\n  Discovered {len(bots)} bots:")
    for b in bots:
        print(f"    {b.category:<8} {b.name}")

    if "--list" in args:
        sys.exit(0)

    monitor_only = "--monitor" in args
    if monitor_only:
        print("\n  Monitor-only mode — not starting bots")
    else:
        print(f"\n  Will start all {len(bots)} bots with {START_DELAY}s between each")

    print("\n  Press Enter to continue or Ctrl+C to cancel...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n  Cancelled.")
        sys.exit(0)

    # Handle Ctrl+C — stop all bots cleanly
    def on_exit(sig, frame):
        print("\n\n  Stopping all bots...")
        for b in bots:
            b.stop()
            print(f"  ■ {b.name} stopped")
        tg("🛑 *SHACKOBOT Watchdog stopped*\nAll bots stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, on_exit)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_exit)

    run_watchdog(bots, monitor_only=monitor_only)
