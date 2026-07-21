"""
SHACKOBOT DASHBOARD
Right-side symbol panel · Bot cards grid · Chart on click · Live data
python dashboard.py          → dashboard.html
python dashboard.py --serve  → http://localhost:5000
"""
import os, sys, json, glob, time, re, hmac, hashlib
from datetime import datetime
import requests

TAKER_FEE = 0.00055  # per side

BYBIT_API   = "https://api.bybit.com"
REFRESH_SEC = 15
OUTPUT_FILE = "dashboard.html"
PORT        = 5000

# Symbol categories for filters
CATEGORIES = {
    "stock": {
        # US stocks & ETFs on Bybit
        "TSLAUSDT","NVDAUSDT","AAPLUSDT","AMDUSDT","AMDSTOCKUSDT","SPYUSDT","MSFTUSDT",
        "GOOGLUSDT","GOOGLAUSDT","INTCUSDT","QQQUSDT","ORCLUSDT",
        "COINUSDT","AMZNUSDT","METAUSDT","NFLXUSDT","BRKBUSDT",
        "JPMUSDT","VSUSDT","BRKUSDT","DISUSDT","SBUXUSDT","NIKEUSDT",
        "NOKIAUSDT","SPCXUSDT","TSMUSDT","MUUSDT","SNDKUSDT","MSTRUSDT",
        "HOODUSDT","CRCLUSDT","EWJUSDT","EWYUSDT","SNAPUSDT","PLTRUSDT",
        "ARMUSTDT","COINUSDT",
    },
    "commodity": {"XAUUSDT","XAGUSDT","CLUSDT","NGUSDT","BTCUSD.P"},
}
# Known stock tickers on Bybit TradFi — auto-updated as you add new bots
# Just add the ticker here when you add a new stock bot, no other changes needed
STOCK_TICKERS = {
    # Tech
    "AAPL","AMD","AMDSTOCK","GOOGL","GOOGLA","INTC","MSFT","NVDA","ORCL",
    "TSLA","META","AMZN","NFLX","COIN","MSTR","CRCL","TSM","MU","SNDK",
    "ARM","PLTR","SMCI","AVGO","QCOM","TXN","CRM","NOW","RBLX","SNAP","SPOT",
    # Finance
    "JPM","BAC","GS","MS","HOOD","BRK","BRKB",
    # Consumer / Other
    "WMT","DIS","SBUX","NIKE","VS","NKE",
    # ETFs
    "SPY","QQQ","SPCX","EWJ","EWY","IWM","GLD","SLV","USO",
    # Telecom
    "NOKIA",
}

# Known commodity base symbols
COMMODITY_BASES = {"XAU","XAG","CL","NG","HG","PL","PA","SI","GC","ZC","ZW","ZS"}

# ── Volume tiers (approximate 24h vol on Bybit) ──────────────────────────────
TIER1_SYMS = {
    "BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","PEPEUSDT",
    "TRUMPUSDT","WIFUSDT","SHIBUSDT","HYPEUSDT","VIRTUALUSDT","PENGUUSDT",
    "MOVEUSDT","ARBUSDT","ADAUSDT","TRXUSDT","AVAXUSDT","WLDUSDT","ENAUSUSDT",
    "NEARUSDT","SUIUSDT","TAOUSDT","LTCUSDT","BCHUSDT","XLMUSDT","XMRUSDT",
}
TIER2_SYMS = {
    "LINKUSDT","OPUSDT","HBARUSDT","IPUSDT","BERAUSDT","ZEROUSDT","ETHFIUSDT",
    "CRVUSDT","LDOUSDT","PENDLEUSDT","BONKUSDT","FLOKIUSDT","EIGENUSDT",
    "STRKUSDT","ENSUSDT","GRTUSDT","AXSUSDT","BLURUSDT","SANDUSDT","JUPUSDT","COWUSDT","STGUSDT","RSRUSDT","FLUIDUSDT",
    "KASUSDT","SEIUSDT","RENDERUSDT","IMXUSDT","FILUSDT","ICPUSDT","ETCUSDT",
    "APTUSDT","STGUSDT","ORDIUSDT","ZKUSDT","MOODENGUSDT","POPCATUSDT",
    "1INCHUSDT","PNUTUSDT","COMPUSDT","ALGOUSDT","CHZUSDT","IOTAUSDT",
    "ATOMUSDT","DYDXUSDT","THETAUSDT","INJUSDT","DOTUSDT","UNIUSDT","TONUSDT",
    "ZECUSDT","AAVEUSDT","ONDOUSDT","STXUSDT","VVVUSDT","SPXUSDT","WLFIUSDT",
    "ENAUSDT","MNXUSDT","JUPTUSDT","JTOUSDT","MNXUSDT","KSMUSDT","IMXUSDT",
    "QNTUSDT","VETUSDT","OKBUSDT","TIAUSDT","LITUSDT","SEIUSDT",
}
# ── Layer / category classification ──────────────────────────────────────────
L1_SYMS = {
    "BTCUSDT","ETHUSDT","SOLUSDT","ADAUSDT","AVAXUSDT","BNBUSDT","DOTUSDT",
    "ATOMUSDT","NEARUSDT","ALGOUSDT","TRXUSDT","TONUSDT","SUIUSDT","APTUSDT",
    "TAOUSDT","HYPEUSDT","HBARUSDT","BERAUSDT","IPUSDT","ICPUSDT","IOTAUSDT",
    "KASUSDT","THETAUSDT","NEOUSDT","XRPUSDT","XLMUSDT","XMRUSDT","ZECUSDT",
    "LTCUSDT","BCHUSDT","DASHUSDT","KSMUSDT","QNTUSDT","VETUSDT","FLOWUSDT",
    "EGLDUSDT","INJUSDT","SEIUSDT","TIAUSDT","MOVEUSDT","STXUSDT","MNXUSDT",
    "BERAUSDT","NIGHTUSDT","HUSDT","ALGOUSDT","SUSDT","RAVEUSDT",
}
L2_SYMS = {
    "ARBUSDT","OPUSDT","STRKUSDT","ZKUSDT","IMXUSDT","LDOUSDT","MATICUSDT",
    "POLUSDT","METISUSDT",
}
DEFI_SYMS = {
    "AAVEUSDT","UNIUSDT","CRVUSDT","COMPUSDT","SNXUSDT","PENDLEUSDT",
    "DYDXUSDT","GRTUSDT","1INCHUSDT","SUSHIUSDT","RUNEUSDT","ONDOUSDT",
    "EIGENUSDT","ETHFIUSDT","STGUSDT","ENSUSDT","FLUIDUSDT","RENDERUSDT",
    "ZEROUSDT","JTOUSDT","JUPUSDT","RAYUSDT","LDOUSDT","ENAUSUSDT","ENAUSDT","COWUSDT","RSRUSDT","STGUSDT","MYXUSDT","FFUSDT","DYDXUSDT","RUNEUSDT","SNXUSDT","1INCHUSDT","SUSHIUSDT",
}
MEME_SYMS = {
    "DOGEUSDT","SHIB1000USDT","1000PEPEUSDT","WIFUSDT","1000BONKUSDT","1000FLOKIUSDT",
    "TRUMPUSDT","PENGUUSDT","MOODENGUSDT","POPCATUSDT","PNUTUSDT","BLURUSDT",
    "SPXUSDT","VVVUSDT","BEATUSDT","STABLEUSDT","WLFIUSDT","NOTUSDT",
    "NIGHTUSDT",
}
AI_SYMS = {
    "TAOUSDT","RENDERUSDT","GRTUSDT","VIRTUALUSDT","IOUSDT","AKTUSDT","ALLOUSDT","ATHUSD","DEEPUSDT","EIGENUSDT","PYTHUSDT",
    "ALLOUSDT","ATHUSD","DEEPUSDT","FLUIDUSDT","FETCHUSDT","AGIXUSDT",
}
GAMING_SYMS = {
    "AXSUSDT","SANDUSDT","GALAUSDT","MANAUSDT","ENJUSDT","IMXUSDT","RAVEUSDT",
}

def get_tier(symbol):
    if symbol in TIER1_SYMS: return "tier1"
    if symbol in TIER2_SYMS: return "tier2"
    return "tier3"

def get_layer(symbol):
    if symbol in L1_SYMS:     return "l1"
    if symbol in L2_SYMS:     return "l2"
    if symbol in DEFI_SYMS:   return "defi"
    if symbol in MEME_SYMS:   return "meme"
    if symbol in AI_SYMS:     return "ai"
    if symbol in GAMING_SYMS: return "gaming"
    return "other"

def get_category(symbol):
    # Explicit commodity set first (most reliable)
    if symbol in CATEGORIES["commodity"]: return "commodity"
    # Strip USDT suffix to get base ticker
    base = symbol.replace("USDT","").replace("STOCK","").upper()
    # Check commodity bases
    if base in COMMODITY_BASES: return "commodity"
    # Check stock tickers
    if symbol in CATEGORIES["stock"]: return "stock"
    if base in STOCK_TICKERS: return "stock"
    # Auto-detect: stock tickers are typically 1-5 uppercase letters, no numbers
    # Crypto symbols often have numbers (1INCH, SHIB1000) or are longer
    # Heuristic: if it's in the Bybit TradFi stock naming pattern
    # (pure alpha, 1-5 chars, not a known crypto) treat as stock
    # This is a fallback — explicit lists above are authoritative
    return "crypto"

NAMES = {
    "BTCUSDT":"Bitcoin","AMDSTOCKUSDT":"AMD","ETHUSDT":"Ethereum","XAUUSDT":"Gold","XAGUSDT":"Silver",
    "SOLUSDT":"Solana","XRPUSDT":"XRP","BNBUSDT":"BNB","CLUSDT":"Crude Oil",
    "DOGEUSDT":"Dogecoin","ADAUSDT":"Cardano","AVAXUSDT":"Avalanche",
    "ETCUSDT":"ETH Classic","TRXUSDT":"TRON","XMRUSDT":"Monero","ZECUSDT":"Zcash",
    "BCHUSDT":"Bitcoin Cash","HYPEUSDT":"Hyperliquid","LTCUSDT":"Litecoin",
    "ARBUSDT":"Arbitrum","OPUSDT":"Optimism","NEARUSDT":"NEAR",
    "LINKUSDT":"Chainlink","DOTUSDT":"Polkadot","INJUSDT":"Injective",
    "TSLAUSDT":"Tesla","NVDAUSDT":"NVIDIA","AAPLUSDT":"Apple",
    "AMDUSDT":"AMD","SPYUSDT":"S&P 500","COINUSDT":"Coinbase",
    "MSFTUSDT":"MSFT","GOOGLUSDT":"Google","GOOGLAUSDT":"Google",
    "INTCUSDT":"INTC","QQQUSDT":"QQQ","ORCLUSDT":"ORCL",
    "AMZNUSDT":"Amazon","METAUSDT":"Meta","NFLXUSDT":"Netflix",
    "CLUSDT":"Crude Oil","NGUSDT":"Nat Gas",
    "ATHUSDT":"Aethir","ALLOUSDT":"Allora","FFUSDT":"Falcon Finance","RIVERUSDT":"River","MYXUSDT":"MYX Finance","COWUSDT":"CoW Protocol","RSRUSDT":"Reserve Rights","STGUSDT":"Stargate","TRUMPUSDT":"Trump","VIRTUALUSDT":"Virtuals","PENGUUSDT":"Pudgy Penguins","ARBUSDT":"Arbitrum","HBARUSDT":"Hedera","1000BONKUSDT":"Bonk","LDOUSDT":"Lido","1000FLOKIUSDT":"FLOKI","EIGENUSDT":"EigenLayer","STRKUSDT":"Starknet","ORDIUSDT":"ORDI","ZKUSDT":"ZKsync","BLURUSDT":"Blur","PNUTUSDT":"Peanut","POPCATUSDT":"Popcat","MOODENGUSDT":"Moo Deng","1INCHUSDT":"1inch","SUSHIUSDT":"SushiSwap","NOTUSDT":"Notcoin","RUNEUSDT":"THORChain","SNXUSDT":"Synthetix","AXSUSDT":"Axie Infinity","SANDUSDT":"The Sandbox","GRTUSDT":"The Graph","PYTHUSDT":"Pyth","DYDXUSDT":"dYdX","CRVUSDT":"Curve","PENDLEUSDT":"Pendle","ETHFIUSDT":"ether.fi","ZEROUSDT":"LayerZero","IOUSDT":"io.net","BERAUSDT":"Berachain","IPUSDT":"Story Protocol","WUSDT":"Wormhole","RAVEUSDT":"RaveDAO","SUSDT":"Sonic","NIGHTUSDT":"Night","NOKIAUSDT":"Nokia","SPCXUSDT":"S&P500 Covered","TSMUSDT":"TSMC",
    "MUUSDT":"Micron","SNDKUSDT":"SanDisk","MSTRUSDT":"MicroStrategy",
    "HOODUSDT":"Robinhood","CRCLUSDT":"Circle","EWJUSDT":"iShares Japan",
    "EWYUSDT":"iShares Korea","HBARUSDT":"Hedera","HUSDT":"Humanity","1000PEPEUSDT":"Pepe","SHIB1000USDT":"Shiba Inu","1000BONKUSDT":"Bonk","1000FLOKIUSDT":"FLOKI",
}
COIN_MAP = {
    # Majors
    "beat":"BEATUSDT","vvv":"VVVUSDT","wlfi":"WLFIUSDT","wld":"WLDUSDT","mnt":"MNTUSDT","ondo":"ONDOUSDT","ena":"ENAUSDT","tao":"TAOUSDT","chz":"CHZUSDT","cro":"CROUSDT","dash":"DASHUSDT","okb":"OKBUSDT","btc":"BTCUSDT","eth":"ETHUSDT","bnb":"BNBUSDT","xrp":"XRPUSDT",
    "sol":"SOLUSDT","ada":"ADAUSDT","doge":"DOGEUSDT","trx":"TRXUSDT",
    "avax":"AVAXUSDT","dot":"DOTUSDT","link":"LINKUSDT","matic":"MATICUSDT",
    "shib":"SHIB1000USDT","ltc":"LTCUSDT","bch":"BCHUSDT","etc":"ETCUSDT",
    "xlm":"XLMUSDT","atom":"ATOMUSDT","near":"NEARUSDT","apt":"APTUSDT",
    "sui":"SUIUSDT","arb":"ARBUSDT","op":"OPUSDT","inj":"INJUSDT",
    "xmr":"XMRUSDT","zec":"ZECUSDT","hype":"HYPEUSDT","pepe":"1000PEPEUSDT",
    "wif":"WIFUSDT","bonk":"BONKUSDT","not":"NOTUSDT","dogs":"DOGSUSDT",
    "mew":"MEWUSDT","jup":"JUPUSDT","ray":"RAYUSDT","ton":"TONUSDT",
    "sei":"SEIUSDT","tia":"TIAUSDT","kas":"KASUSDT","stx":"STXUSDT",
    "ftm":"FTMUSDT","eos":"EOSUSDT","icp":"ICPUSDT","fil":"FILUSDT",
    "aave":"AAVEUSDT","uni":"UNIUSDT","mkr":"MKRUSDT","crv":"CRVUSDT",
    "snx":"SNXUSDT","comp":"COMPUSDT","sushi":"SUSHIUSDT","yfi":"YFIUSDT",
    "rune":"RUNEUSDT","algo":"ALGOUSDT","iota":"IOTAUSDT","hbar":"HBARUSDT",
    "vet":"VETUSDT","theta":"THETAUSDT","neo":"NEOUSDT","waves":"WAVESUSDT",
    "one":"ONEUSDT","gala":"GALAUSDT","sand":"SANDUSDT","mana":"MANAUSDT",
    "axs":"AXSUSDT","imx":"IMXUSDT","flow":"FLOWUSDT","egld":"EGLDUSDT",
    "kava":"KAVAUSDT","cake":"CAKEUSDT","osmo":"OSMOUSDT","lrc":"LRCUSDT",
    "1inch":"1INCHUSDT","enj":"ENJUSDT","cvx":"CVXUSDT","bal":"BALUSDT",
    # Commodities / indices
    "xau":"XAUUSDT","gold":"XAUUSDT","xag":"XAGUSDT","silver":"XAGUSDT",
    "cl":"CLUSDT","oil":"CLUSDT",
    # Stock tokens
    "tsla":"TSLAUSDT","nvda":"NVDAUSDT","aapl":"AAPLUSDT",
    "amd":"AMDSTOCKUSDT","spy":"SPYUSDT","spyusd":"SPYUSDT","msft":"MSFTUSDT",
    "googl":"GOOGLUSDT","google":"GOOGLUSDT","intc":"INTCUSDT",
    "qqq":"QQQUSDT","orcl":"ORCLUSDT","amzn":"AMZNUSDT",
    "meta":"METAUSDT","nflx":"NFLXUSDT","coin":"COINUSDT","coinbase":"COINUSDT",
    "dis":"DISUSDT","sbux":"SBUXUSDT","nike":"NIKEUSDT",
    "ath":"ATHUSDT","rave":"RAVEUSDT","s":"SUSDT","sonic":"SUSDT","night":"NIGHTUSDT","nokia":"NOKIAUSDT","ksm":"KSMUSDT","ens":"ENSUSDT","stg":"STGUSDT","rsr":"RSRUSDT","spx":"SPXUSDT","cow":"COWUSDT","myx":"MYXUSDT","ff":"FFUSDT","river":"RIVERUSDT","trump":"TRUMPUSDT","virtual":"VIRTUALUSDT","pengu":"PENGUUSDT","arb":"ARBUSDT","hbar":"HBARUSDT","bonk":"1000BONKUSDT","ldo":"LDOUSDT","floki":"1000FLOKIUSDT","eigen":"EIGENUSDT","strk":"STRKUSDT","ordi":"ORDIUSDT","zk":"ZKUSDT","blur":"BLURUSDT","pnut":"PNUTUSDT","popcat":"POPCATUSDT","moodeng":"MOODENGUSDT","1inch":"1INCHUSDT","sushi":"SUSHIUSDT","not":"NOTUSDT","rune":"RUNEUSDT","snx":"SNXUSDT","axs":"AXSUSDT","sand":"SANDUSDT","grt":"GRTUSDT","pyth":"PYTHUSDT","dydx":"DYDXUSDT","crv":"CRVUSDT","pendle":"PENDLEUSDT","ethfi":"ETHFIUSDT","zro":"ZEROUSDT","io":"IOUSDT","bera":"BERAUSDT","ip":"IPUSDT","virtual":"VIRTUALUSDT","w":"WUSDT","stable":"STABLEUSDT","aster":"ASTERUSDT","spcx":"SPCXUSDT","myx":"MYXUSDT","ff":"FFUSDT","river":"RIVERUSDT","fluid":"FLUIDUSDT","deep":"DEEPUSDT","allo":"ALLOUSDT","akt":"AKTUSDT","gala":"GALAUSDT","move":"MOVEUSDT","neo":"NEOUSDT","op":"OPUSDT","stg":"STGUSDT","spcx":"SPCXUSDT","tsm":"TSMUSDT",
    "mu":"MUUSDT","sndk":"SNDKUSDT","mstr":"MSTRUSDT",
    "hood":"HOODUSDT","crcl":"CRCLUSDT","ewj":"EWJUSDT","ewy":"EWYUSDT",
    "h":"HUSDT","hbar":"HBARUSDT",
    # Aliases
    "near":"NEARUSDT","ftm":"FTMUSDT",
}

# Symbols already announced via [DISCOVER] — suppresses repeat prints on every poll
_discovered_logged = set()

def sym_from_fname(fname):
    fl = fname.lower()
    # 1. breakout_3m_{coin} pattern
    m = re.search(r'breakout_3m_([a-z0-9]+)', fl)
    if m:
        c = m.group(1)
        return COIN_MAP.get(c, c.upper() + "USDT")
    # 2. {coin}usdt anywhere in filename
    m = re.search(r'([a-z][a-z0-9]+)usdt', fl)
    if m:
        return m.group(1).upper() + "USDT"
    # 3. COIN_MAP key in filename
    for k in sorted(COIN_MAP, key=len, reverse=True):
        # Only match if key appears as a word (before _ or at string start/end)
        if ('_'+k+'_' in '_'+fl+'_'):
            return COIN_MAP[k]
    # 4. Fallback: first part of filename before underscore
    parts = [p for p in fl.split('_') if len(p) >= 2]
    if parts:
        sym = parts[0].upper() + "USDT"
        # Skip generic filenames that aren't real symbols
        if sym in ("MERGEDUSDT","BOTUSDT","TESTUSDT","MAINUSDT","CONFIGUSDT","UNIVERSALUSDT","V2USDT"):
            return None
        return sym
    return None

def discover(directory="."):
    bots = []
    _sf=(sorted(glob.glob(os.path.join(directory,"*_state.json")))+sorted(glob.glob(os.path.join(directory,"*","*_state.json")))+sorted(glob.glob(os.path.join(directory,"*","*","*_state.json"))))
    for fp in _sf:
        try:
            with open(fp) as f: state = json.load(f)
        except: continue
        fname  = os.path.basename(fp).replace("_state.json","")
        symbol = sym_from_fname(fname)
        if not symbol: continue
        fl = fname.lower()
        btype = ("Breakout 3M" if "breakout" in fl else
                 "Merged"      if "merged"   in fl else
                 "Trend Greedy" if "greedy"  in fl else
                 "Trend v3B"    if "v3b"     in fl else
                 "Trend v3"     if "v3"      in fl else "Bot")
        mtime  = os.path.getmtime(fp)
        # Use the most recently touched file (state OR log) as heartbeat
        # Flat bots never rewrite state, but always write logs every loop
        # Search for logs in same dir as state file AND root dir
        state_dir = os.path.dirname(fp)
        log_files = (glob.glob(os.path.join(state_dir, fname+"*.log")) +
                     glob.glob(os.path.join(directory, fname+"*.log")))
        log_files = list(set(log_files))  # deduplicate
        if log_files:
            log_mtime = max(os.path.getmtime(lf) for lf in log_files)
            heartbeat = max(mtime, log_mtime)
        else:
            heartbeat = mtime
        age    = time.time() - heartbeat
        # Estimate run time from file creation time
        try:    run_sec = time.time() - os.path.getctime(fp)
        except: run_sec = age
        # Parse log files for trade history and fees
        log_trades = []
        for lf in (log_files or []):
            log_trades.extend(parse_log(lf))
        log_trades.sort(key=lambda t: t['tout'], reverse=True)
        # Read history JSON for exact Bybit PnL
        hist_file = fp.replace("_state.json", "_history.json")
        hist_trades = []
        if os.path.exists(hist_file):
            try:
                with open(hist_file) as hf: hist_trades = json.load(hf)
            except: pass

        bots.append({
            "symbol":symbol, "name":NAMES.get(symbol, symbol.replace("USDT","")),
            "bot_type":btype, "state":state,
            "age":age, "run_sec":run_sec,
            "log_trades":log_trades,
            "hist_trades":hist_trades,

            "ago":(f"{int(age)}s" if age<60 else f"{int(age//60)}m{int(age%60)}s" if age<3600 else f"{int(age//3600)}h{int((age%3600)//60)}m")+" ago",
            "runtime":(f"{int(run_sec//3600)}h{int((run_sec%3600)//60)}m" if run_sec>=3600
                       else f"{int(run_sec//60)}m" if run_sec>=60
                       else f"{int(run_sec)}s"),
        })
    # Deduplicate — two filenames can resolve to the same symbol (e.g. cl + clusdt)
    seen = {}
    deduped = []
    for b in bots:
        sym = b["symbol"]
        if sym not in seen:
            seen[sym] = True
            deduped.append(b)
        else:
            # Keep the one with more recent state (smaller age)
            for i, existing in enumerate(deduped):
                if existing["symbol"] == sym and b["age"] < existing["age"]:
                    deduped[i] = b
                    break
    # Also add bots with log but no state file (never traded)
    state_syms = {b["symbol"] for b in bots}
    for lp in sorted(glob.glob(os.path.join(directory,"*_merged*.log")) +
                     glob.glob(os.path.join(directory,"*","*_merged*.log")) +
                     glob.glob(os.path.join(directory,"*","*","*_merged*.log"))):
        try:
            base = os.path.basename(lp).replace(".log","")
            symbol = sym_from_fname(base)
            if not symbol or symbol in state_syms: continue
            state_syms.add(symbol)
            mtime = os.path.getmtime(lp)
            log_files2 = glob.glob(os.path.join(directory, base+"*.log"))
            heartbeat2 = max((os.path.getmtime(lf) for lf in log_files2), default=mtime)
            age   = time.time()-max(mtime, heartbeat2)
            try: run_sec = time.time()-os.path.getctime(lp)
            except: run_sec = age
            log_trades = []
            for lf in log_files2:
                try: log_trades.extend(parse_log(lf))
                except: pass
            log_trades.sort(key=lambda t: t.get("tout",""),reverse=True)
            fl = base.lower()
            btype = ("Merged" if "merged" in fl else "Bot")
            bots.append({"symbol":symbol,"name":NAMES.get(symbol,symbol.replace("USDT","")),"bot_type":btype,"state":{"in_trade":False,"wins":0,"losses":0,"total_pnl":0},"age":age,"run_sec":run_sec,"log_trades":log_trades,"hist_trades":[],"ago":(f"{int(age)}s" if age<60 else f"{int(age//60)}m{int(age%60)}s" if age<3600 else f"{int(age//3600)}h{int((age%3600)//60)}m")+" ago","runtime":(f"{int(run_sec//3600)}h{int((run_sec%3600)//60)}m" if run_sec>=3600 else f"{int(run_sec//60)}m" if run_sec>=60 else f"{int(run_sec)}s")})
            if symbol not in _discovered_logged:
                print(f"[DISCOVER] added {symbol} from log (no state file)")
                _discovered_logged.add(symbol)
        except Exception as _e: print(f"[DISCOVER] log scan error: {_e}")
    return deduped

# ── Log parser ──────────────────────────────────────────────────────────────
_ER = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*ENTRY\s+(LONG|SHORT)\s+@\s*([\d.]+)\s+qty=([\d.]+).*SL=([\d.]+)', re.IGNORECASE)
_CR = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*CLOSE[\s\[]([^\]@]*)\]?\s*@\s*([\d.]+).*pnl=([+-]?[\d.]+)', re.IGNORECASE)
_PR = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*(?:PARTIAL|partial).*pnl=([+-]?[\d.]+)', re.IGNORECASE)

# Regex for partial/catch-up closes
_TP1R = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[TP1[\s_].*@.*?([\d.]+).*pnl=([+-]?[\d.]+)', re.IGNORECASE)
_TP2R = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[TP2[\s_].*@.*?([\d.]+).*pnl=([+-]?[\d.]+)', re.IGNORECASE)
_MKR  = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[(TP1|TP2) MARKET\].*@.*?~?([\d.]+)', re.IGNORECASE)
_CTR  = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*CATCH-UP.*SHORT.*closed.*market', re.IGNORECASE)
_SLR  = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*CLOSE.*STOP_LOSS.*@\s*([\d.]+)', re.IGNORECASE)

def parse_log(path):
    trades, pending, ppnl, partials = [], None, 0.0, []
    try:
        with open(path, encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        for line in lines:
            # ── ENTRY ──────────────────────────────────────────────
            m = _ER.search(line)
            if m:
                pending = {'tin':m.group(1),'dir':m.group(2),
                           'entry':float(m.group(3)),'qty':float(m.group(4))}
                ppnl=0.0; partials=[]; continue
            # ── TP1/TP2 MARKET (catch-up) ──────────────────────────
            m = _MKR.search(line)
            if m and pending:
                tp_label = m.group(2).upper()
                px = float(m.group(3))
                partials.append({'tin':pending['tin'],'tout':m.group(1),'qty':pending.get('qty',0),
                    'dir':pending['dir'],'entry':pending['entry'],
                    'close':px,'reason':tp_label,'pnl':0,'won':True})
                continue
            # ── PARTIAL TP detection ────────────────────────────────
            m = _PR.search(line)
            if m and pending:
                ppnl+=abs(float(m.group(2))); continue
            # ── FULL CLOSE ─────────────────────────────────────────
            m = _CR.search(line)
            if m and pending:
                ep=float(m.group(3)); tot=ppnl+float(m.group(4))
                reason=m.group(2).strip() if m.group(2) else 'CLOSE'
                try:
                    ti=datetime.strptime(pending['tin'],'%Y-%m-%d %H:%M:%S')
                    to=datetime.strptime(m.group(1),'%Y-%m-%d %H:%M:%S')
                    ds=int((to-ti).total_seconds())
                    dur=(f"{ds//3600}h{(ds%3600)//60}m" if ds>=3600
                         else f"{ds//60}m{ds%60}s" if ds>=60 else f"{ds}s")
                except: dur="—"
                fee=pending['qty']*pending['entry']*TAKER_FEE*2
                # Add all partials first, then full close
                trades.extend(partials)
                trades.append({'tin':pending['tin'],'tout':m.group(1),'qty':pending.get('qty',0),
                    'dir':pending['dir'],'entry':pending['entry'],
                    'close':ep,'reason':reason,'pnl':round(tot,6),
                    'won':tot>0,'dur':dur,'fee':round(fee,6)})
                pending=None; ppnl=0.0; partials=[]
    except: pass
    return trades

# ── Balance (Bybit HMAC) ─────────────────────────────────────────────────────
# ── Bybit Closed PnL  (exact per-symbol from API) ───────────────
_cpnl_cache = {}   # {symbol: {"ts":float, "list":[...],"total":float}}
_CPNL_TTL   = 60   # seconds between re-fetches per symbol

def _bybit_get(endpoint, params, key, secret):
    """Signed GET to Bybit V5 — query string for signing must exactly match URL."""
    try:
        from urllib.parse import urlencode
        ts  = str(int(time.time()*1000))
        rw  = "5000"
        qs  = urlencode(sorted(params.items()))  # sorted = consistent for signing
        sig = hmac.new(secret.encode(),(ts+key+rw+qs).encode(),hashlib.sha256).hexdigest()
        url = f"{BYBIT_API}{endpoint}?{qs}"
        r   = requests.get(url, timeout=8,
            headers={"X-BAPI-API-KEY":key,"X-BAPI-TIMESTAMP":ts,
                     "X-BAPI-SIGN":sig,"X-BAPI-RECV-WINDOW":rw})
        data = r.json()
        if data.get("retCode") not in (0, None):
            print(f"[Bybit {endpoint}] {data.get('retCode')} {data.get('retMsg','')}")
        return data
    except Exception as e:
        return {"retCode":-1,"retMsg":str(e)}


_bybit_cache = {}; _bybit_cache_ts = 0.0; _bybit_fetching = False

def _bybit_fetch():
    """Do the actual Bybit API calls (run in background thread)."""
    global _bybit_cache, _bybit_cache_ts, _bybit_fetching
    if _bybit_fetching: return
    _bybit_fetching = True
    try:
        key, secret = _load_keys()
        if not key or not secret: return
        out = {"ok":True,"balance":0,"positions":{},"closed":{},
               "total_realized":0,"total_unrealized":0,"wins":0,"losses":0}
        # 1. Balance
        r = _bybit_get("/v5/account/wallet-balance",{"accountType":"UNIFIED"},key,secret)
        if r.get("retCode")==0:
            for acc in r.get("result",{}).get("list",[]):
                if acc.get("accountType")=="UNIFIED":
                    out["balance"] = round(float(acc.get("totalEquity",0)),2); break
        # 2. Open positions
        r2 = _bybit_get("/v5/position/list",{"category":"linear","settleCoin":"USDT"},key,secret)
        if r2.get("retCode")==0:
            for pos in r2.get("result",{}).get("list",[]):
                if float(pos.get("size","0"))>0:
                    sym=pos["symbol"]; upnl=round(float(pos.get("unrealisedPnl",0)),6)
                    out["positions"][sym]={"unrealized":upnl,"side":pos.get("side",""),
                        "size":float(pos.get("size",0)),"avgPrice":round(float(pos.get("avgPrice",0)),6)}
                    out["total_unrealized"]+=upnl
        # 3. Realized PnL — try 3 methods in order
        total_execs=0; pnl_execs=0

        # Method A: execution list (no startTime — gets recent history)
        for attempt, ex_params in enumerate([
            {"category":"linear","limit":200},                          # recent only
            {"category":"linear","limit":200,                           # with startTime
             "startTime":str(int((time.time()-30*24*3600)*1000))},
        ]):
            cursor_a=""
            for _ in range(5):
                p = dict(ex_params); 
                if cursor_a: p["cursor"]=cursor_a
                r3=_bybit_get("/v5/execution/list",p,key,secret)
                if r3.get("retCode")!=0:
                    if attempt==0:
                        print(f"[exec] attempt {attempt} failed: {r3.get('retCode')} {r3.get('retMsg')}")
                    break
                rows=r3.get("result",{}).get("list",[])
                total_execs+=len(rows)
                for t in rows:
                    ep=round(float(t.get("execPnl","0") or 0),6)
                    if ep==0: continue
                    pnl_execs+=1; sym=t.get("symbol","")
                    if not sym: continue
                    if sym not in out["closed"]: out["closed"][sym]={"total":0,"wins":0,"losses":0,"ct":0}
                    out["closed"][sym]["total"]=round(out["closed"][sym]["total"]+ep,6)
                    if ep>0: out["closed"][sym]["wins"]+=1; out["wins"]+=1
                    elif ep<0: out["closed"][sym]["losses"]+=1; out["losses"]+=1
                    out["closed"][sym]["ct"]+=1
                cursor_a=r3.get("result",{}).get("nextPageCursor","")
                if not cursor_a or not rows: break
            if pnl_execs>0: break  # found data, stop trying

        # Method B: closed-pnl fallback (fully closed positions)
        if pnl_execs==0:
            print("[exec] execution list empty — trying closed-pnl fallback")
            for cp_params in [
                {"category":"linear","limit":200},
                {"category":"linear","limit":200,
                 "startTime":str(int((time.time()-30*24*3600)*1000))},
            ]:
                r4=_bybit_get("/v5/position/closed-pnl",cp_params,key,secret)
                if r4.get("retCode")==0:
                    for t in r4.get("result",{}).get("list",[]):
                        sym=t.get("symbol",""); pnl=round(float(t.get("closedPnl","0") or 0),6)
                        if not sym or pnl==0: continue
                        if sym not in out["closed"]: out["closed"][sym]={"total":0,"wins":0,"losses":0,"ct":0}
                        out["closed"][sym]["total"]=round(out["closed"][sym]["total"]+pnl,6)
                        if pnl>0: out["closed"][sym]["wins"]+=1; out["wins"]+=1
                        elif pnl<0: out["closed"][sym]["losses"]+=1; out["losses"]+=1
                        out["closed"][sym]["ct"]+=1; pnl_execs+=1
                    if pnl_execs>0: break

        print(f"[Bybit exec] scanned={total_execs}  with_pnl={pnl_execs}  "
              f"realized={round(sum(d['total'] for d in out['closed'].values()),4)}")
        if total_execs==0:
            # Debug: show raw response to diagnose
            r_dbg=_bybit_get("/v5/execution/list",{"category":"linear","limit":5},key,secret)
            print(f"[exec debug] raw={r_dbg}")
        out["total_realized"]=round(sum(d["total"] for d in out["closed"].values()),6)
        out["total_unrealized"]=round(out["total_unrealized"],6)
        _bybit_cache=out; _bybit_cache_ts=time.time()
        print(f"[Bybit] bal=${out['balance']} real={out['total_realized']:+.4f} trades={out['wins']+out['losses']}")
    except Exception as e:
        print(f"[Bybit fetch error] {e}")
    finally:
        _bybit_fetching=False


def get_bybit_closed_pnl(symbol, limit=50):
    """Fetch exact realized PnL trades for a symbol from Bybit API."""
    global _cpnl_cache
    now = time.time()
    cached = _cpnl_cache.get(symbol)
    if cached and now - cached["ts"] < _CPNL_TTL:
        return cached
    key, secret = _load_keys()
    if not key or not secret:
        return {"ts": now, "list": [], "total": 0.0, "ok": False}
    try:
        ts  = str(int(now * 1000))
        rw  = "5000"
        qs  = f"category=linear&symbol={symbol}&limit={limit}"
        sig = hmac.new(secret.encode(),
                       (ts + key + rw + qs).encode(),
                       hashlib.sha256).hexdigest()
        r = requests.get(
            f"{BYBIT_API}/v5/position/closed-pnl",
            params={"category": "linear", "symbol": symbol, "limit": limit},
            timeout=6,
            headers={"X-BAPI-API-KEY":      key,
                     "X-BAPI-TIMESTAMP":    ts,
                     "X-BAPI-SIGN":         sig,
                     "X-BAPI-RECV-WINDOW":  rw},
        ).json()
        if r.get("retCode") != 0:
            raise ValueError(f"retCode={r.get('retCode')} {r.get('retMsg')}")
        trades = r["result"]["list"]
        # Each entry is one close order (partial or full)
        total  = round(sum(float(t.get("closedPnl", 0)) for t in trades), 6)
        result = {"ts": now, "list": trades, "total": total, "ok": True}
        _cpnl_cache[symbol] = result
        return result
    except Exception as e:
        print(f"\n[PnL/{symbol}] {e}")
        result = {"ts": now, "list": [], "total": 0.0, "ok": False}
        _cpnl_cache[symbol] = result
        return result

# ── API key loader — env vars OR api_keys.txt / .env ────────────
_keys_loaded = False
_keys_warned = False
def _load_keys():
    global _keys_loaded, _keys_warned
    key    = os.environ.get("BYBIT_API_KEY",    "")
    secret = os.environ.get("BYBIT_API_SECRET", "")
    if key and secret:
        if not _keys_loaded:
            _keys_loaded = True
            print("[Keys] loaded from environment variables")
        return key, secret
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for fname in ["api_keys.txt", ".env", "config.txt",
                  os.path.join(script_dir, "api_keys.txt")]:
        if os.path.exists(fname):
            try:
                with open(fname) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"): continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip().strip('"').strip("'")
                            v = v.strip().strip('"').strip("'")
                            if k in ("BYBIT_API_KEY",    "API_KEY"):    key    = v
                            if k in ("BYBIT_API_SECRET", "API_SECRET"): secret = v
                if key and secret:
                    if not _keys_loaded:
                        _keys_loaded = True
                        print(f"[Keys] loaded from {fname}")
                    return key, secret
            except Exception as e:
                pass
    if not key or not secret:
        if not _keys_warned:
            _keys_warned = True
            print(f"[Keys] NOT FOUND — create api_keys.txt in: {script_dir}")
            print("       with lines:  BYBIT_API_KEY=xxx  and  BYBIT_API_SECRET=xxx")
    return key, secret

_bal=0.0; _bal_ts=0.0; _bal_err=""
def get_balance():
    global _bal, _bal_ts, _bal_err
    if _bal>0 and time.time()-_bal_ts<30: return _bal
    if _bal==0 and time.time()-_bal_ts<5:  return _bal
    try:
        key, secret = _load_keys()
        if not key or not secret: return _bal
        ts=str(int(time.time()*1000)); rw="5000"; qs="accountType=UNIFIED"
        sig=hmac.new(secret.encode(),(ts+key+rw+qs).encode(),hashlib.sha256).hexdigest()
        r=requests.get(f"{BYBIT_API}/v5/account/wallet-balance",
            params={"accountType":"UNIFIED"},timeout=5,
            headers={"X-BAPI-API-KEY":key,"X-BAPI-TIMESTAMP":ts,
                     "X-BAPI-SIGN":sig,"X-BAPI-RECV-WINDOW":rw}).json()
        _bal_ts=time.time()
        if r.get("retCode",1)!=0: return _bal
        for acct in r.get("result",{}).get("list",[]):
            for k in ("totalEquity","totalMarginBalance","totalWalletBalance"):
                try:
                    v=float(acct.get(k,"0") or 0)
                    if v>0: _bal=v; print(f"\n[Bal] ${v:.2f}"); return _bal
                except: pass
    except Exception as e:
        print(f"\n[Bal] {e}"); _bal_ts=time.time()-3
    return _bal

_pc={}; _pt=0.0
def get_prices(symbols):
    global _pc, _pt
    if time.time()-_pt < 5: return _pc
    try:
        d = requests.get(f"{BYBIT_API}/v5/market/tickers",
                         params={"category":"linear"}, timeout=5).json()
        p = {}
        for it in d.get("result",{}).get("list",[]):
            s = it.get("symbol","")
            if s in symbols:
                try:
                    p[s]       = float(it["lastPrice"])
                    p[s+"_c"]  = float(it.get("price24hPcnt","0"))*100
                    p[s+"_h"]  = float(it.get("highPrice24h","0"))
                    p[s+"_l"]  = float(it.get("lowPrice24h","0"))
                    p[s+"_v"]  = float(it.get("volume24h","0"))
                    p[s+"_mk"] = float(it.get("markPrice", it["lastPrice"]))
                except: pass
        _pc=p; _pt=time.time(); return p
    except: return _pc

def unreal(state, price):
    if not state.get("in_trade") or not price: return 0.0
    e=state.get("entry_price",0); q=state.get("qty",0); d=state.get("direction","")
    if not e or not q: return 0.0
    return q*(price-e)*(1 if d=="long" else -1)  # qty already has leverage baked in

def generate(bots, px, bal):
    now        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    def _xpnl(b):
        h=b.get("hist_trades",[])
        return sum(t.get("net_pnl",0) for t in h) if h else b["state"].get("total_pnl",0)
    tot_pnl = sum(_xpnl(b) for b in bots)
    tot_wins   = sum(b["state"].get("wins",0)       for b in bots)
    tot_loss   = sum(b["state"].get("losses",0)     for b in bots)
    open_ct    = sum(1 for b in bots if b["state"].get("in_trade"))
    stale_ct   = sum(1 for b in bots if b["age"] > 300)
    tot_unr    = sum(unreal(b["state"],px.get(b["symbol"],0)) for b in bots)
    trades     = tot_wins+tot_loss
    wr         = f"{tot_wins/trades*100:.1f}" if trades>0 else "0.0"
    equity     = tot_pnl+tot_unr
    best       = max(bots, key=_xpnl, default=None)
    worst      = min(bots, key=_xpnl, default=None)
    best_sym   = best["symbol"].replace("USDT","")  if best  else "—"
    worst_sym  = worst["symbol"].replace("USDT","") if worst else "—"
    best_pnl   = max((_xpnl(b) for b in bots), default=0)
    worst_pnl  = min((_xpnl(b) for b in bots), default=0)

    # Fees from log files
    tot_fees = sum(t.get('fee',0) for b in bots for t in b.get('log_trades',[]))
    all_log_ct = sum(len(b.get('log_trades',[])) for b in bots)

    ranked   = sorted(bots, key=_xpnl, reverse=True)
    best_b   = ranked[0]  if ranked else None
    worst_b  = ranked[-1] if ranked else None
    best_sym = best_b["symbol"].replace("USDT","")  if best_b  else "—"
    worst_sym= worst_b["symbol"].replace("USDT","") if worst_b else "—"
    best_pnl = round(best_b["state"].get("total_pnl",0),4)  if best_b  else 0
    worst_pnl= round(worst_b["state"].get("total_pnl",0),4) if worst_b else 0

    import json as _j
    bdata = _j.dumps([{
        "symbol":b["symbol"], "name":b["name"], "bot_type":b["bot_type"], "cat":get_category(b["symbol"]), "tier":get_tier(b["symbol"]), "layer":get_layer(b["symbol"]),
        "in_trade":b["state"].get("in_trade",False),
        "direction":b["state"].get("direction",""),
        "entry":b["state"].get("entry_price",0),
        "sl":b["state"].get("sl_price",0),
        "qty":b["state"].get("qty",0),
        "wins": b["state"].get("wins",0) or sum(1 for t in b.get("log_trades",[]) if t.get("won")),
        "losses": b["state"].get("losses",0) or sum(1 for t in b.get("log_trades",[]) if not t.get("won")),
        "pnl":round(b["state"].get("total_pnl",0),6),
        "log_pnl":round(sum(t.get("pnl",0) for t in b.get("log_trades",[])),6),
        "partial":b["state"].get("partial_done",False),"tp1":b["state"].get("tp1_price",0),"tp2":b["state"].get("tp2_price",0),"tp2_done":b["state"].get("tp2_done",False),
        "trades":[{"dir":t.get("dir",""),"tin":t.get("tin",""),"tout":t.get("tout",""),"entry":t.get("entry",0),"close":t.get("close",0),"pnl":round(t.get("pnl",0),4),"reason":t.get("reason",""),"qty":t.get("qty",0)} for t in b.get("log_trades",[]) if t.get("tin")],
        "price":px.get(b["symbol"],0),
        "mark":px.get(b["symbol"]+"_mk",0),
        "chg24":round(px.get(b["symbol"]+"_c",0),3),
        "high24":px.get(b["symbol"]+"_h",0),
        "low24":px.get(b["symbol"]+"_l",0),
        "vol24":round(px.get(b["symbol"]+"_v",0),2),
        "unreal":round(unreal(b["state"],px.get(b["symbol"],0)),6),
        "runtime":b["runtime"], "ago":b["ago"], "age":b["age"],
        "log_ct":len(b.get("log_trades",[])),
        # TP levels from state (set at entry)
        "tp1_price":b["state"].get("tp1_price",0) or 0,
        "tp2_price":b["state"].get("tp2_price",0) or 0,
        "initial_qty":b["state"].get("initial_qty",0) or 0,
        "tp1_done":bool(b["state"].get("partial_done",False)),
        "tp2_done":bool(b["state"].get("tp2_done",False)),
        # Exact PnL from Bybit history (if tracker running)
        "hist_ct":len(b.get("hist_trades",[])),
        "exact_pnl":round((sum(t.get("net_pnl",0) for t in b.get("hist_trades",[])) or sum(t.get("pnl",0) for t in b.get("log_trades",[]))),6),
        "exact_fees":round(sum(t.get("total_fees",0) for t in b.get("hist_trades",[])),6),
        "exact_funding":round(sum(t.get("funding_fees",0) for t in b.get("hist_trades",[])),6),
        "has_exact":len(b.get("hist_trades",[]))>0 or len(b.get("log_trades",[]))>0,
    } for b in bots])


    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SHACKOBOT</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root{{
  --bg:#000;--s1:#070707;--s2:#0c0c0c;--s3:#111;--s4:#161616;
  --b1:#181818;--b2:#222;--b3:#2c2c2c;
  --tx:#c4c4c4;--tx2:#484848;--tx3:#242424;
  --g:#00e676;--r:#ff3b5c;--o:#ff9500;--y:#ffd60a;--b:#0a84ff;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;background:var(--bg);color:var(--tx);
  font-family:'JetBrains Mono',monospace;font-size:12px;overflow:hidden}}
::-webkit-scrollbar{{width:2px;height:2px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:#1a1a1a;border-radius:1px}}
.col-g{{color:var(--g)}}.col-r{{color:var(--r)}}.col-o{{color:var(--o)}}.col-y{{color:var(--y)}}.col-b{{color:var(--b)}}.col-dim{{color:#2e2e2e}}
/* dots */
.pulse-dot{{width:6px;height:6px;border-radius:50%;background:var(--g);display:inline-block;
  box-shadow:0 0 0 0 rgba(0,230,118,.5);animation:rip 1.8s ease infinite}}
@keyframes rip{{0%{{box-shadow:0 0 0 0 rgba(0,230,118,.5)}}70%{{box-shadow:0 0 0 7px rgba(0,230,118,0)}}100%{{box-shadow:0 0 0 0}}}}
.dot-y{{width:6px;height:6px;border-radius:50%;background:var(--o);display:inline-block}}
.dot-r{{width:6px;height:6px;border-radius:50%;background:var(--r);display:inline-block;
  animation:rip-r .8s step-start infinite}}
@keyframes rip-r{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.dot-dead{{width:6px;height:6px;border-radius:50%;background:#551111;display:inline-block;border:1px solid var(--r)}}
/* shell */
.shell{{display:flex;flex-direction:column;height:100vh}}
/* topbar */
.topbar{{height:46px;background:var(--s1);border-bottom:1px solid var(--b1);
  display:flex;align-items:center;flex-shrink:0}}
.logo-zone{{padding:0 20px;display:flex;align-items:center;gap:10px;
  border-right:1px solid var(--b1);height:100%;flex-shrink:0}}
.logo-mark{{width:28px;height:28px;border:1px solid rgba(0,230,118,.35);border-radius:5px;
  display:flex;align-items:center;justify-content:center;background:rgba(0,230,118,.04)}}
.logo-mark svg{{width:14px;height:14px}}
.logo-main{{font-size:11px;font-weight:700;letter-spacing:3px;color:#fff}}
.logo-sub{{font-size:7px;color:var(--tx3);letter-spacing:3px;margin-top:1px}}
.nav-zone{{
  display:flex;height:100%;
  overflow-x:auto;overflow-y:hidden;
  -webkit-overflow-scrolling:touch;
  scrollbar-width:none;flex:1;
}}
.nav-zone::-webkit-scrollbar{{display:none}}
.nav-btn{{
  padding:0 18px;font-size:10px;letter-spacing:1px;color:var(--tx2);
  cursor:pointer;border-bottom:2px solid transparent;
  border-right:1px solid var(--b1);
  display:flex;align-items:center;gap:7px;transition:all .15s;
  background:transparent;font-family:inherit;
  border-top:none;border-left:none;flex-shrink:0;
}}
.nav-btn:hover{{color:var(--tx)}}
.nav-on{{color:var(--g);border-bottom-color:var(--g)}}
.nct{{font-size:8px;padding:1px 6px;border-radius:10px;background:var(--b1);color:var(--tx2)}}
.nav-on .nct{{background:rgba(0,230,118,.1);color:var(--g)}}
/* Filter pills inside nav-zone */
.nav-flt-sep{{
  width:1px;height:16px;background:#1c1c1c;
  margin:auto 6px;flex-shrink:0;align-self:center;
}}
.nav-flt-btn{{
  padding:0 10px;height:22px;border-radius:11px;
  font-size:9px;letter-spacing:.6px;
  border:1px solid transparent;background:transparent;
  color:#2e2e2e;cursor:pointer;font-family:inherit;
  transition:all .12s;white-space:nowrap;flex-shrink:0;
  align-self:center;touch-action:manipulation;
  -webkit-tap-highlight-color:transparent;
}}
.nav-flt-btn:hover{{color:#666;border-color:#222;background:rgba(255,255,255,.03)}}
.nav-flt-btn:active{{opacity:.6}}
.nav-flt-btn.nav-flt-on,
.nav-flt-btn.flt-on{{
  background:rgba(10,132,255,.15);color:#4da3ff;
  border-color:rgba(10,132,255,.4);
}}
.nav-flt-btn.flt-danger{{color:#2a1010}}
.nav-flt-btn.flt-danger.flt-on{{
  background:rgba(255,59,92,.15);color:#ff3b5c;
  border-color:rgba(255,59,92,.4);
}}
.nav-flt-btn.flt-t1.flt-on{{background:rgba(0,230,118,.12);color:#00e676;border-color:rgba(0,230,118,.35)}}
.nav-flt-btn.flt-t2.flt-on{{background:rgba(255,214,10,.1);color:#ffd60a;border-color:rgba(255,214,10,.3)}}
.nav-flt-btn.flt-t3.flt-on{{background:rgba(255,149,0,.1);color:#ff9500;border-color:rgba(255,149,0,.3)}}
.topbar-right{{margin-left:auto;display:flex;align-items:center;gap:14px;padding:0 20px}}
.live-pill{{display:flex;align-items:center;gap:6px;padding:4px 10px;
  border:1px solid rgba(0,230,118,.15);border-radius:20px;background:rgba(0,230,118,.03)}}
.live-txt{{font-size:8px;letter-spacing:3px;color:var(--g)}}
.topbar-clock{{font-size:11px;color:var(--tx3)}}
/* metrics strip */
.metrics-row{{height:56px;background:var(--s1);border-bottom:1px solid var(--b1);
  display:flex;flex-shrink:0;overflow-x:auto}}
.metrics-row::-webkit-scrollbar{{height:0}}
.met{{padding:0 20px;border-right:1px solid var(--b1);display:flex;
  flex-direction:column;justify-content:center;min-width:120px;flex-shrink:0}}
.met-l{{font-size:7px;letter-spacing:2px;text-transform:uppercase;color:var(--tx3);margin-bottom:4px}}
.met-v{{font-size:15px;font-weight:700;line-height:1;white-space:nowrap}}
.met-s{{font-size:8px;color:var(--tx3);margin-top:3px;white-space:nowrap}}
/* body */
.body-row{{display:flex;flex:1;overflow:hidden}}
.main-content{{flex:1;display:flex;flex-direction:column;overflow:hidden}}
.view{{flex:1;display:none;flex-direction:column;overflow:hidden}}
/* BOT LIST VIEW (overview) */
.list-wrap{{flex:1;overflow-y:auto}}
.bot-table{{width:100%;border-collapse:collapse}}
.bot-table thead{{background:var(--s2);position:sticky;top:0;z-index:5}}
.bot-table th{{padding:10px 16px;text-align:left;font-size:8px;letter-spacing:1.5px;
  text-transform:uppercase;color:var(--tx2);border-bottom:1px solid var(--b1);
  white-space:nowrap;font-weight:500}}
.bot-table td{{padding:12px 16px;border-bottom:1px solid #0a0a0a;vertical-align:middle}}
.bot-table tbody tr{{cursor:pointer;transition:background .1s}}
.bot-table tbody tr:hover td{{background:var(--s2)}}
/* long/short row accent */
.row-long td:first-child{{border-left:2px solid rgba(0,230,118,.5)}}
.row-short td:first-child{{border-left:2px solid rgba(255,59,92,.5)}}
.row-flat td:first-child{{border-left:2px solid transparent}}
/* badges */
.card-badge{{font-size:8px;padding:2px 7px;border-radius:2px;font-weight:700;letter-spacing:.5px;white-space:nowrap}}
.cb-long{{background:rgba(0,230,118,.08);color:var(--g);border:1px solid rgba(0,230,118,.2)}}
.cb-short{{background:rgba(255,59,92,.08);color:var(--r);border:1px solid rgba(255,59,92,.2)}}
.cb-flat{{background:rgba(30,30,30,.8);color:#383838;border:1px solid var(--b1)}}
.num{{font-family:'JetBrains Mono',monospace}}
/* Bot row inline tags */
.bot-tag{{font-size:6px;padding:1px 3px;border-radius:2px;margin-left:2px;
  font-family:'JetBrains Mono',monospace;vertical-align:middle;letter-spacing:.2px;
  display:inline-block;line-height:1.4;}}
.tag-stock{{background:rgba(255,149,0,.08);color:#5a3a10}}
.tag-commod{{background:rgba(255,214,10,.06);color:#4a4010}}
.tag-t1{{background:rgba(0,230,118,.06);color:#1a4a28}}
.tag-t2{{background:transparent;color:#252525;border:1px solid #1a1a1a}}
.tag-layer{{background:transparent;color:#222}}
/* wr bar in table */
.wr-row{{display:flex;align-items:center;gap:7px}}
.wr-bg{{flex:1;height:2px;background:var(--b1);border-radius:1px;overflow:hidden;min-width:50px}}
.wr-bar-f{{height:100%;border-radius:1px}}
/* data views (positions, history) */
.data-view{{flex:1;overflow-y:auto;padding:24px 28px}}
.dv-head{{display:flex;align-items:baseline;gap:14px;margin-bottom:20px;
  padding-bottom:14px;border-bottom:1px solid var(--b1)}}
.dv-title{{font-size:17px;font-weight:700;letter-spacing:.5px;color:#fff}}
.dv-ct{{font-size:10px;color:var(--tx3)}}
.dt{{width:100%;border-collapse:collapse}}
.dt thead tr{{background:var(--s2)}}
.dt th{{padding:9px 14px;text-align:left;font-size:8px;letter-spacing:1.5px;
  text-transform:uppercase;color:var(--tx2);font-weight:500;border-bottom:1px solid var(--b1);white-space:nowrap}}
.dt td{{padding:11px 14px;border-bottom:1px solid #0a0a0a;vertical-align:middle;font-size:11px}}
.dt tbody tr:hover td{{background:var(--s2);cursor:pointer}}
.dt td.num{{font-family:'JetBrains Mono',monospace}}
.empty-s{{display:none;flex-direction:column;align-items:center;justify-content:center;
  height:280px;gap:10px;color:var(--tx3);font-size:12px}}
/* modal */
#modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:1000;backdrop-filter:blur(4px)}}
#chart-modal{{display:none;position:fixed;z-index:1001;
  top:4vh;left:4vw;right:4vw;bottom:4vh;
  background:var(--s1);border:1px solid var(--b2);border-radius:6px;
  flex-direction:column;overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,.9)}}
.cm-topbar{{display:flex;align-items:center;background:var(--s2);border-bottom:1px solid var(--b1);flex-shrink:0;height:52px}}
.cm-sym-block{{padding:0 16px;border-right:1px solid var(--b1);display:flex;flex-direction:column;justify-content:center;min-width:160px;height:100%}}
.cm-sym-name{{font-size:14px;font-weight:700;color:#fff}}
.cm-sym-sub{{font-size:9px;color:var(--tx3);margin-top:2px}}
.cm-price-block{{padding:0 16px;border-right:1px solid var(--b1);display:flex;flex-direction:column;justify-content:center;height:100%}}
.cm-price-v{{font-size:18px;font-weight:700}}
.cm-chg{{font-size:10px;margin-top:2px}}
.cm-stats-row{{display:flex;flex:1;overflow:hidden;height:100%}}
.cm-stat{{padding:0 14px;border-right:1px solid var(--b1);display:flex;flex-direction:column;justify-content:center;flex-shrink:0}}
.cm-stat-l{{font-size:7px;text-transform:uppercase;letter-spacing:1.5px;color:var(--tx3);margin-bottom:3px}}
.cm-stat-v{{font-size:11px;font-weight:600}}
.cm-status-badge{{padding:0 14px;display:flex;align-items:center;flex-shrink:0}}
.cm-close{{margin-left:auto;width:52px;height:52px;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:18px;color:var(--tx2);border-left:1px solid var(--b1);transition:all .12s;background:transparent;border-top:none;border-right:none;border-bottom:none;font-family:inherit}}
.cm-close:hover{{color:var(--r);background:rgba(255,59,92,.08)}}
.cm-badge{{font-size:9px;padding:3px 10px;border-radius:2px;font-weight:700;letter-spacing:.5px}}
.cm-controls{{display:flex;align-items:center;padding:6px 12px;gap:3px;background:var(--s2);border-bottom:1px solid var(--b1);flex-shrink:0}}
.tf-btn{{font-size:9px;padding:3px 9px;border-radius:2px;border:1px solid transparent;background:transparent;color:var(--tx2);cursor:pointer;font-family:inherit;letter-spacing:.5px;transition:all .12s}}
.tf-btn:hover{{color:var(--tx)}}
.tf-on{{background:rgba(255,214,10,.08);color:var(--y);border-color:rgba(255,214,10,.25)}}
.flt-on{{background:rgba(0,132,255,.1);color:var(--b);border-color:rgba(0,132,255,.3);border:1px solid rgba(0,132,255,.3)}}
/* flt-btn fallback (unused but kept for safety) */
.flt-btn.flt-on{{background:rgba(10,132,255,.15);color:#4da3ff;border-color:rgba(10,132,255,.35)}}
/* Mobile */
@media(max-width:768px){{
  .hide-mobile{{display:none!important}}
  /* Topbar — compact */
  .topbar{{height:44px}}
  .logo-zone{{padding:0 12px;gap:7px}}
  .logo-mark{{width:24px;height:24px}}
  .logo-sub{{display:none}}
  .logo-main{{font-size:9px;letter-spacing:2px}}
  .nav-btn{{padding:0 12px;font-size:9px;letter-spacing:.5px}}
  .nct{{font-size:7px;padding:1px 4px}}
  .topbar-right{{padding:0 8px;gap:6px}}
  .live-pill{{padding:3px 7px;gap:4px}}
  .live-txt{{font-size:7px;letter-spacing:2px}}
  .topbar-clock{{font-size:9px}}

  /* Metrics — 3-column compact grid */
  .metrics-row{{
    height:auto;flex-wrap:wrap;
    display:grid;grid-template-columns:repeat(3,1fr);
    border-bottom:1px solid var(--b1);
  }}
  .met{{
    min-width:0;padding:8px 10px;
    border-right:1px solid var(--b1);border-bottom:1px solid var(--b1);
  }}
  .met-v{{font-size:13px}}
  .met-l{{font-size:6px;letter-spacing:1.5px}}
  .met-s{{font-size:7px}}

  /* Bot table — mobile: Symbol | Status | Price | 24h only */
  .bot-table th:nth-child(n+5),
  .bot-table td:nth-child(n+5) {{display:none}}
  .bot-table td:first-child b{{font-size:13px;letter-spacing:.3px}}
  .bot-table td{{padding:10px 10px;font-size:11px}}
  .card-badge{{font-size:7px;padding:2px 7px;letter-spacing:.3px}}
  /* Make status badge wider tap area */
  .bot-table td:nth-child(2){{min-width:70px}}
  /* Price col */
  .bot-table td:nth-child(3){{font-size:12px;font-weight:700}}
}}
@keyframes px-up{{0%{{color:#00e676}}100%{{color:inherit}}}}
@keyframes px-dn{{0%{{color:#ff3b5c}}100%{{color:inherit}}}}
.px-up{{animation:px-up .4s ease-out}}
.px-dn{{animation:px-dn .4s ease-out}}
.cm-chart-area{{flex:1;position:relative;overflow:hidden;background:#030303}}
#cm-chart{{width:100%;height:100%}}
.cm-spin{{display:none;position:absolute;top:50%;left:50%;width:22px;height:22px;margin:-11px;border:2px solid var(--b2);border-top-color:var(--y);border-radius:50%;animation:spin .6s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.cm-trade-bar{{background:var(--s2);border-top:1px solid var(--b1);display:flex;overflow-x:auto;min-height:38px;align-items:stretch;flex-shrink:0}}
.cm-trade-bar::-webkit-scrollbar{{height:0}}
.cm-tb-item{{padding:0 14px;border-right:1px solid var(--b1);display:flex;flex-direction:column;justify-content:center;gap:2px;flex-shrink:0}}
.cm-tb-l{{font-size:7px;text-transform:uppercase;letter-spacing:1.5px;color:var(--tx3)}}
.cm-tb-v{{font-size:11px;font-weight:600}}
@media(max-width:900px){{.cm-stats-row .cm-stat:nth-child(n+5){{display:none}}}}
</style>
</head>
<body>
<div class="shell">

<div class="topbar">
  <div class="logo-zone">
    <div class="logo-mark">
      <svg viewBox="0 0 14 14" fill="none">
        <polyline points="1,11 4,7 7,9 10.5,3.5 13,6"
          stroke="#00e676" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <div>
      <div class="logo-main">SHACKOBOT</div>
      <div class="logo-sub">BOT TERMINAL</div>
    </div>
  </div>
  <div class="nav-zone">
    <button class="nav-btn nav-on" id="nb-overview"  onclick="goView('overview')">Overview  <span class="nct">{len(bots)}</span></button>
    <button class="nav-btn"        id="nb-positions" onclick="goView('positions')">Positions <span class="nct">{open_ct}</span></button>
    <button class="nav-btn"        id="nb-history"   onclick="goView('history')">History   <span class="nct">{all_log_ct}</span></button>
    <div class="nav-flt-sep"></div>
    <button id="flt-all"       onclick="setFilter('all')"       class="nav-flt-btn flt-on">ALL</button>
    <button id="flt-trading"   onclick="setFilter('trading')"   class="nav-flt-btn">TRADE</button>
    <button id="flt-flat"      onclick="setFilter('flat')"      class="nav-flt-btn">FLAT</button>
    <button id="flt-stale"     onclick="setFilter('stale')"     class="nav-flt-btn flt-danger">STALE</button>
    <div class="nav-flt-sep"></div>
    <button id="flt-crypto"    onclick="setFilter('crypto')"    class="nav-flt-btn">CRYPTO</button>
    <button id="flt-stock"     onclick="setFilter('stock')"     class="nav-flt-btn">STOCK</button>
    <button id="flt-commodity" onclick="setFilter('commodity')" class="nav-flt-btn">COMMOD</button>
    <div class="nav-flt-sep"></div>
    <button id="flt-tier1"     onclick="setFilter('tier1')"     class="nav-flt-btn flt-t1">T1</button>
    <button id="flt-tier2"     onclick="setFilter('tier2')"     class="nav-flt-btn flt-t2">T2</button>
    <button id="flt-tier3"     onclick="setFilter('tier3')"     class="nav-flt-btn flt-t3">T3</button>
    <div class="nav-flt-sep"></div>
    <button id="flt-l1"        onclick="setFilter('l1')"        class="nav-flt-btn">L1</button>
    <button id="flt-l2"        onclick="setFilter('l2')"        class="nav-flt-btn">L2</button>
    <button id="flt-defi"      onclick="setFilter('defi')"      class="nav-flt-btn">DEFI</button>
    <button id="flt-meme"      onclick="setFilter('meme')"      class="nav-flt-btn">MEME</button>
    <button id="flt-ai"        onclick="setFilter('ai')"        class="nav-flt-btn">AI</button>
    <button id="flt-gaming"    onclick="setFilter('gaming')"    class="nav-flt-btn">GAME</button>
  </div>
  <div class="topbar-right">
    <div class="live-pill" id="live-pill">
      <div class="pulse-dot" style="width:5px;height:5px"></div>
      <div class="live-txt">LIVE</div>
    </div>
    <div>
      <div class="topbar-clock" id="clock">--:--:--</div>
      <div style="font-size:8px;color:var(--tx3);text-align:right" class="hide-mobile">{now[:10]}</div>
    </div>
  </div>
</div>

<div class="metrics-row">
  <div class="met" style="min-width:140px">
    <div class="met-l">Balance</div>
    <div class="met-v {'col-g' if bal>0 else 'col-dim'} num" id=\"m-bal\">{'$'+f'{bal:.2f}' if bal>0 else '$--'}</div>
    <div class="met-s">{'Bybit UNIFIED' if bal>0 else 'set api_keys.txt'}</div>
  </div>
  <div class="met">
    <div class="met-l">Realised PnL</div>
    <div class="met-v {'col-g' if tot_pnl>=0 else 'col-r'} num" id="m-rpnl">${'{:+.4f}'.format(tot_pnl)}</div>
    <div class="met-s">{trades} closed</div>
  </div>
  <div class="met">
    <div class="met-l">Unrealised</div>
    <div class="met-v {'col-g' if tot_unr>=0 else 'col-r'} num" id="m-upnl">${'{:+.4f}'.format(tot_unr)}</div>
    <div class="met-s">{open_ct} open</div>
  </div>

  <div class="met">
    <div class="met-l">Win Rate</div>
    <div class="met-v {'col-g' if float(wr)>=50 else 'col-o' if float(wr)>=35 else 'col-r'} num" id=\"m-wr\">{wr}%</div>
    <div class="met-s" id=\"m-wl\">{tot_wins}W · {tot_loss}L</div>
  </div>
  <div class="met">
    <div class="met-l">Best Bot</div>
    <div class="met-v col-g" style="font-size:13px" id="m-best">{best_sym}</div>
    <div class="met-s">${'{:+.4f}'.format(best_pnl)}</div>
  </div>
  <div class="met">
    <div class="met-l">Worst Bot</div>
    <div class="met-v col-r" style="font-size:13px" id="m-worst">{worst_sym}</div>
    <div class="met-s">${'{:.4f}'.format(worst_pnl)}</div>
  </div>
  <div class="met">
    <div class="met-l">Bots</div>
    <div class="met-v col-y num">{len(bots)}</div>
    <div class="met-s">{open_ct} trading</div>
  </div>
  <div class="met" id="stale-met">
    <div class="met-l">Stale / Down</div>
    <div class="met-v {'col-r' if stale_ct>0 else 'col-dim'} num" id="m-stale">{stale_ct}</div>
    <div class="met-s">{'click STALE filter' if stale_ct>0 else 'all OK'}</div>
  </div>
  <div class="met">
    <div class="met-l">Last Update</div>
    <div class="met-v num" style="font-size:11px;color:#2a2a2a">{now[11:]}</div>
    <div class="met-s">{REFRESH_SEC}s refresh</div>
  </div>
</div>

<div class="body-row">
<div class="main-content">

  <!-- OVERVIEW: BOT LIST -->
  <div class="view" id="vw-overview" style="display:flex">
    <div class="list-wrap">
      <table class="bot-table">
        <thead><tr>
          <th>Symbol</th>
          <th>Status</th>
          <th>Price</th>
          <th>24h</th>
          <th>Entry</th>
          <th>Move</th>
          <th>Unreal</th>
          <th>PnL</th>
          <th>W / L</th>
          <th>Win Rate</th>
          <th>Runtime</th>
          <th>Updated</th>
        </tr></thead>
        <tbody id="bot-list-body"></tbody>
      </table>
      <div id="filter-info" style="font-size:9px;color:#333;padding:6px 16px;letter-spacing:1px"></div>

      </table>
    </div>
  </div>

  <!-- POSITIONS -->
  <div class="view" id="vw-positions">
    <div class="data-view">
      <div class="dv-head">
        <div class="dv-title">Open Positions</div>
        <div class="dv-ct" id="pos-count">—</div>
      </div>
      <div class="empty-s" id="pos-empty">
        <div style="font-size:30px;opacity:.15">◻</div>
        <div>No open positions right now</div>
      </div>
      <table class="dt"><thead><tr>
        <th>Symbol</th><th>Dir</th><th>Entry</th><th>Mark</th>
        <th>SL / BE</th><th>SL%</th><th>TP1</th><th>TP2</th>
        <th>Move</th><th>Unrealised</th><th>Size</th>
        <th>TP1</th><th>TP2</th><th>Runtime</th><th>Updated</th>
      </tr></thead><tbody id="pos-body"></tbody></table>
    </div>
  </div>

  <!-- HISTORY -->
  <div class="view" id="vw-history">
    <div class="data-view">
      <div class="dv-head">
        <div class="dv-title">Trade History</div>
        <div class="dv-ct">All bots · sorted by PnL</div>
      </div>
      <table class="dt"><thead><tr>
        <th>Symbol</th><th>Type</th><th>Status</th><th>Trades</th>
        <th>Wins</th><th>Losses</th><th>Win Rate</th>
        <th>PnL (log est.)</th><th>Exact PnL (Bybit)</th><th>Exact Fees</th><th>Funding</th><th>Log Trades</th><th>Runtime</th><th>Updated</th>
      </tr></thead><tbody id="hist-body"></tbody></table>
    </div>
  </div>

</div>
</div>

<!-- MODAL OVERLAY -->
<div id="modal-overlay" onclick="closeChart()"></div>

<!-- CHART MODAL -->
<div id="chart-modal">
  <div class="cm-topbar">
    <div class="cm-sym-block">
      <div class="cm-sym-name" id="cm-sym">—</div>
      <div class="cm-sym-sub" id="cm-name">—</div>
    </div>
    <div class="cm-price-block">
      <div class="cm-price-v" id="cm-price">—</div>
      <div class="cm-chg" id="cm-chg">—</div>
    </div>
    <div class="cm-stats-row">
      <div class="cm-stat"><div class="cm-stat-l">24h High</div><div class="cm-stat-v col-g" id="cm-high">—</div></div>
      <div class="cm-stat"><div class="cm-stat-l">24h Low</div><div class="cm-stat-v col-r" id="cm-low">—</div></div>
      <div class="cm-stat"><div class="cm-stat-l">Volume</div><div class="cm-stat-v" id="cm-vol">—</div></div>
      <div class="cm-stat"><div class="cm-stat-l">Entry</div><div class="cm-stat-v" id="cm-entry">—</div></div>
      <div class="cm-stat"><div class="cm-stat-l">SL / BE</div><div class="cm-stat-v col-r" id="cm-sl">—</div></div>
      <div class="cm-stat"><div class="cm-stat-l">TP1</div><div class="cm-stat-v col-y" id="cm-tp1">—</div></div>
      <div class="cm-stat"><div class="cm-stat-l">TP2</div><div class="cm-stat-v col-y" id="cm-tp2">—</div></div>
      <div class="cm-stat"><div class="cm-stat-l">Unrealised</div><div class="cm-stat-v" id="cm-unreal">—</div></div>
      <div class="cm-stat"><div class="cm-stat-l">Win Rate</div><div class="cm-stat-v col-b" id="cm-wr">—</div></div>
      <div class="cm-stat"><div class="cm-stat-l">Total PnL</div><div class="cm-stat-v" id="cm-pnl">—</div></div>
      <div class="cm-stat"><div class="cm-stat-l">Runtime</div><div class="cm-stat-v col-dim" id="cm-runtime">—</div></div>
    </div>
    <div class="cm-status-badge" id="cm-status" style="padding:0 14px;display:flex;align-items:center"></div>
    <button class="cm-close" onclick="closeChart()">✕</button>
  </div>
  <div class="cm-controls">
    <button class="tf-btn" data-tf="1"   onclick="setTF(this)">1m</button>
    <button class="tf-btn" data-tf="3"   onclick="setTF(this)">3m</button>
    <button class="tf-btn tf-on" data-tf="5" onclick="setTF(this)">5m</button>
    <button class="tf-btn" data-tf="15"  onclick="setTF(this)">15m</button>
    <button class="tf-btn" data-tf="30"  onclick="setTF(this)">30m</button>
    <button class="tf-btn" data-tf="60"  onclick="setTF(this)">1h</button>
    <button class="tf-btn" data-tf="240" onclick="setTF(this)">4h</button>
    <button class="tf-btn" data-tf="D"   onclick="setTF(this)">1D</button>
    <span style="margin-left:14px;font-size:8px;color:#222;letter-spacing:1px">ENTRY · SL · TP1 · BE</span>
    <span style="margin-left:8px;font-size:8px;color:#1a1a1a">Partial: <span id="cm-partial" style="color:#444">—</span></span>
    <span style="margin-left:auto;font-size:8px;color:#1e1e1e">ESC or click outside</span>
  </div>
  <div class="cm-chart-area">
    <div id="cm-chart"></div>
    <div class="cm-spin" id="cm-spin"></div>
  </div>
  <div id="signal-debug" style="background:#070707;border-top:1px solid #111;padding:4px 12px;font-size:9px;display:flex;align-items:center;flex-shrink:0;height:22px;overflow:hidden">Loading...</div>
  <div style="background:#050505;border-top:1px solid var(--b1);max-height:160px;overflow-y:auto;flex-shrink:0" id="cm-bybit-trades"></div>
  <div class="cm-trade-bar">
    <div class="cm-tb-item"><div class="cm-tb-l">Status</div><div class="cm-tb-v" id="cm-status-bar">—</div></div>
    <div class="cm-tb-item"><div class="cm-tb-l">Qty</div><div class="cm-tb-v" id="cm-qty">—</div></div>
    <div class="cm-tb-item"><div class="cm-tb-l">W / L</div><div class="cm-tb-v" id="cm-wl">—</div></div>
    <div class="cm-tb-item"><div class="cm-tb-l">Bot Type</div><div class="cm-tb-v" id="cm-type" style="color:#444">—</div></div>
    <div class="cm-tb-item" style="margin-left:auto;border-left:1px solid var(--b1);border-right:none">
      <div class="cm-tb-l">Last Update</div><div class="cm-tb-v" id="cm-ago" style="color:#444">—</div>
    </div>
  </div>
</div>

<script>window._BD_={bdata};</script>
<script>
const B=window._BD_;
// Always use exact Bybit PnL when history file is present
function getPnl(b){{if(b.has_exact&&b.exact_pnl!==0)return b.exact_pnl;if(b.pnl!==0)return b.pnl;return+(b.log_pnl)||0;}}
function getPnlLabel(b){{return b.has_exact?'exact':'est';}}
function getFees(b){{return b.has_exact?b.exact_fees:(b.log_ct||0)*0.00055*2;}}
function getFunding(b){{return b.has_exact?b.exact_funding:0;}}
const API='https://api.bybit.com';
let TF='5',chart=null,macdChart=null,cS=null,vS=null,PL=[],activeView='overview';
let e20S=null,e50S=null,e100S=null,e200S=null,macdHS=null,macdLS=null,macdSS=null,_liveBar=null,_lastHABar=null,_lastSMAs=null;

function dp(p){{if(!p)return 2;if(p<0.0001)return 8;if(p<0.001)return 6;if(p<0.01)return 5;if(p<1)return 4;if(p<10)return 3;if(p<10000)return 2;return 1;}}
function fc(p){{if(!p&&p!==0)return '--';var d=dp(Math.abs(p));return '$'+Math.abs(p).toLocaleString('en',{{minimumFractionDigits:d,maximumFractionDigits:d}});}}
function fv(v){{if(!v)return '--';if(v>1e9)return(v/1e9).toFixed(2)+'B';if(v>1e6)return(v/1e6).toFixed(2)+'M';if(v>1e3)return(v/1e3).toFixed(2)+'K';return v.toFixed(0);}}
function el(id){{return document.getElementById(id);}}

function tick(){{var e=el('clock');if(e)e.textContent=new Date().toLocaleTimeString('en-GB',{{hour12:false}});}}
setInterval(tick,1000);tick();

function goView(v){{
  activeView=v;
  document.querySelectorAll('.nav-btn').forEach(function(n){{n.classList.remove('nav-on');}});
  var nb=el('nb-'+v);if(nb)nb.classList.add('nav-on');
  document.querySelectorAll('.view').forEach(function(x){{x.style.display='none';}});
  var vw=el('vw-'+v);if(vw)vw.style.display='flex';
  if(v==='positions')renderPos();
  if(v==='history')renderHist();
}}

/* FILTER — watchdog-style: status + category */
var _activeFilter='all';
// A bot is STALE if its state file hasn't been touched in >300s (5 min)
// This mirrors watchdog.py crash detection (bot has stopped writing state)
function getBotStatus(b){{
  if(b.in_trade) return 'trading';
  if(b.age>300)  return 'stale';
  return 'flat';
}}
function setCounts(){{
  var cats={{all:B.length,trading:0,flat:0,stale:0,crypto:0,stock:0,commodity:0,
             tier1:0,tier2:0,tier3:0,l1:0,l2:0,defi:0,meme:0,ai:0,gaming:0}};
  B.forEach(function(b){{
    var s=getBotStatus(b);
    if(cats[s]!==undefined) cats[s]++;
    if(cats[b.cat]!==undefined) cats[b.cat]++;
    if(b.tier&&cats[b.tier]!==undefined) cats[b.tier]++;
    if(b.layer&&cats[b.layer]!==undefined) cats[b.layer]++;
  }});
  var labels={{
    all:'ALL', trading:'▲▼ TRADE', flat:'— FLAT', stale:'⚠ STALE',
    crypto:'₿ CRYPTO', stock:'STOCK', commodity:'COMMOD',
    tier1:'T1', tier2:'T2', tier3:'T3',
    l1:'L1', l2:'L2', defi:'DeFi', meme:'Meme', ai:'AI', gaming:'Game'
  }};
  ['all','trading','flat','stale','crypto','stock','commodity',
   'tier1','tier2','tier3','l1','l2','defi','meme','ai','gaming'].forEach(function(c){{
    var btn=el('flt-'+c);
    if(!btn)return;
    var n=cats[c];
    btn.style.opacity=n>0?'1':'0.35';
    btn.disabled=false;
    btn.textContent=labels[c]+' ('+n+')';
  }});
  // Pulse the STALE button red if any bots are stale
  var sb=el('flt-stale');
  if(sb){{
    if(cats.stale>0&&_activeFilter!=='stale'){{
      sb.style.borderColor='rgba(255,59,92,.5)';
      sb.style.color='#ff3b5c';
    }} else if(_activeFilter!=='stale'){{
      sb.style.borderColor='';
      sb.style.color='';
    }}
  }}
}}
function setFilter(f){{
  _activeFilter=f;
  document.querySelectorAll('.flt-btn,.nav-flt-btn').forEach(function(b){{b.classList.remove('flt-on');}});
  var fb=el('flt-'+f);if(fb)fb.classList.add('flt-on');
  // Show/hide rows — status filters check data-status; category filters check data-cat
  var shown=0,total=0;
  var tierFilters=['tier1','tier2','tier3'];
  var layerFilters=['l1','l2','defi','meme','ai','gaming'];
  var catFilters=['crypto','stock','commodity'];
  var statusFilters=['trading','flat','stale'];
  document.querySelectorAll('#bot-list-body tr').forEach(function(r){{
    var show;
    if(f==='all') show=true;
    else if(statusFilters.indexOf(f)>=0) show=(r.dataset.status===f);
    else if(catFilters.indexOf(f)>=0) show=(r.dataset.cat===f);
    else if(tierFilters.indexOf(f)>=0) show=(r.dataset.tier===f);
    else if(layerFilters.indexOf(f)>=0) show=(r.dataset.layer===f);
    else show=true;
    r.style.display=show?'':'none';
    if(show)shown++; total++;
  }});
  var info=el('filter-info');
  if(info){{
    if(f==='all') info.textContent='';
    else if(f==='stale'&&shown>0) info.textContent='⚠ '+shown+' bots not responding (state file >5 min old) — may be crashed';
    else info.textContent='Showing '+shown+' of '+total+' bots · '+f.toUpperCase();
  }}
}}

/* BOT LIST — main overview table */
function renderBotList(){{
  var tb=el('bot-list-body');
  if(!tb)return;
  if(!B.length){{
    tb.innerHTML='<tr><td colspan="13" style="padding:40px;text-align:center;color:#2a2a2a">No bots detected — ensure *_state.json files are in the same folder</td></tr>';
    return;
  }}
  var html='';
  B.forEach(function(b,i){{
    var t=b.wins+b.losses,wr=t>0?(b.wins/t*100):0;
    var wrc=wr>=50?'var(--g)':wr>=35?'var(--o)':'var(--r)';
    var d=dp(b.price);
    var dotcls=b.age<30?'pulse-dot':b.age<120?'dot-y':b.age<300?'dot-r':'dot-dead';
    var rowcls=b.in_trade&&b.direction==='long'?'row-long':b.in_trade&&b.direction==='short'?'row-short':'row-flat';
    var badge=b.in_trade&&b.direction==='long'?'<span class="card-badge cb-long">▲ LONG</span>'
              :b.in_trade&&b.direction==='short'?'<span class="card-badge cb-short">▼ SHORT</span>'
              :'<span class="card-badge cb-flat">— FLAT</span>';
    var chgCls=b.chg24>=0?'col-g':'col-r';
    var entry=b.in_trade&&b.entry?fc(b.entry):'<span style="color:#2a2a2a">—</span>';
    var mv='<span style="color:#2a2a2a">—</span>';
    if(b.in_trade&&b.price&&b.entry){{
      var m=(b.price-b.entry)/b.entry*100*(b.direction==='long'?1:-1);
      mv='<span class="'+(m>=0?'col-g':'col-r')+'" style="font-weight:700">'+(m>=0?'+':'')+(+(m)||0).toFixed(3)+'%</span>';
    }}
    var unrH=b.in_trade
      ?'<span class="'+(b.unreal>=0?'col-g':'col-r')+'" style="font-weight:700">'+(b.unreal>=0?'+':'')+(+(b.unreal)||0).toFixed(4)+'</span>'
      :'<span style="color:#2a2a2a">—</span>';
    var realPnl=getPnl(b); var pnlCls=realPnl>=0?'col-g':'col-r';
    /* last trade */
    var bstatus=getBotStatus(b);
    html+='<tr class="'+rowcls+'" data-cat="'+b.cat+'" data-sym="'+b.symbol+'" data-status="'+bstatus+'" data-tier="'+(b.tier||'tier3')+'" data-layer="'+(b.layer||'other')+'" onclick="openChart('+i+')">'
      +'<td><span class="'+dotcls+'" style="display:inline-block;margin-right:7px"></span>'
        +(bstatus==='stale'?'<span style="font-size:7px;padding:1px 5px;border-radius:1px;background:rgba(255,59,92,.15);color:#ff3b5c;margin-right:4px">STALE</span>':'')
        +'<b style="color:#fff;font-size:13px;letter-spacing:.3px">'+b.symbol.replace('USDT','').replace('1000','')+'</b>'
        +'<span style="color:#252525;font-size:8px"> /USDT</span>'
        +'<div style="font-size:8px;color:#282828;margin-top:2px;line-height:1.3">'
          +b.name
          +(b.cat==='stock'?'<span class="bot-tag tag-stock">STK</span>':b.cat==='commodity'?'<span class="bot-tag tag-commod">CMD</span>':'')
          +(b.tier==='tier1'?'<span class="bot-tag tag-t1">T1</span>':b.tier==='tier2'?'<span class="bot-tag tag-t2">T2</span>':'')
          +(b.layer&&b.layer!=='other'?'<span class="bot-tag tag-layer">'+b.layer+'</span>':'')
        +'</div>'
      +'</td>'
      +'<td>'+badge+'</td>'
      +'<td class="num '+(b.chg24>=0?'col-g':'col-r')+'" id="px-'+b.symbol+'" style="font-weight:700;font-size:13px">'+(b.price?b.price.toFixed(d):'--')+'</td>'
      +'<td class="num '+chgCls+'" id="chg-'+b.symbol+'">'+(b.chg24>=0?'+':'')+(+(b.chg24)||0).toFixed(2)+'%</td>'
      +'<td class="num">'+entry+'</td>'
      +'<td>'+mv+'</td>'
      +'<td>'+unrH+'</td>'
      +'<td class="num '+pnlCls+'" style="font-weight:700">'+(realPnl>=0?'+':'')+(+(realPnl)||0).toFixed(4)+(b.has_exact?'<span class="col-dim" style="font-size:8px"> exact</span>':'')+'</td>'
      +'<td class="num" style="text-align:center">'+b.wins+'<span style="color:#2a2a2a"> / </span>'+b.losses+'</td>'
      +'<td style="white-space:nowrap">'
        +'<div style="display:flex;align-items:center;gap:5px;min-width:70px">'
          +'<div style="flex:1;height:2px;background:#111;border-radius:1px;overflow:hidden;min-width:30px;max-width:50px">'
            +'<div style="height:100%;border-radius:1px;width:'+Math.min(wr,100).toFixed(0)+'%;background:'+wrc+'"></div>'
          +'</div>'
          +'<span style="color:'+wrc+';font-weight:700;font-size:11px;min-width:28px;text-align:right">'+wr.toFixed(0)+'%</span>'
        +'</div>'
      +'</td>'

      +'<td style="color:#333;font-size:10px">'+b.runtime+'</td>'
      +'<td style="color:#2a2a2a;font-size:10px">'+b.ago+'</td>'
      +'</tr>';
  }});
  tb.innerHTML=html;
}}

/* CHART — same as original */
function openChart(idx){{
  var b=B[idx];
  var modal=el('chart-modal');
  var overlay=el('modal-overlay');
  if(!modal||!overlay)return;
  overlay.style.display='block';
  modal.style.display='flex';
  var d=dp(b.price);
  _activeChartSym=b.symbol;
  el('cm-sym').textContent=b.symbol.replace('USDT','')+'/USDT';
  el('cm-name').textContent=b.name+' · '+b.bot_type;
  var pe=el('cm-price');pe.textContent=b.price?'$'+b.price.toFixed(d):'--';pe.className='cm-price-v '+(b.chg24>=0?'col-g':'col-r');
  el('cm-chg').textContent=(b.chg24>=0?'+':'')+(+(b.chg24)||0).toFixed(2)+'% (24h)';el('cm-chg').className='cm-chg '+(b.chg24>=0?'col-g':'col-r');
  el('cm-high').textContent=b.high24?'$'+b.high24.toFixed(d):'--';
  el('cm-low').textContent=b.low24?'$'+b.low24.toFixed(d):'--';
  el('cm-vol').textContent=fv(b.vol24)+' USDT';
  el('cm-entry').textContent=b.in_trade&&b.entry?'$'+b.entry.toFixed(d):'--';
  var sle=el('cm-sl');
  if(b.in_trade&&b.sl){{sle.textContent='$'+b.sl.toFixed(d)+(b.tp1_done?' (BE)':'');sle.className='cm-stat-v '+(b.tp1_done?'col-o':'col-r');}}
  else{{sle.textContent='--';}}
  var tp1e=el('cm-tp1');
  if(tp1e){{if(b.tp1_price){{tp1e.textContent='$'+b.tp1_price.toFixed(d)+(b.tp1_done?' hit':'');tp1e.className='cm-stat-v '+(b.tp1_done?'col-g':'col-y');}}else{{tp1e.textContent='--';}}}}
  var tp2e=el('cm-tp2');
  if(tp2e){{if(b.tp2_price){{tp2e.textContent='$'+b.tp2_price.toFixed(d)+(b.tp2_done?' hit':'');tp2e.className='cm-stat-v '+(b.tp2_done?'col-g':'col-y');}}else{{tp2e.textContent='--';}}}}

  if(b.in_trade&&b.entry){{
    var tt=b.wins+b.losses,wr2=tt>0?(b.wins/tt*100).toFixed(1):'0.0';
    el('cm-wr').textContent=wr2+'% ('+b.wins+'W/'+b.losses+'L)';
    el('cm-pnl').textContent=(b.pnl>=0?'+':'')+b.pnl.toFixed(4);
    el('cm-pnl').className='cm-stat-v '+(b.pnl>=0?'col-g':'col-r');
    var ure=el('cm-unreal');ure.textContent=b.in_trade?(b.unreal>=0?'+':'')+(+(b.unreal)||0).toFixed(4):'--';ure.className='cm-stat-v '+(b.unreal>=0?'col-g':'col-r');
  }}
  el('cm-runtime').textContent=b.runtime;
  var sb=el('cm-status');
  if(b.in_trade&&b.direction==='long')sb.innerHTML='<span class="cm-badge cb-long">▲ LONG</span>';
  else if(b.in_trade&&b.direction==='short')sb.innerHTML='<span class="cm-badge cb-short">▼ SHORT</span>';
  else sb.innerHTML='<span class="cm-badge cb-flat">— FLAT</span>';
  var pp=el('cm-partial');if(pp){{pp.textContent=b.partial?'✓ Breakeven hit':'Not hit';pp.className='cm-stat-v '+(b.partial?'col-o':'col-dim');}}
  /* bottom bar */
  var bbar=el('cm-status-bar');
  if(bbar){{if(b.in_trade&&b.direction==='long')bbar.innerHTML='<span class="col-g" style="font-weight:700">▲ LONG</span>';else if(b.in_trade&&b.direction==='short')bbar.innerHTML='<span class="col-r" style="font-weight:700">▼ SHORT</span>';else bbar.textContent='— FLAT';}}
  var qt=el('cm-qty');if(qt)qt.textContent=b.qty?b.qty+' '+b.symbol.replace('USDT',''):'--';
  var wle=el('cm-wl');if(wle)wle.textContent=b.wins+'W / '+b.losses+'L';
  var tp=el('cm-type');if(tp)tp.textContent=b.bot_type;
  var ag=el('cm-ago');if(ag)ag.textContent=b.ago;
  // Bybit exact trades pane
  var bybitPane=el('cm-bybit-trades');
  if(bybitPane){{
    bybitPane.innerHTML='<div style="color:#333;padding:12px;font-size:9px">Loading Bybit trades...</div>';
    loadBybitPnl(b.symbol,bybitPane);
  }}
  buildChart(b);
}}

function closeChart(){{
  _activeChartSym=null;
  el('modal-overlay').style.display='none';
  el('chart-modal').style.display='none';
  if(chart){{chart.remove();chart=null;}}
  if(macdChart){{macdChart.remove();macdChart=null;}}
  cS=null;vS=null;e20S=null;e50S=null;e100S=null;e200S=null;
  macdHS=null;macdLS=null;macdSS=null;PL=[];
}}

function buildChart(b){{
  var wrap=el('cm-chart');if(!wrap)return;
  // Cleanup
  if(chart){{chart.remove();chart=null;}}
  if(macdChart){{macdChart.remove();macdChart=null;}}
  cS=vS=e20S=e50S=e100S=e200S=macdHS=macdLS=macdSS=null;_liveBar=null;_lastHABar=null;_lastSMAs=null;PL=[];
  // Split chart area into main + MACD pane
  wrap.innerHTML='';
  wrap.style.display='flex';wrap.style.flexDirection='column';
  var mainDiv=document.createElement('div');
  mainDiv.style.cssText='flex:1;position:relative;min-height:0';
  var macdDiv=document.createElement('div');
  macdDiv.style.cssText='height:130px;position:relative;border-top:1px solid #111;flex-shrink:0';
  wrap.appendChild(mainDiv);wrap.appendChild(macdDiv);
  var prec=dp(b.price||b.entry||1);
  var minmv=Math.pow(10,-prec);
  var baseOpts={{
    layout:{{background:{{color:'#050505'}},textColor:'#3a3a3a',fontFamily:"'JetBrains Mono',monospace",fontSize:10}},
    grid:{{vertLines:{{color:'#0d0d0d'}},horzLines:{{color:'#0d0d0d'}}}},
    crosshair:{{mode:LightweightCharts.CrosshairMode.Normal,
      vertLine:{{color:'rgba(255,170,0,.3)',labelBackgroundColor:'#1a1600'}},
      horzLine:{{color:'rgba(255,170,0,.3)',labelBackgroundColor:'#1a1600'}}}},
    handleScroll:true,handleScale:true,
  }};
  // Main chart
  chart=LightweightCharts.createChart(mainDiv,Object.assign({{}},baseOpts,{{
    rightPriceScale:{{borderColor:'#1a1a1a',scaleMargins:{{top:0.05,bottom:0.12}}}},
    timeScale:{{borderColor:'#1a1a1a',timeVisible:true,secondsVisible:TF==='1'}},
  }}));
  // Heikin Ashi series
  cS=chart.addCandlestickSeries({{upColor:'#00e676',downColor:'#ff1744',
    borderUpColor:'#00e676',borderDownColor:'#ff1744',
    wickUpColor:'#26a661',wickDownColor:'#e53935',
    priceFormat:{{type:'price',precision:prec,minMove:minmv}}}});
  // Volume
  vS=chart.addHistogramSeries({{priceFormat:{{type:'volume'}},priceScaleId:'vol'}});
  chart.priceScale('vol').applyOptions({{scaleMargins:{{top:0.88,bottom:0}},visible:false}});
  // EMA ribbon (matches bot signal: SMA 20/50/100/200)
  var lOpts={{priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,lineWidth:1}};
  e20S =chart.addLineSeries(Object.assign({{}},lOpts,{{color:'rgba(255,235,59,0.7)' }}));
  e50S =chart.addLineSeries(Object.assign({{}},lOpts,{{color:'rgba(255,152,0,0.65)' }}));
  e100S=chart.addLineSeries(Object.assign({{}},lOpts,{{color:'rgba(255,87,34,0.55)' }}));
  e200S=chart.addLineSeries(Object.assign({{}},lOpts,{{color:'rgba(198,40,40,0.5)'  }}));
  // MACD chart
  macdChart=LightweightCharts.createChart(macdDiv,Object.assign({{}},baseOpts,{{
    rightPriceScale:{{borderColor:'#1a1a1a',scaleMargins:{{top:0.1,bottom:0.1}}}},
    timeScale:{{borderColor:'#1a1a1a',timeVisible:false,visible:false}},
    handleScroll:false,handleScale:false,
  }}));
  macdHS=macdChart.addHistogramSeries({{priceLineVisible:false,lastValueVisible:false}});
  macdLS=macdChart.addLineSeries({{color:'#00bcd4',lineWidth:1,priceLineVisible:false,lastValueVisible:true}});
  macdSS=macdChart.addLineSeries({{color:'#ff7043',lineWidth:1,priceLineVisible:false,lastValueVisible:true}});
  // Zero line
  var _zeroLine=macdChart.addLineSeries({{color:'rgba(255,255,255,.08)',lineWidth:1,priceLineVisible:false,lastValueVisible:false}});
  // Sync crosshairs & scroll
  chart.timeScale().subscribeVisibleLogicalRangeChange(function(r){{if(r&&macdChart)macdChart.timeScale().setVisibleLogicalRange(r);}});
  macdChart.timeScale().subscribeVisibleLogicalRangeChange(function(r){{if(r&&chart)chart.timeScale().setVisibleLogicalRange(r);}});
  // Resize
  new ResizeObserver(function(){{
    if(chart)chart.applyOptions({{width:mainDiv.clientWidth,height:mainDiv.clientHeight}});
    if(macdChart)macdChart.applyOptions({{width:macdDiv.clientWidth,height:macdDiv.clientHeight}});
  }}).observe(wrap);
  chart.applyOptions({{width:mainDiv.clientWidth,height:mainDiv.clientHeight}});
  macdChart.applyOptions({{width:macdDiv.clientWidth,height:macdDiv.clientHeight}});
  loadCandles(b);
}}

function loadCandles(b){{
  var spin=el('cm-spin');if(spin)spin.style.display='block';
  fetch(API+'/v5/market/kline?category=linear&symbol='+b.symbol+'&interval='+TF+'&limit=500')
  .then(function(r){{return r.json();}})
  .then(function(data){{
    var raw=(data.result&&data.result.list)||[];
    if(!raw.length){{
      var wrap2=el('cm-chart');
      if(wrap2)wrap2.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#333;font-size:11px;letter-spacing:1px">'
        +'NO DATA FOR '+b.symbol+' — symbol may not exist on Bybit</div>';
      if(spin)spin.style.display='none';return;
    }}
    // Parse raw candles (Bybit timestamps are UTC unix ms)
    var candles=raw.map(function(r){{
      return{{time:Math.floor(parseInt(r[0])/1000),
              open:parseFloat(r[1]),high:parseFloat(r[2]),
              low:parseFloat(r[3]),close:parseFloat(r[4]),vol:parseFloat(r[5])}};
    }}).sort(function(a,x){{return a.time-x.time;}});
    // Heikin Ashi
    var ha=[];var pHAO=0,pHAC=0;
    for(var i=0;i<candles.length;i++){{
      var c=candles[i];
      var haC=(c.open+c.high+c.low+c.close)/4;
      var haO=i===0?(c.open+c.close)/2:(pHAO+pHAC)/2;
      var haH=Math.max(c.high,haO,haC);
      var haL=Math.min(c.low,haO,haC);
      ha.push({{time:c.time,open:haO,high:haH,low:haL,close:haC,vol:c.vol}});
      pHAO=haO;pHAC=haC;
    }}
    // EMA (matches bot: ewm adjust=False)
    function ema(arr,p){{
      var k=2/(p+1),out=[arr[0]];
      for(var i=1;i<arr.length;i++)out.push(arr[i]*k+out[i-1]*(1-k));
      return out;
    }}
    // SMA (matches bot: rolling mean = ta.sma)
    function sma(arr,p){{
      var out=[];
      for(var i=0;i<arr.length;i++){{
        if(i<p-1){{out.push(null);continue;}}
        var s=0;for(var j=i-p+1;j<=i;j++)s+=arr[j];out.push(s/p);
      }}
      return out;
    }}
    var cls=candles.map(function(c){{return c.close;}});
    var s20=sma(cls,20),s50=sma(cls,50),s100=sma(cls,100),s200=sma(cls,200);
    var e12=ema(cls,12),e26=ema(cls,26);
    var macd=e12.map(function(v,i){{return v-e26[i];}});
    var sig=ema(macd,9);
    var hist=macd.map(function(v,i){{return v-sig[i];}});
    // Helpers
    function ts(arr,useHA){{
      return arr.map(function(v,i){{return v!==null?{{time:(useHA?ha:candles)[i].time,value:v}}:null;}}).filter(Boolean);
    }}
    // Store for fallback use
    _lastCandles=candles;
    _lastHABar=ha.length>0?ha[ha.length-1]:null;
    // Set Heikin Ashi candles
    if(cS)cS.setData(ha);
    // Volume (HA colour)
    if(vS)vS.setData(ha.map(function(c){{return{{time:c.time,value:c.vol,
      color:c.close>=c.open?'rgba(0,230,118,.12)':'rgba(255,23,68,.12)'}}; }}));
    // SMA ribbon
    if(e20S) e20S.setData(ts(s20));
    if(e50S) e50S.setData(ts(s50));
    if(e100S)e100S.setData(ts(s100));
    if(e200S)e200S.setData(ts(s200));
    // Store last valid SMA values for live bar extension
    var _getLastValid=function(arr){{for(var i=arr.length-1;i>=0;i--)if(arr[i]!==null)return arr[i];return null;}};
    _lastSMAs={{s20:_getLastValid(s20),s50:_getLastValid(s50),
                s100:_getLastValid(s100),s200:_getLastValid(s200),
                macd:macd[macd.length-1]||0,sig:sig[sig.length-1]||0,
                hist:hist[hist.length-1]||0,cls:cls}};
    // MACD pane
    if(macdLS)macdLS.setData(ts(macd));
    if(macdSS)macdSS.setData(ts(sig));
    if(macdHS){{
      var ph=0;
      macdHS.setData(candles.map(function(c,i){{
        var h=hist[i];
        var col=h>=0?(h>=ph?'#26a69a':'#147766'):(h<=ph?'#ef5350':'#7f3833');
        ph=h;return{{time:c.time,value:h,color:col}};
      }}));
    }}
    // Zero line for MACD reference
    try{{if(typeof _zeroLine!=='undefined'&&_zeroLine&&_zeroLine.setData)
      _zeroLine.setData(candles.map(function(c){{return{{time:c.time,value:0}};}}))
    }}catch(e){{}}
    // Buy/Sell signal markers (exact bot logic)
    // ── Markers: MACD crosses + actual trades ────────────────────
    var markers=[], macdMarkers=[];

    // MACD crossover circles — ON the MACD line (inBar), small
    for(var i=1;i<candles.length;i++){{
      if(!macd[i]||!sig[i]||!macd[i-1]||!sig[i-1])continue;
      var xup=macd[i-1]<=sig[i-1]&&macd[i]>sig[i];
      var xdn=macd[i-1]>=sig[i-1]&&macd[i]<sig[i];
      if(xup) macdMarkers.push({{time:ha[i].time,position:'inBar',
        color:'#00e676',shape:'circle',size:1}});
      if(xdn) macdMarkers.push({{time:ha[i].time,position:'inBar',
        color:'#ef5350',shape:'circle',size:1}});
    }}
    if(macdLS){{try{{macdLS.setMarkers(macdMarkers);}}catch(e){{}}}}

    // ── Trade markers from log history + current open position ──
    var trades=b.trades||[];
    function nearCandle(ts){{
      var best=null,bd=Infinity;
      for(var ci=0;ci<ha.length;ci++){{
        var d=Math.abs(ha[ci].time-ts);
        if(d<bd){{bd=d;best=ha[ci].time;}}
      }}
      return bd<86400?best:null;  // within 24h
    }}
    // From log history (completed + partial trades)
    trades.forEach(function(t){{
      if(!t.entry||!t.tin)return;
      var isLong=(t.dir||'').toUpperCase()==='LONG';
      var epd=dp(t.entry||1), cpd=dp(t.close||1);
      var ets=Math.floor(new Date(t.tin.replace(' ','T')+'Z').getTime()/1000);
      var et=nearCandle(ets);
      if(et){{
        markers.push({{time:et,
          position:isLong?'belowBar':'aboveBar',
          color:isLong?'#00e676':'#ef5350',
          shape:isLong?'arrowUp':'arrowDown',
          size:1,text:(t.entry).toFixed(epd)+(t.qty?" q"+t.qty:"")}});
      }}
      if(t.close&&t.tout){{
        var xts=Math.floor(new Date(t.tout.replace(' ','T')+'Z').getTime()/1000);
        var xt=nearCandle(xts);
        if(xt){{
          var lbl=(t.close).toFixed(cpd)+(t.reason?' '+t.reason:'');
          markers.push({{time:xt,
            position:isLong?'aboveBar':'belowBar',
            color:isLong?'#ef5350':'#00e676',
            shape:isLong?'arrowDown':'arrowUp',
            size:1,text:lbl}});
        }}
      }}
    }});
    // Current OPEN position — entry + TP1/TP2 markers
    if(b.in_trade&&b.entry&&ha.length>0){{
      var isLong=b.direction==='long';
      var epd=dp(b.entry);

      // ── Find entry candle ──────────────────────────────────────
      // For SHORT: first candle where HIGH >= entry AND previous candle HIGH < entry
      // (price crosses entry level from below going short)
      // Fallback: last candle that contains entry price
      var entryIdx=-1;
      for(var ei=1;ei<ha.length;ei++){{
        var prev=ha[ei-1], cur=ha[ei];
        if(!isLong && prev.high<b.entry && cur.high>=b.entry) {{ entryIdx=ei; }}
        if(isLong  && prev.low>b.entry  && cur.low<=b.entry)  {{ entryIdx=ei; }}
      }}
      // If no clear cross found, use last candle containing entry
      if(entryIdx<0){{
        for(var ei2=ha.length-1;ei2>=0;ei2--){{
          if(ha[ei2].low<=b.entry&&ha[ei2].high>=b.entry){{entryIdx=ei2;break;}}
        }}
      }}
      if(entryIdx<0) entryIdx=ha.length-1;
      var entryT=ha[entryIdx].time;

      // Entry arrow (only if no log trade already added at this time)
      var alreadyHasEntry=markers.some(function(mk){{return mk.time===entryT;}});
      if(!alreadyHasEntry){{
        markers.push({{time:entryT,
          position:isLong?'belowBar':'aboveBar',
          color:isLong?'#00e676':'#ef5350',
          shape:isLong?'arrowUp':'arrowDown',
          size:2, text:b.entry.toFixed(epd)+(b.qty?' q'+b.qty:'')}});
      }}

      // ── TP1: search FORWARD from entry for FIRST hit ──────────
      if(b.partial&&b.tp1&&b.tp1>0){{
        var tp1d=dp(b.tp1);
        for(var t1=entryIdx+1;t1<ha.length;t1++){{
          var hit1=(isLong&&ha[t1].high>=b.tp1)||(!isLong&&ha[t1].low<=b.tp1);
          if(hit1){{
            markers.push({{time:ha[t1].time,
              position:isLong?'aboveBar':'belowBar',
              color:isLong?'#ef5350':'#00e676',
              shape:isLong?'arrowDown':'arrowUp',
              size:1, text:b.tp1.toFixed(tp1d)+' TP1'}});
            break;
          }}
        }}
      }}

      // ── TP2: show if tp2_done OR price visibly crossed TP2 ──
      if(b.tp2&&b.tp2>0){{
        var tp2d=dp(b.tp2);
        // Price-based check: did any candle after entry cross TP2?
        var tp2PriceCrossed=false;
        var tp2CandleIdx=-1;
        for(var t2=entryIdx+1;t2<ha.length;t2++){{
          var hit2=(isLong&&ha[t2].high>=b.tp2)||(!isLong&&ha[t2].low<=b.tp2);
          if(hit2){{tp2PriceCrossed=true;tp2CandleIdx=t2;break;}}
        }}
        if((b.tp2_done||tp2PriceCrossed)&&tp2CandleIdx>=0){{
          markers.push({{time:ha[tp2CandleIdx].time,
            position:isLong?'aboveBar':'belowBar',
            color:isLong?'#ef5350':'#00e676',
            shape:isLong?'arrowDown':'arrowUp',
            size:1, text:b.tp2.toFixed(tp2d)+' TP2'}});
        }}
      }}
      // ── SL hit: check if price crossed SL after entry ─────────
      if(b.sl&&b.sl>0&&!b.in_trade===false){{
        // Only show SL if position is still open (don't double-mark closed trades)
      }}
    }}
    // Sort markers by time (required by LightweightCharts)
    markers.sort(function(a,b){{return a.time-b.time;}});
    // Fit all data first, then scroll to live edge
    chart.timeScale().fitContent();
    if(macdChart)macdChart.timeScale().fitContent();
    try{{chart.timeScale().scrollToRealTime();}}catch(e){{}}
    try{{if(macdChart)macdChart.timeScale().scrollToRealTime();}}catch(e){{}}
    _sigMarkers=markers;
    if(cS)cS.setMarkers(markers);
    drawLines(b);
    // Last bar signal condition debug
    var li=candles.length-1;
    if(li>0&&s20[li]&&s50[li]&&s100[li]&&s200[li]){{
      var lbc=cls[li],lm=macd[li],ls2=sig[li],lh=hist[li];
      var bs=lbc>s20[li]&&s20[li]>s50[li]&&s50[li]>s100[li]&&s100[li]>s200[li];
      var rs=lbc<s20[li]&&s20[li]<s50[li]&&s50[li]<s100[li]&&s100[li]<s200[li];
      var xu=macd[li-1]<=sig[li-1]&&lm>ls2,xd=macd[li-1]>=sig[li-1]&&lm<ls2;
      var mu=lh>hist[li-1],md=lh<hist[li-1];
      var mkr=function(ok,t){{return'<span style="color:'+(ok?'#00e676':'#333')+';margin-right:6px">'+(ok?'✓':'✗')+' '+t+'</span>';}};
      var sd=el('signal-debug');
      if(sd)sd.innerHTML=
        '<span style="color:#2a2a2a;font-size:9px;margin-right:8px;letter-spacing:1px">BUY:</span>'
        +mkr(bs,'SMA↑')+mkr(xu,'X↑')+mkr(lm>0,'M>0')+mkr(mu,'H↑')
        +'<span style="color:#111;margin:0 10px">│</span>'
        +'<span style="color:#2a2a2a;font-size:9px;margin-right:8px;letter-spacing:1px">SELL:</span>'
        +mkr(rs,'SMA↓')+mkr(xd,'X↓')+mkr(lm<0,'M<0')+mkr(md,'H↓')
        +(bs&&xu&&lm>0&&mu?'<span style="color:#00e676;margin-left:10px">▲ LONG SIGNAL</span>'
          :rs&&xd&&lm<0&&md?'<span style="color:#ff3b5c;margin-left:10px">▼ SHORT SIGNAL</span>'
          :'<span style="color:#1a1a1a;margin-left:10px">neutral</span>');
    }}
    if(spin)spin.style.display='none';
  }}).catch(function(e){{console.error(e);if(spin)spin.style.display='none';}});
}}

function clearLines(){{
  PL.forEach(function(item){{
    try{{cS.removePriceLine(item);}}catch(e){{
      try{{chart.removeSeries(item);}}catch(e2){{}}
    }}
  }});
  PL=[];
}}

function drawLines(b){{
  if(!cS||!chart||!b||!b.in_trade||!b.entry)return;
  clearLines();
  var isLong=(b.direction==='long'),d=dp(b.entry);
  var eC=isLong?'#00e676':'#ff3b5c';
  [
    {{p:b.entry,c:eC,lw:2,ls:0,t:(isLong?'L ':'S ')+'Entry '+b.entry.toFixed(d)}},
    {{p:+(b.sl)||0,c:b.tp1_done?'#ff9500':'#ff3b5c',lw:2,ls:2,t:'SL '+b.sl.toFixed(d)}},
    {{p:+(b.tp1_price)||0,c:b.tp1_done?'#00e676':'#ffd60a',lw:1,ls:2,t:'TP1 '+(+(b.tp1_price)||0).toFixed(d)}},
    {{p:+(b.tp2_price)||0,c:b.tp2_done?'#00e676':'#ff9f0a',lw:1,ls:2,t:'TP2 '+(+(b.tp2_price)||0).toFixed(d)}},
  ].forEach(function(lv){{
    if(!lv.p||lv.p<=0)return;
    try{{PL.push(cS.createPriceLine({{price:lv.p,color:lv.c,lineWidth:lv.lw,
      lineStyle:lv.ls,axisLabelVisible:true,title:lv.t}}));}}
    catch(e){{
      try{{
        if(!_lastCandles||!_lastCandles.length)return;
        var s=chart.addLineSeries({{color:lv.c,lineWidth:lv.lw,lineStyle:lv.ls,
          priceLineVisible:false,lastValueVisible:true,title:lv.t}});
        s.setData([{{time:_lastCandles[0].time,value:lv.p}},
                   {{time:_lastCandles[_lastCandles.length-1].time,value:lv.p}}]);
        PL.push(s);
      }}catch(e2){{console.error('drawLines failed',lv.t,lv.p,e2);}}
    }}
  }});
  try{{
    var n3=Math.floor(Date.now()/1000);
    var ts=parseInt(TF==='D'?'1440':TF)*60,bT=Math.floor(n3/ts)*ts;
    var pm={{time:bT,position:isLong?'belowBar':'aboveBar',color:eC,
      shape:isLong?'arrowUp':'arrowDown',
      text:(isLong?'▲':'▼')+' '+b.entry.toFixed(d),size:2}};
    var am=(_sigMarkers||[]).filter(function(m){{return m.time<bT-ts*2;}});
    am.push(pm);cS.setMarkers(am);
  }}catch(e){{}}
}}



function setTF(btn){{
  TF=btn.dataset.tf;
  document.querySelectorAll('.tf-btn').forEach(function(b){{b.classList.remove('tf-on');}});
  btn.classList.add('tf-on');
  var activeBot=null;
  B.forEach(function(b){{if(el('cm-sym')&&el('cm-sym').textContent.startsWith(b.symbol.replace('USDT','')))activeBot=b;}});
  if(chart&&activeBot)loadCandles(activeBot);  // reloads both main+MACD
}}

function renderPos(){{
  var tb=el('pos-body'),em=el('pos-empty'),ct=el('pos-count');
  var open=B.filter(function(b){{return b.in_trade;}});
  if(ct)ct.textContent=open.length+' open';
  if(!open.length){{if(tb)tb.innerHTML='';if(em)em.style.display='flex';return;}}
  if(em)em.style.display='none';if(!tb)return;
  tb.innerHTML=open.map(function(b){{
    var d=dp(b.price||b.entry||1);
    var isLong=b.direction==='long';
    // SL distance %
    var slp=b.entry&&b.sl?(Math.abs(b.entry-b.sl)/b.entry*100).toFixed(2)+'%':'--';
    // SL label — BE if TP1 hit
    var slLabel=b.sl?fc(b.sl)+(b.tp1_done?' <span style="color:#ff9500;font-size:8px">BE</span>':''):'--';
    var slCls=b.tp1_done?'col-o':'col-r';
    // Move
    var mv='<span style="color:#2a2a2a">--</span>';
    if(b.price&&b.entry){{
      var m=(b.price-b.entry)/b.entry*100*(isLong?1:-1);
      mv='<span class="'+(m>=0?'col-g':'col-r')+'" style="font-weight:700">'+(m>=0?'+':'')+(+(m)||0).toFixed(3)+'%</span>';
    }}
    // Unrealised
    var uc=b.unreal>=0?'col-g':'col-r';
    var unrStr=(b.unreal>=0?'+':'')+(+(b.unreal)||0).toFixed(4);
    // Size
    var sizeStr=b.qty?b.qty+' <span style="color:#333">'+b.symbol.replace('USDT','')+'</span>':'--';
    // TP1
    var tp1d=dp(b.tp1_price||1);
    var tp1Str=b.tp1_price?'<span class="'+(b.tp1_done?'col-g':'col-y')+'">'+fc(b.tp1_price)+'</span>':'<span style="color:#2a2a2a">--</span>';
    // TP2
    var tp2Str=b.tp2_price?'<span class="'+(b.tp2_done?'col-g':'col-o')+'">'+fc(b.tp2_price)+'</span>':'<span style="color:#2a2a2a">--</span>';
    // TP1/TP2 status badges
    var tp1Badge=b.tp1_done?'<span style="color:#00e676;font-size:9px">✓ HIT</span>':'<span style="color:#2a2a2a;font-size:9px">-</span>';
    var tp2Badge=b.tp2_done?'<span style="color:#00e676;font-size:9px">✓ HIT</span>':'<span style="color:#2a2a2a;font-size:9px">-</span>';
    var dotcls=b.age<30?'pulse-dot':b.age<120?'dot-y':b.age<300?'dot-r':'dot-dead';
    return '<tr onclick="openChart(B.indexOf(b))" style="cursor:pointer">'
      +'<td><span class="'+dotcls+'" style="display:inline-block;margin-right:6px"></span>'
        +'<b style="color:#fff">'+b.symbol.replace('USDT','')+'</b>'
        +'<span style="color:#2a2a2a">/USDT</span>'
        +'<div style="font-size:8px;color:#2a2a2a;margin-top:1px">'+b.name+'</div>'
      +'</td>'
      +'<td><span class="card-badge '+(isLong?'cb-long':'cb-short')+'">'+(isLong?'▲ LONG':'▼ SHORT')+'</span></td>'
      +'<td class="num">'+(b.entry?fc(b.entry):'--')+'</td>'
      +'<td class="num '+(b.mark?(b.mark>b.entry?(isLong?'col-g':'col-r'):(isLong?'col-r':'col-g')):'')+'">'+( b.mark?fc(b.mark):'--')+'</td>'
      +'<td class="num '+slCls+'">'+slLabel+'</td>'
      +'<td class="num" style="color:#555">'+slp+'</td>'
      +'<td>'+tp1Str+'</td>'
      +'<td>'+tp2Str+'</td>'
      +'<td>'+mv+'</td>'
      +'<td class="num '+uc+'" style="font-weight:700">'+unrStr+'</td>'
      +'<td class="num" style="color:#444">'+sizeStr+'</td>'
      +'<td style="font-size:10px">'+tp1Badge+'</td>'
      +'<td style="font-size:10px">'+tp2Badge+'</td>'
      +'<td style="color:#333;font-size:10px">'+b.runtime+'</td>'
      +'<td style="color:#2a2a2a;font-size:10px">'+b.ago+'</td>'
      +'</tr>';
  }}).join('');
}}

// Load exact Bybit PnL lazily (after page renders, per symbol, on demand)
var _bpCache={{}};
function loadBybitPnl(symbol,pane){{
  if(_bpCache[symbol]){{if(pane)pane.innerHTML=renderBybitTrades(symbol,_bpCache[symbol]);return;}}
  var key=localStorage.getItem('bybit_key')||'';
  var sec=localStorage.getItem('bybit_sec')||'';
  if(!key||!sec){{if(pane)pane.innerHTML='<div style="color:#333;padding:12px;font-size:9px">Set BYBIT_API_KEY / BYBIT_API_SECRET env vars for exact PnL</div>';return;}}
  var ts=Date.now().toString();var rw='5000';
  var qs='category=linear&symbol='+symbol+'&limit=20';
  // Note: HMAC signing requires server-side — skip for browser security
  if(pane)pane.innerHTML='<div style="color:#333;padding:12px;font-size:9px">Bybit PnL loaded from api_keys.txt on server — see state file</div>';
}}
function fmtTime(ms){{
  if(!ms)return'--';
  var d=new Date(parseInt(ms));
  return d.toISOString().replace('T',' ').substr(0,19);
}}

function renderBybitTrades(symbol,trades){{
  if(!trades||!trades.length)return'<div style="color:#2a2a2a;padding:20px">No closed trades found for '+symbol+'</div>';
  var d=2;
  var rows=trades.map(function(t){{
    var pc=t.won?'col-g':'col-r';
    var side=t.side==='Sell'?'<span class="card-badge cb-short">▼ SHORT</span>':'<span class="card-badge cb-long">▲ LONG</span>';
    return '<tr>'      +'<td>'+fmtTime(t.time)+'</td>'      +'<td>'+side+'</td>'      +'<td class="num">'+t.entry.toFixed(d)+'</td>'      +'<td class="num">'+t.exit.toFixed(d)+'</td>'      +'<td class="num">'+t.qty+'</td>'      +'<td class="num '+pc+'" style="font-weight:700">'+(t.pnl>=0?'+':'')+t.pnl.toFixed(6)+' USDT</td>'      +'</tr>';
  }}).join('');
  return '<table class="dt" style="width:100%">'    +'<thead><tr><th>Time (UTC)</th><th>Side</th><th>Entry</th><th>Exit</th><th>Qty</th><th>Realized PnL</th></tr></thead>'    +'<tbody>'+rows+'</tbody></table>';
}}

function renderHist(){{
  var tb=el('hist-body');if(!tb)return;
  var sorted=B.slice().sort(function(a,b){{return b.pnl-a.pnl;}});
  tb.innerHTML=sorted.map(function(b){{
    var t=b.wins+b.losses,wr=t>0?(b.wins/t*100):0;
    var wrc=wr>=50?'var(--g)':wr>=35?'var(--o)':'var(--r)';
    var histPnl=getPnl(b); var pCls=histPnl>=0?'col-g':'col-r';
    var dot=b.age<30?'pulse-dot':b.age<120?'dot-y':'dot-r';
    var badge=b.in_trade&&b.direction==='long'?'<span class="card-badge cb-long">▲ LONG</span>'
              :b.in_trade&&b.direction==='short'?'<span class="card-badge cb-short">▼ SHORT</span>'
              :'<span class="card-badge cb-flat">FLAT</span>';
    return '<tr data-hsym="'+b.symbol+'" onclick="openChart(B.indexOf(b))" style="cursor:pointer">'
      +'<td><span class="'+dot+'" style="display:inline-block;margin-right:6px"></span><b>'+b.symbol.replace('USDT','')+'</b><span style="color:#2a2a2a">/USDT</span></td>'
      +'<td style="color:#333;font-size:10px">'+b.bot_type+'</td>'
      +'<td>'+badge+'</td>'
      +'<td class="num" style="text-align:center">'+t+'</td>'
      +'<td class="col-g" style="text-align:center">'+b.wins+'</td>'
      +'<td class="col-r" style="text-align:center">'+b.losses+'</td>'
      +'<td><div style="display:flex;align-items:center;gap:5px"><div style="flex:1;height:2px;background:#111;border-radius:1px;overflow:hidden;min-width:30px;max-width:50px"><div style="height:100%;border-radius:1px;width:'+Math.min(wr,100).toFixed(0)+'%;background:'+wrc+'"></div></div>'
          +'<span style="color:'+wrc+';font-weight:700;min-width:34px">'+wr.toFixed(0)+'%</span></div></td>'
      +'<td class="num '+pCls+'" style="font-weight:700">'+(histPnl>=0?'+':'')+histPnl.toFixed(4)+'</td>'
      +(b.has_exact
        ?'<td class="num '+(b.exact_pnl>=0?'col-g':'col-r')+'" style="font-weight:700">'+(b.exact_pnl>=0?'+':'')+b.exact_pnl.toFixed(4)+'</td>'
         +'<td class="num col-r" style="font-size:10px">-$'+b.exact_fees.toFixed(4)+'</td>'
         +'<td class="num '+(b.exact_funding>=0?'col-g':'col-r')+'" style="font-size:10px">'+(b.exact_funding>=0?'+':'')+b.exact_funding.toFixed(4)+'</td>'
        :'<td class="col-dim" style="font-size:10px">no history</td><td class="col-dim">—</td><td class="col-dim">—</td>')
      +'<td style="color:#333;font-size:10px">'+b.log_ct+'</td>'
      +'<td style="color:#2a2a2a;font-size:10px">'+b.runtime+'</td>'
      +'<td style="color:#2a2a2a;font-size:10px">'+b.ago+'</td>'
      +'</tr>';
  }}).join('');
}}


// ─── Live Price Engine — WebSocket + 1s REST fallback ───────────
var _ws=null,_wsSyms=[],_liveP={{}},_prevP={{}},_activeChartSym=null,_sigMarkers=[],_lastCandles=[];
var _tickTimer=null;

// REST: fetch ALL tickers at once — one call covers all 31 bots
function _fetchAllTickers(){{
  fetch(API+'/v5/market/tickers?category=linear')
  .then(function(r){{return r.json();}})
  .then(function(data){{
    if(!data.result||!data.result.list)return;
    data.result.list.forEach(function(t){{
      var sym=t.symbol;
      // Only update symbols we track
      if(_wsSyms.indexOf(sym)===-1)return;
      var px=parseFloat(t.lastPrice);
      var chgPct=parseFloat(t.price24hPcnt||0)*100;
      var high=parseFloat(t.highPrice24h||0);
      var low=parseFloat(t.lowPrice24h||0);
      var vol=parseFloat(t.volume24h||0);
      if(isNaN(px)||px===0)return;
      _updateSymPrice(sym,px,chgPct,high,low,vol);
    }});
    // Pulse the live indicator
    var pill=el('live-pill');
    if(pill){{pill.style.opacity='0.5';setTimeout(function(){{pill.style.opacity='1';}},120);}}
  }})
  .catch(function(){{}});
}}

function _updateSymPrice(sym,px,chgPct,high,low,vol){{
  var prev=_liveP[sym]||0;
  _prevP[sym]=prev;
  _liveP[sym]=px;
  var d=dp(px);
  // Update chart modal header price if this is the active chart
  if(_activeChartSym===sym){{
    var cp=el('cm-price');
    if(cp){{cp.textContent='$'+px.toFixed(d);cp.className='cm-price-v '+(px>=prev?'col-g':'col-r');}}
  }}
  // Price cell
  var pc=el('px-'+sym);
  if(pc){{
    pc.textContent=px.toFixed(d);
    if(px!==prev&&prev!==0){{
      pc.className='num '+(px>=prev?'col-g':'col-r');
      pc.style.fontWeight='700';pc.style.fontSize='13px';
      pc.classList.remove('px-up','px-dn');
      void pc.offsetWidth; // reflow to restart animation
      pc.classList.add(px>=prev?'px-up':'px-dn');
    }} else {{
      pc.className='num '+(chgPct>=0?'col-g':'col-r');
      pc.style.fontWeight='700';pc.style.fontSize='13px';
    }}
  }}
  // 24h change
  var cc=el('chg-'+sym);
  if(cc){{cc.textContent=(chgPct>=0?'+':'')+chgPct.toFixed(2)+'%';cc.className='num '+(chgPct>=0?'col-g':'col-r');}}
  // Unrealised PnL for open positions
  B.forEach(function(b){{
    if(b.symbol!==sym||!b.in_trade||!b.entry)return;
    var unr=b.qty*(b.direction==='long'?px-b.entry:b.entry-px);
    var mv=(px-b.entry)/b.entry*100*(b.direction==='long'?1:-1);
    var row=document.querySelector('#bot-list-body tr[data-sym="'+sym+'"]');
    if(!row)return;
    var mvCell=row.cells[5],unrCell=row.cells[6];
    if(mvCell)mvCell.innerHTML='<span class="'+(mv>=0?'col-g':'col-r')+'" style="font-weight:700">'+(mv>=0?'+':'')+mv.toFixed(3)+'%</span>';
    if(unrCell)unrCell.innerHTML='<span class="'+(unr>=0?'col-g':'col-r')+'" style="font-weight:700">'+(unr>=0?'+':'')+unr.toFixed(4)+'</span>';
  }});
  // Live chart candle — correct UTC, proper HA, no future empty space
  if(chart&&_activeChartSym===sym&&cS&&_lastCandles&&_lastCandles.length>0){{
    try{{
      var tfSec=parseInt(TF==='D'?'1440':TF)*60;
      var nowUTC=Math.floor(Date.now()/1000);
      var barT=Math.floor(nowUTC/tfSec)*tfSec;
      var lhab=_lastHABar||(_lastCandles.length>0?_lastCandles[_lastCandles.length-1]:null);
      if(!_liveBar||_liveBar.time!==barT){{
        var prevHAO=lhab?lhab.open:px, prevHAC=lhab?lhab.close:px;
        _liveBar={{time:barT,open:px,high:px,low:px,close:px,haOpen:(prevHAO+prevHAC)/2}};
      }}else{{
        _liveBar.close=px;
        if(px>_liveBar.high)_liveBar.high=px;
        if(px<_liveBar.low)_liveBar.low=px;
      }}
      var haC=(_liveBar.open+_liveBar.high+_liveBar.low+_liveBar.close)/4;
      var haO=_liveBar.haOpen;
      var haH=Math.max(_liveBar.high,haO,haC);
      var haL=Math.min(_liveBar.low,haO,haC);
      cS.update({{time:barT,open:haO,high:haH,low:haL,close:haC}});
      // Extend SMA/MACD lines to live bar using last values + live close
      if(_lastSMAs){{
        var liveCls=_lastSMAs.cls.concat([px]);
        var liveS20=liveCls.slice(-20).reduce(function(a,b){{return a+b;}},0)/Math.min(20,liveCls.length);
        var liveS50=liveCls.slice(-50).reduce(function(a,b){{return a+b;}},0)/Math.min(50,liveCls.length);
        var liveS100=liveCls.slice(-100).reduce(function(a,b){{return a+b;}},0)/Math.min(100,liveCls.length);
        var liveS200=liveCls.slice(-200).reduce(function(a,b){{return a+b;}},0)/Math.min(200,liveCls.length);
        try{{if(e20S) e20S.update({{time:barT,value:liveS20}});}}catch(e){{}}
        try{{if(e50S) e50S.update({{time:barT,value:liveS50}});}}catch(e){{}}
        try{{if(e100S)e100S.update({{time:barT,value:liveS100}});}}catch(e){{}}
        try{{if(e200S)e200S.update({{time:barT,value:liveS200}});}}catch(e){{}}
        // Extend MACD flat to live bar (approximate)
        try{{if(macdLS)macdLS.update({{time:barT,value:_lastSMAs.macd}});}}catch(e){{}}
        try{{if(macdSS)macdSS.update({{time:barT,value:_lastSMAs.sig}});}}catch(e){{}}
        try{{if(macdHS)macdHS.update({{time:barT,value:_lastSMAs.hist,
          color:_lastSMAs.hist>=0?'#26a69a':'#ef5350'}});}}catch(e){{}}
      }}
      // Only scroll on new bar — not every tick (avoids flicker)
      if(!_liveBar._scrolled){{
        _liveBar._scrolled=true;
        try{{chart.timeScale().scrollToRealTime();}}catch(e){{}}
        try{{if(macdChart)macdChart.timeScale().scrollToRealTime();}}catch(e){{}}
      }}
    }}catch(ex){{}}
  }}
}}

// WebSocket for sub-second updates (supplements REST)
function _wsConnect(){{
  if(_ws){{try{{_ws.close();}}catch(e){{}}}}
  _ws=new WebSocket('wss://stream.bybit.com/v5/public/linear');
  _ws.onopen=function(){{
    var args=_wsSyms.map(function(s){{return'tickers.'+s;}});
    if(args.length)_ws.send(JSON.stringify({{op:'subscribe',args:args}}));
    var pill=el('live-pill');
    if(pill)pill.style.boxShadow='0 0 0 2px rgba(0,230,118,.4)';
  }};
  _ws.onmessage=function(e){{
    try{{
      var m=JSON.parse(e.data);
      if(!m.topic||m.topic.indexOf('tickers.')!==0||!m.data||!m.data.lastPrice)return;
      var t=m.data;
      _updateSymPrice(t.symbol,parseFloat(t.lastPrice),parseFloat(t.price24hPcnt||0)*100,
        parseFloat(t.highPrice24h||0),parseFloat(t.lowPrice24h||0),parseFloat(t.volume24h||0));
    }}catch(e){{}}
  }};
  _ws.onclose=function(){{
    var pill=el('live-pill');
    if(pill)pill.style.boxShadow='0 0 0 2px rgba(255,59,92,.4)';
    setTimeout(_wsConnect,4000);
  }};
  _ws.onerror=function(){{try{{_ws.close();}}catch(e){{}}}};
}}

// Start 1-second REST polling (guaranteed updates for ALL symbols)
function startLivePrices(){{
  _wsSyms=B.map(function(b){{return b.symbol;}});
  _fetchAllTickers();
  _tickTimer=setInterval(_fetchAllTickers,1000);
  _wsConnect();
}}

document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeChart();}});
startLivePrices();
setCounts();
renderBotList();
goView('overview');

// Fetch exact realized PnL from Bybit via server every 30s
function fetchExactPnl(){{
  fetch('/api/pnl').then(function(r){{return r.json();}}).then(function(data){{
    var totalPnl=0, totalCt=0;
    B.forEach(function(b){{
      var d=data[b.symbol];
      if(!d||!d.ct)return;
      totalPnl+=d.total; totalCt+=d.ct;
      // Update per-bot realized PnL cell if visible
      var row=document.querySelector('#bot-list-body tr[data-sym="'+b.symbol+'"]');
      if(!row)return;
      var cell=row.cells[7];
      if(!cell)return;
      var pc=d.total>=0?'col-g':'col-r';
      cell.innerHTML='<span class="'+pc+'" style="font-weight:700">'+(d.total>=0?'+':'')+d.total.toFixed(4)
        +'<span style="font-size:8px;opacity:.4;margin-left:4px">bybit</span></span>';
    }});
    // Update overview metric
    var rEl=el('metric-rpnl');
    if(rEl){{
      rEl.textContent=(totalPnl>=0?'+':'')+totalPnl.toFixed(4)+' USDT';
      rEl.className='met-v num '+(totalPnl>=0?'col-g':'col-r');
    }}
    var rCt=el('m-rct');
    if(rCt)rCt.textContent=totalCt+' closed';
  }}).catch(function(){{}});
}}
fetchExactPnl();
setInterval(fetchExactPnl, 30000);

// ── Bybit live data — updates ALL metrics from exchange ──────────
function fetchBybit(){{
  fetch('/api/bybit').then(function(r){{return r.json();}}).then(function(d){{
    if(!d.ok)return;
    // Balance
    var bel=el('m-bal');
    if(bel){{bel.textContent='$'+d.balance.toFixed(2);bel.className='met-v col-g num';}}
    // Realized PnL
    var rel=el('m-rpnl');
    if(rel){{
      rel.textContent=(d.total_realized>=0?'+':'')+d.total_realized.toFixed(4)+' USDT';
      rel.className='met-v '+(d.total_realized>=0?'col-g':'col-r')+' num';
    }}
    // Unrealized PnL
    var uel=el('m-upnl');
    if(uel){{
      uel.textContent=(d.total_unrealized>=0?'+':'')+d.total_unrealized.toFixed(4)+' USDT';
      uel.className='met-v '+(d.total_unrealized>=0?'col-g':'col-r')+' num';
    }}
    // Win rate overall
    var tot=d.wins+d.losses;
    var wr=tot>0?(d.wins/tot*100).toFixed(1):'0.0';
    var wrel=el('m-wr');if(wrel){{wrel.textContent=wr+'%';wrel.className='met-v '+(parseFloat(wr)>=50?'col-g':parseFloat(wr)>=35?'col-o':'col-r')+' num';}}
    var wlel=el('m-wl');if(wlel)wlel.textContent=d.wins+'W · '+d.losses+'L';
    var rCt2=document.getElementById('m-rct');
    if(rCt2)rCt2.textContent=(d.wins+d.losses)+' closed';
    // Best / worst bot
    var syms=Object.keys(d.closed);
    if(syms.length>0){{
      syms.sort(function(a,b){{return d.closed[b].total-d.closed[a].total;}});
      var best=syms[0],worst=syms[syms.length-1];
      var bst=el('m-best');
      if(bst)bst.textContent=best.replace('USDT','')+' $'+(d.closed[best].total>=0?'+':'')+d.closed[best].total.toFixed(4);
      var wst=el('m-worst');
      if(wst)wst.textContent=worst.replace('USDT','')+' $'+d.closed[worst].total.toFixed(4);
    }}
    // Per-bot rows
    B.forEach(function(b){{
      var sym=b.symbol;
      var row=document.querySelector('#bot-list-body tr[data-sym="'+sym+'"]');
      if(!row)return;
      // Unrealized
      var pos=d.positions[sym];
      if(pos){{
        var uc=row.cells[6];
        if(uc)uc.innerHTML='<span class="'+(pos.unrealized>=0?'col-g':'col-r')+'" style="font-weight:700">'+(pos.unrealized>=0?'+':'')+pos.unrealized.toFixed(4)+'</span>';
      }}
      // Realized + W/L + WinRate
      var cl=d.closed[sym];
      var hrow=document.querySelector('#hist-body tr[data-hsym="'+sym+'"]');
      if(cl){{
        var rc=row&&row.cells[7];
        if(rc)rc.innerHTML='<span class="'+(cl.total>=0?'col-g':'col-r')+'" style="font-weight:700">'+(cl.total>=0?'+':'')+cl.total.toFixed(4)+'<span style="font-size:8px;opacity:.4;margin-left:4px">bybit</span></span>';
        var wc=row&&row.cells[8];
        if(wc)wc.textContent=cl.wins+' / '+cl.losses;
        var wroc=row&&row.cells[9];
        var t2=cl.wins+cl.losses;
        if(wroc&&t2>0){{
          var wr2=(cl.wins/t2*100).toFixed(1);
          var wrc2=parseFloat(wr2)>=50?'var(--g)':parseFloat(wr2)>=35?'var(--o)':'var(--r)';
          wroc.innerHTML='<div style="display:flex;align-items:center;gap:5px;min-width:70px">'
            +'<div style="flex:1;height:2px;background:#111;border-radius:1px;overflow:hidden;min-width:30px;max-width:50px">'
              +'<div style="height:100%;border-radius:1px;width:'+wr2+'%;background:'+wrc2+'"></div>'
            +'</div>'
            +'<span style="color:'+wrc2+';font-weight:700;font-size:11px;min-width:28px;text-align:right">'+wr2+'%</span>'
          +'</div>';
        }}
        // Update history table: Exact PnL (8), wins (4), losses (5), trades (3), wr (6)
        if(hrow){{
          var hep=hrow.cells[8];
          if(hep)hep.innerHTML='<span class="'+(cl.total>=0?'col-g':'col-r')+'" style="font-weight:700">'+(cl.total>=0?'+':'')+cl.total.toFixed(4)+'</span>';
          if(t2>0){{
            var ht=hrow.cells[3];if(ht)ht.textContent=t2;
            var hww=hrow.cells[4];if(hww)hww.textContent=cl.wins;
            var hwl=hrow.cells[5];if(hwl)hwl.textContent=cl.losses;
            var hwr=hrow.cells[6];
            if(hwr){{
              var wr3=(cl.wins/t2*100).toFixed(1);
              var wrc3=parseFloat(wr3)>=50?'var(--g)':parseFloat(wr3)>=35?'var(--o)':'var(--r)';
              hwr.innerHTML='<div style="display:flex;align-items:center;gap:5px">'
                +'<div style="flex:1;height:2px;background:#111;border-radius:1px;overflow:hidden;min-width:30px;max-width:50px">'
                  +'<div style="height:100%;border-radius:1px;width:'+wr3+'%;background:'+wrc3+'"></div>'
                +'</div>'
                +'<span style="color:'+wrc3+';font-weight:700;font-size:11px;min-width:28px">'+wr3+'%</span>'
              +'</div>';
            }}
          }}
        }}
        // Re-sort history table by Exact PnL after each update
        _histDirty=true;
      }}
    }});
  // Re-sort history table if any row was updated
  if(_histDirty){{
    _histDirty=false;
    var htb=el('hist-body');
    if(htb){{
      var rows=Array.from(htb.rows);
      rows.sort(function(a,b){{
        // Sort by Exact PnL cell (8) value, descending
        function getPnlFromRow(r){{
          var c=r.cells[8];
          if(!c)return 0;
          var txt=c.textContent.replace(/[^0-9.+-]/g,'');
          return parseFloat(txt)||0;
        }}
        return getPnlFromRow(b)-getPnlFromRow(a);
      }});
      rows.forEach(function(r){{htb.appendChild(r);}});
    }}
  }}
  }}).catch(function(){{}});
}}
var _histDirty=false;
fetchBybit();
setInterval(fetchBybit,15000);
</script>
</body>
</html>"""


def build(directory="."):
    bots    = discover(directory)
    syms    = list(dict.fromkeys(b["symbol"] for b in bots))
    px      = get_prices(syms) if syms else {}
    return generate(bots, px, get_balance())

def run_file(directory="."):
    print(f"Dashboard → {OUTPUT_FILE}  (refresh {REFRESH_SEC}s)")
    print("Open dashboard.html in browser · Ctrl+C to stop\n")
    while True:
        try:
            html = build(directory)
            with open(OUTPUT_FILE,"w",encoding="utf-8") as f: f.write(html)
            bots  = discover(directory)
            open_ = sum(1 for b in bots if b["state"].get("in_trade"))
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] {len(bots)} bots | {open_} open | bal=${_bal:.2f} | OK    ",end="",flush=True)
        except Exception as e:
            print(f"\nError: {e}")
        time.sleep(REFRESH_SEC)

# ── Server-side PnL cache (fetched from Bybit, refreshed every 60s) ──
import threading as _threading
_pnl_cache = {}        # {symbol: {"total":float,"ct":int,"ts":float}}
_pnl_lock  = _threading.Lock()

def _fetch_pnl_for(symbol):
    """Fetch exact realized PnL for one symbol from Bybit."""
    key, secret = _load_keys()
    if not key or not secret: return None
    try:
        ts  = str(int(time.time() * 1000))
        rw  = "5000"
        qs  = f"category=linear&symbol={symbol}&limit=50"
        sig = hmac.new(secret.encode(), (ts+key+rw+qs).encode(), hashlib.sha256).hexdigest()
        r = requests.get(f"{BYBIT_API}/v5/position/closed-pnl",
            params={"category":"linear","symbol":symbol,"limit":50}, timeout=5,
            headers={"X-BAPI-API-KEY":key,"X-BAPI-TIMESTAMP":ts,
                     "X-BAPI-SIGN":sig,"X-BAPI-RECV-WINDOW":rw}).json()
        if r.get("retCode") != 0: return None
        trades = r["result"]["list"]
        total  = round(sum(float(t.get("closedPnl",0)) for t in trades), 6)
        return {"total":total, "ct":len(trades), "ts":time.time()}
    except: return None

def _refresh_pnl_cache(symbols):
    """Background thread: refresh PnL for all symbols."""
    for sym in symbols:
        cached = _pnl_cache.get(sym)
        if cached and time.time() - cached["ts"] < 60:
            continue  # fresh enough
        result = _fetch_pnl_for(sym)
        if result is not None:
            with _pnl_lock:
                _pnl_cache[sym] = result

def run_server(directory="."):
    import http.server, socketserver, threading
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            # ── /api/pnl — returns Bybit realized PnL as JSON ────
            if self.path == "/api/bybit":
                try:
                    # Always return cached data immediately — never block on API calls
                    # Background thread refreshes every 60s
                    if time.time()-_bybit_cache_ts > 60:
                        import threading as _t2
                        _t2.Thread(target=_bybit_fetch, daemon=True).start()
                    data = _bybit_cache if _bybit_cache else {"ok":False,"balance":0,
                        "positions":{},"closed":{},"total_realized":0,
                        "total_unrealized":0,"wins":0,"losses":0}
                    jdata = json.dumps(data).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    self.send_header("Content-Length",str(len(jdata)))
                    self.send_header("Cache-Control","no-cache")
                    self.end_headers()
                    try: self.wfile.write(jdata)
                    except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError,OSError): pass
                    return
                except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError,OSError): return
                except Exception as e:
                    try: self.send_error(500,str(e))
                    except: pass
                    return
            if self.path == "/api/pnl":
                try:
                    # Return cached pnl immediately, refresh in background
                    bots = discover(directory)
                    syms = list(dict.fromkeys(b["symbol"] for b in bots))
                    import threading as _tpnl
                    _tpnl.Thread(target=_refresh_pnl_cache,args=(syms,),daemon=True).start()
                    with _pnl_lock:
                        data = {s: _pnl_cache.get(s,{"total":0,"ct":0}) for s in syms}
                    jdata = json.dumps(data).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    self.send_header("Content-Length",str(len(jdata)))
                    self.send_header("Cache-Control","no-cache")
                    self.end_headers()
                    try: self.wfile.write(jdata)
                    except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError,OSError): pass
                    return
                except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError,OSError): return
                except Exception as e:
                    try: self.send_error(500,str(e))
                    except: pass
                    return
            # ── Main dashboard HTML ───────────────────────────────
            try:
                html = build(directory).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.send_header("Cache-Control","no-cache, no-store, must-revalidate")
                self.end_headers()
                try:
                    try:
                        self.wfile.write(html)
                    except (BrokenPipeError,ConnectionAbortedError,OSError): return
                except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError,OSError): return
                bots = discover(directory)
                open_ = sum(1 for b in bots if b["state"].get("in_trade"))
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] {len(bots)} bots | {open_} open | bal=${_bal:.2f} | served    ", end="", flush=True)
            except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError,OSError): return
            except Exception as e:
                try: self.send_error(500, str(e))
                except: pass
        def log_message(self, *a): pass  # suppress request logs
    socketserver.TCPServer.allow_reuse_address = True
    socketserver.TCPServer.allow_reuse_address = True

    class QuietTCPServer(socketserver.TCPServer):
        def handle_error(self, request, client_address):
            # Suppress noisy phone-disconnect errors (WinError 10054, BrokenPipe etc.)
            import sys as _sys
            exc = _sys.exc_info()[1]
            if isinstance(exc, (ConnectionResetError, BrokenPipeError,
                                ConnectionAbortedError, OSError)):
                return
            super().handle_error(request, client_address)

    with QuietTCPServer(("0.0.0.0", PORT), Handler) as srv:
        import socket as _sock
        # Detect ALL local IPs (WiFi, Ethernet, VPN, hotspot)
        all_ips = []
        try:
            # Get all network interfaces
            hostname = _sock.gethostname()
            infos = _sock.getaddrinfo(hostname, None)
            seen = set()
            for info in infos:
                ip = info[4][0]
                if ip not in seen and not ip.startswith("127.") and ":" not in ip:
                    seen.add(ip); all_ips.append(ip)
        except: pass
        # Fallback: use socket connect trick to find outbound IP
        if not all_ips:
            try:
                s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                all_ips = [s.getsockname()[0]]
                s.close()
            except: all_ips = ["YOUR_PC_IP"]
        print()
        print("  ╔══════════════════════════════════════════════╗")
        print(f"  ║  SHACKOBOT running on port {PORT:<18}║")
        print(f"  ║  PC:    http://localhost:{PORT:<20}║")
        for ip in all_ips:
            label = f"http://{ip}:{PORT}"
            print(f"  ║  LAN:   {label:<36}║")
        print( "  ║  (phone must be on same WiFi)               ║")
        print( "  ╚══════════════════════════════════════════════╝")
        print()
        print("  If phone can't connect, run in PowerShell (Admin):")
        print(f"  netsh advfirewall firewall add rule name=SHACKOBOT dir=in action=allow protocol=TCP localport={PORT}")
        print()
        # Pre-warm Bybit cache so first request returns instantly
        import threading as _t3
        _t3.Thread(target=_bybit_fetch, daemon=True).start()
        srv.serve_forever()

if __name__ == "__main__":
    d = "."
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args: d = args[0]
    if "--file" in sys.argv:
        run_file(d)
    else:
        print(f"SHACKOBOT Dashboard")
        print(f"Directory: {os.path.abspath(d)}")
        run_server(d)
