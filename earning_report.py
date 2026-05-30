import requests
import json
import time
import os
from datetime import datetime
from pathlib import Path

API_KEY = os.getenv('ALPHA_VANTAGE_KEY')
BASE = Path(__file__).resolve().parent
STRUCT_P = BASE / "structure.json"
RESEARCH_P = BASE / "research_report.json"
OUT_P = BASE / "earnings_dates.json"

# cache TTL (seconds) - default 24 hours
DEFAULT_TTL = int(os.getenv('EARNINGS_TTL', 24*3600))


def read_cache():
    if OUT_P.exists():
        try:
            return json.loads(OUT_P.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def write_cache(d):
    try:
        OUT_P.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def is_entry_fresh(entry: dict, ttl: int = DEFAULT_TTL) -> bool:
    if not entry:
        return False
    ts = entry.get('_ts')
    if not ts:
        return False
    try:
        age = time.time() - float(ts)
        return age <= ttl
    except Exception:
        return False


def parse_alpha_vantage_response(text: str):
    # Try JSON first
    try:
        j = json.loads(text)
        if isinstance(j, dict) and 'earningsCalendar' in j:
            cal = j['earningsCalendar']
            if isinstance(cal, list) and len(cal) > 0:
                first = cal[0]
                return first.get('reportDate') or first.get('reportDateGMT')
    except Exception:
        pass

    # Fallback to CSV parsing
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) >= 2:
        row = lines[1].split(',')
        if len(row) >= 3:
            return row[2].strip()
    return None


def fetch_earnings_for_symbol(symbol: str, force: bool = False, ttl: int = DEFAULT_TTL):
    """Fetch or return cached earnings data for a single symbol.

    Returns None if no data available; otherwise returns dict {next_earnings_date, earnings_countdown}
    """
    cache = read_cache()
    entry = cache.get(symbol)

    if entry and not force and is_entry_fresh(entry, ttl) and entry.get('data'):
        return entry.get('data')

    # If no API key provided, do not attempt network call; return cached data if any
    if not API_KEY:
        return entry.get('data') if entry else None

    url = (
        "https://www.alphavantage.co/query"
        f"?function=EARNINGS_CALENDAR"
        f"&symbol={symbol}"
        f"&horizon=3month"
        f"&apikey={API_KEY}"
    )
    try:
        r = requests.get(url, timeout=20)
    except Exception:
        return entry.get('data') if entry else None

    if r.status_code != 200:
        return entry.get('data') if entry else None

    date_str = parse_alpha_vantage_response(r.text)
    if not date_str:
        # save raw sample to cache with empty data so we don't hammer API repeatedly
        cache[symbol] = {'_ts': time.time(), 'data': None, 'raw': r.text[:200]}
        write_cache(cache)
        return entry.get('data') if entry else None

    # normalize
    try:
        dt = None
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(date_str[:19], fmt)
                break
            except Exception:
                dt = None
        if dt is None:
            return entry.get('data') if entry else None
        e_date = dt.date()
        countdown = (e_date - datetime.utcnow().date()).days
        data = {'next_earnings_date': e_date.isoformat(), 'earnings_countdown': countdown}
    except Exception:
        data = {'raw': date_str}

    cache[symbol] = {'_ts': time.time(), 'data': data}
    write_cache(cache)
    # polite sleep for free API
    time.sleep(12)
    return data


def main(symbols=None, force: bool = False):
    """Batch fetch earnings for a list of symbols. If symbols is None, use structure.json."""
    if symbols is None:
        if not STRUCT_P.exists():
            print('structure.json not found')
            return
        struct = json.loads(STRUCT_P.read_text(encoding='utf-8'))
        symbols = []

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == 'symbols' and isinstance(v, list):
                        symbols.extend(v)
                    else:
                        walk(v)
            elif isinstance(o, list):
                for i in o:
                    walk(i)

        walk(struct)

    results = {}
    for i, sym in enumerate(sorted(set(symbols)), 1):
        print(f"[{i}/{len(symbols)}] {sym} -> fetching earnings...", end=' ')
        d = fetch_earnings_for_symbol(sym, force=force)
        if not d:
            print('no data')
            results[sym] = None
        else:
            print(d.get('next_earnings_date') if d.get('next_earnings_date') else d)
            results[sym] = d

    # write cache already handled per-symbol; merge into research_report.json if exists
    if RESEARCH_P.exists():
        try:
            research = json.loads(RESEARCH_P.read_text(encoding='utf-8'))
        except Exception:
            research = {}
        changed = False
        for sym, info in results.items():
            if not info:
                continue
            if sym in research:
                research[sym]['next_earnings_date'] = info.get('next_earnings_date')
                research[sym]['earnings_countdown'] = info.get('earnings_countdown')
                changed = True
        if changed:
            RESEARCH_P.write_text(json.dumps(research, ensure_ascii=False, indent=2), encoding='utf-8')
            print('research_report.json updated with earnings dates')


if __name__ == '__main__':
    main()