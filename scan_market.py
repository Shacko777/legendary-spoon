"""
╔══════════════════════════════════════════════════════════════════╗
║   SHACKOBOT  —  Market Scanner                                   ║
║   Fetches all Bybit linear perpetuals, filters by volume,        ║
║   and auto-generates a bot file for every symbol you don't       ║
║   already have.                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║   HOW TO USE                                                     ║
║   1. Set MIN_VOLUME_24H below (default $10M)                     ║
║   2. Run:  python scan_market.py                                 ║
║   3. Review the preview, press Enter to generate                 ║
║   4. Restart watchdog to pick up new bots                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, sys, re, json, requests
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════

# Minimum 24h traded volume in USD to include a symbol
MIN_VOLUME_24H   = 10_000_000      # $1M  — filters out illiquid symbols

# Where to write new bot files
SHACKOBOT_DIR    = Path(__file__).parent
CRYPTO_DIR       = SHACKOBOT_DIR / "CRYPTO"
STOCK_DIR        = SHACKOBOT_DIR / "STOCK"
COMMOD_DIR       = SHACKOBOT_DIR / "COMMOD"

# Template bot file to clone for each new symbol
# Must be in the SHACKOBOT root directory
TEMPLATE_FILE    = SHACKOBOT_DIR / "$.py"

# Bybit API
BYBIT_API        = "https://api.bybit.com"

# ── Known non-crypto categories ───────────────────────────────────
STOCK_BASES = {
    "AAPL","AMD","AMDSTOCK","GOOGL","GOOGLA","INTC","MSFT","NVDA","ORCL",
    "TSLA","META","AMZN","NFLX","COIN","MSTR","CRCL","TSM","MU","SNDK",
    "ARM","PLTR","SMCI","AVGO","QCOM","TXN","CRM","NOW","RBLX","SNAP","SPOT",
    "JPM","BAC","GS","MS","HOOD","BRK","BRKB","WMT","DIS","SBUX","NIKE",
    "SPY","QQQ","SPCX","EWJ","EWY","IWM","GLD","SLV","USO","NOKIA",
}
COMMOD_BASES = {"XAU","XAG","CL","NG","HG","PL","PA","SI","GC","ZC","ZW","ZS"}

# Maps a short bot filename stem to all Bybit symbol variants it covers.
# Add entries here whenever Bybit uses a prefix (1000x, 1000, etc.)
FILENAME_ALIASES: dict = {
    "PEPE":  {"1000PEPEUSDT",  "PEPEUSDT"},
    "SHIB":  {"1000SHIBUSDT",  "SHIB1000USDT", "SHIBUSDT"},
    "BONK":  {"1000BONKUSDT",  "BONKUSDT"},
    "FLOKI": {"1000FLOKIUSDT", "FLOKIUSDT"},
    "RATS":  {"1000RATSUSDT",  "RATSUSDT"},
    "SATS":  {"1000SATSUSDT",  "SATSUSDT"},
    "XEC":   {"1000XECUSDT",   "XECUSDT"},
    "LUNC":  {"1000LUNCUSDT",  "LUNCUSDT"},
}

# Symbols to always skip (stablecoins, index tokens, wrapped assets etc.)
SKIP_SYMBOLS = {
    "USDCUSDT","USDTUSDT","BUSDUSDT","TUSDUSDT","FRAXUSDT","DAIUSDT",
    "BTCDOMUSDT","DEFIUSDT","ALTUSDT","BNXUSDT","USTCUSDT","LUNAUSDT",
    "BTCUSDT.P","ETHUSDT.P",
}

# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def fetch_all_symbols():
    """Fetch all active linear perpetual symbols from Bybit with 24h volume."""
    print("Fetching symbols from Bybit...")
    try:
        r = requests.get(
            f"{BYBIT_API}/v5/market/tickers",
            params={"category": "linear"},
            timeout=15,
        ).json()
        if r.get("retCode") != 0:
            print(f"Bybit error: {r.get('retMsg')}"); sys.exit(1)
        return r["result"]["list"]
    except Exception as e:
        print(f"Failed to fetch symbols: {e}"); sys.exit(1)

def classify(symbol: str):
    """Return 'stock', 'commodity', or 'crypto' for a symbol."""
    base = symbol.replace("USDT","").replace("STOCK","").upper()
    if base in COMMOD_BASES: return "commodity"
    if base in STOCK_BASES:  return "stock"
    return "crypto"

def target_dir(category: str) -> Path:
    return {"stock": STOCK_DIR, "commodity": COMMOD_DIR}.get(category, CRYPTO_DIR)

def bot_filename(symbol: str) -> str:
    """Convert BEATUSDT → BEAT.py"""
    return symbol.replace("USDT","").replace("STOCK","") + ".py"

def existing_symbols() -> set:
    """Return set of symbols that already have a bot file.

    Handles prefixed symbols: PEPE.py → also marks 1000PEPEUSDT as covered,
    SHIB.py → 1000SHIBUSDT, BONK.py → 1000BONKUSDT, etc.
    """
    found = set()
    for folder in [CRYPTO_DIR, STOCK_DIR, COMMOD_DIR]:
        if not folder.exists(): continue
        for f in folder.glob("*.py"):
            if f.name.startswith("_"): continue
            base = f.stem.upper()
            # Direct mapping
            found.add(base + "USDT")
            found.add(base + "STOCKUSDT")   # AMD edge case
            # Alias lookup — catches 1000PEPE, 1000SHIB etc.
            for sym in FILENAME_ALIASES.get(base, set()):
                found.add(sym)
    return found

def generate_bot(symbol: str, template: str) -> str:
    """Replace SYMBOL in template with the target symbol."""
    # Replace the SYMBOL = "BTCUSDT" line only
    new = re.sub(
        r'^(SYMBOL\s*=\s*)["\'][^"\']+["\']',
        f'SYMBOL       = "{symbol}"',
        template,
        count=1,
        flags=re.MULTILINE,
    )
    return new

# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    # ── Load template ─────────────────────────────────────────────
    if not TEMPLATE_FILE.exists():
        print(f"Template not found: {TEMPLATE_FILE}")
        print("Make sure merged_bot_universal_v2.py is in the SHACKOBOT root.")
        sys.exit(1)
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    print(f"Template: {TEMPLATE_FILE.name}")

    # ── Fetch all Bybit tickers ────────────────────────────────────
    tickers = fetch_all_symbols()
    print(f"Total symbols on Bybit: {len(tickers)}")

    # ── Filter ────────────────────────────────────────────────────
    qualified = []
    for t in tickers:
        sym    = t.get("symbol","")
        vol24h = float(t.get("turnover24h") or t.get("volume24h") or 0)

        # Must end in USDT (linear perp)
        if not sym.endswith("USDT"): continue
        # Skip blacklist
        if sym in SKIP_SYMBOLS: continue
        # Skip inverse / quarterly markers
        if any(x in sym for x in ["-","_","."]): continue
        # Volume filter
        if vol24h < MIN_VOLUME_24H: continue

        qualified.append((sym, vol24h, classify(sym)))

    # Sort by volume descending
    qualified.sort(key=lambda x: x[1], reverse=True)
    print(f"After ${MIN_VOLUME_24H/1e6:.0f}M volume filter: {len(qualified)} symbols")

    # ── Compare against existing bots ─────────────────────────────
    have = existing_symbols()
    new  = [(s, v, c) for s, v, c in qualified if s not in have]
    skip = [(s, v, c) for s, v, c in qualified if s in have]

    print(f"Already have bots for: {len(skip)}")
    print(f"New symbols to create: {len(new)}")

    if not new:
        print("\nAll qualifying symbols already have bots. Nothing to do.")
        return

    # ── Preview ───────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  {'SYMBOL':<20} {'CATEGORY':<12} {'24H VOL':>14}")
    print(f"{'─'*60}")
    for sym, vol, cat in new:
        fname = bot_filename(sym)
        folder = target_dir(cat).name
        vol_str = f"${vol/1e6:.1f}M"
        print(f"  {sym:<20} {folder+'/'+fname:<24} {vol_str:>10}")
    print(f"{'─'*60}")
    print(f"  {len(new)} new bot files will be created")
    print()

    # ── Confirm ───────────────────────────────────────────────────
    try:
        ans = input("Press Enter to generate, or Ctrl+C to cancel... ")
    except KeyboardInterrupt:
        print("\nCancelled."); return

    # ── Create directories ────────────────────────────────────────
    for d in [CRYPTO_DIR, STOCK_DIR, COMMOD_DIR]:
        d.mkdir(exist_ok=True)

    # ── Generate files ────────────────────────────────────────────
    created, failed = [], []
    for sym, vol, cat in new:
        dest = target_dir(cat) / bot_filename(sym)
        try:
            content = generate_bot(sym, template)
            # Quick sanity check: SYMBOL line must be updated
            if f'SYMBOL       = "{sym}"' not in content:
                raise ValueError(f"SYMBOL replacement failed for {sym}")
            dest.write_text(content, encoding="utf-8")
            created.append((sym, dest))
            print(f"  ✓  {dest.relative_to(SHACKOBOT_DIR)}")
        except Exception as e:
            failed.append((sym, str(e)))
            print(f"  ✗  {sym}: {e}")

    # ── Summary ───────────────────────────────────────────────────
    print()
    print(f"{'─'*60}")
    print(f"  Created: {len(created)}  Failed: {len(failed)}")
    if failed:
        print("  Failed symbols:")
        for sym, err in failed: print(f"    {sym}: {err}")
    print()
    print("  Next steps:")
    print("  1. Stop watchdog (Ctrl+C)")
    print("  2. Restart watchdog — it will auto-discover the new bots")
    print(f"{'─'*60}")

if __name__ == "__main__":
    main()
