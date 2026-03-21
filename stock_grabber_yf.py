import requests
import json
import numpy as np
from datetime import datetime
import time
import os
import yfinance as yf
from requests.exceptions import RequestException

# IEX Cloud API 配置

# fallback using yfinance when IEX not available

def fetch_stock_data_yf(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        price = info.get('currentPrice') or info.get('regularMarketPrice') or 0.0
        pe_ratio = info.get('trailingPE') or info.get('forwardPE') or info.get('peRatio') or 0.0
        eps = info.get('trailingEps') or info.get('forwardEps') or 0.0
        revenue_ttm = info.get('totalRevenue') or info.get('revenue') or 0.0
        market_cap = info.get('marketCap') or (price * info.get('sharesOutstanding', 0) if price and info.get('sharesOutstanding') else 0)
        return {
            'symbol': symbol,
            'price': round(price, 2),
            'change_percent': 0.0,
            'change_str': 'N/A',
            'market_cap': '--' if not market_cap else f"{market_cap}",
            'market_cap_value': market_cap,
            'pe_ratio': round(pe_ratio, 2) if pe_ratio else 0.0,
            'peg_ratio': 0.0,
            'eps': round(eps, 2) if eps else 0.0,
            'revenue_ttm': revenue_ttm,
            'is_positive': True
        }
    except Exception as e:
        print(f"⚠ yf fallback failed for {symbol}: {e}")
        return get_error_stock_data(symbol)


def fetch_stock_data(symbol):
    # Use yfinance only (no IEX) per user request
    return fetch_stock_data_yf(symbol)

def get_error_stock_data(symbol):
    """返回錯誤時的預設數據結構"""
    return {
        'symbol': symbol,
        'price': 0.0,
        'change_percent': 0.0,
        'change_str': 'Error',
        'market_cap': '--',
        'market_cap_value': 0,
        'pe_ratio': 0.0,
        'peg_ratio': 0.0,
        'eps': 0.0,
        'revenue_ttm': 0.0,
        'is_positive': False
    }

# ============ 計算扇區平均數據 ============
def calculate_sector_stats(stocks_list):
    """計算扇區平均統計"""
    stocks_data = []
    
    # IEX Cloud 免費方案足夠支持正常速度的請求
    for i, symbol in enumerate(stocks_list):
        stocks_data.append(fetch_stock_data(symbol))
        
        # 每個請求間隔 0.1 秒（IEX Cloud 可以支持更高的頻率）
        if i < len(stocks_list) - 1:
            time.sleep(0.1)
    
    # 計算平均漲跌
    changes = [s['change_percent'] for s in stocks_data if s['change_percent'] != 0]
    avg_change = sum(changes) / len(changes) if changes else 0.0
    
    # 計算平均 PE 和 PEG（目前 Alpha Vantage 免費版不提供）
    pes = [s['pe_ratio'] for s in stocks_data if s['pe_ratio'] > 0]
    pegs = [s['peg_ratio'] for s in stocks_data if s['peg_ratio'] > 0]

    avg_pe = np.median(pes) if pes else 0.0
    avg_peg = np.median(pegs) if pegs else 0.0
    
    # 計算平均 P/S
    ps_ratios = []
    for s in stocks_data:
        if s['revenue_ttm'] > 0 and s['market_cap_value'] > 0:
            ps = s['market_cap_value'] / s['revenue_ttm']
            ps_ratios.append(ps)
    avg_ps = sum(ps_ratios) / len(ps_ratios) if ps_ratios else 0.0
    
    return {
        'stocks': stocks_data,
        'avg_change': round(avg_change, 2),
        'avg_change_str': f"{avg_change:+.2f}%",
        'is_positive': avg_change >= 0,
        'avg_pe': round(avg_pe, 2),
        'avg_peg': round(avg_peg, 2),
        'avg_ps': round(avg_ps, 2),
        'count': len(stocks_data)
    }

# ---------- helpers for research_report generation ----------

def clean_val(val):
    if val is None:
        return None
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def secure_round(val, precision):
    c = clean_val(val)
    if c is None:
        return None
    return round(c, precision)


def get_default_fields(symbol, theme, sector_id, cfg):
    return {
        'editor_note': '請填入個人觀點...',
        'theme': theme,
        'theme_display_name': cfg.get('theme_display_name', ''),
        'sector_id': sector_id,
        'sector_name': cfg.get('name', ''),
        'calc_type': (cfg.get('logic_type', 'ps').split('_')[0] if isinstance(cfg.get('logic_type', 'ps'), str) else 'ps'),
        'insight_link': cfg.get('insight_link', f"/insight/{symbol.lower()}"),
        'tag': cfg.get('tag', 'grey'),
        'default_params': cfg.get('default_params', {}),
        'market_consensus_eps_current': None,
        'market_consensus_eps_forward': None,
        'calc_growth': None,
        'growth_estimate': None,
        'revenue_estimate': None,
        'future_revenue_per_share': None,
        'shares_outstanding': None,
        'current_price': None,
        'ps': None,
        'pb': None,
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

# ---------- New main: build research_report.json from structure.json ----------

print("開始根據 structure.json 生成 research_report.json...")
base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, 'structure.json')
output_path = os.path.join(base_dir, 'research_report.json')

# read structure
try:
    with open(config_path, 'r', encoding='utf-8') as f:
        structure = json.load(f)
        themes_config = structure.get('themes', {})
except Exception as e:
    print(f"❌ 無法讀取 structure.json: {e}")
    themes_config = {}

# load existing master data if present
try:
    with open(output_path, 'r', encoding='utf-8') as f:
        master_data = json.load(f)
except FileNotFoundError:
    master_data = {}

# iterate
for theme, theme_info in themes_config.items():
    theme_display_name = theme_info.get('display_name', theme)
    clusters = theme_info.get('clusters', {})
    for sector_id, cfg in clusters.items():
        cfg['theme_display_name'] = theme_display_name
        print(f"\n📂 主題: {theme_display_name} | 板塊：{cfg.get('name')}")
        for symbol in cfg.get('symbols', []):
            print(f"  > 處理: {symbol}")
            # init or reset structure for this symbol
            if symbol not in master_data:
                master_data[symbol] = get_default_fields(symbol, theme, sector_id, cfg)
            else:
                # keep editor_note, but reset other fields to defaults to avoid stale keys
                note = master_data[symbol].get('editor_note', '請填入個人觀點...')
                master_data[symbol] = get_default_fields(symbol, theme, sector_id, cfg)
                master_data[symbol]['editor_note'] = note

            # fetch market/financial data (IEX primary, yfinance fallback)
            market = fetch_stock_data(symbol)

            # also use yfinance ticker for earnings estimates and shares/book
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info or {}
            except Exception:
                info = {}

            # earnings est extraction (similar to earlier logic)
            eps_current = 0.0
            eps_forward = 0.0
            growth_estimate = None
            try:
                est = getattr(ticker, 'earnings_estimate', None)
                if est is not None and hasattr(est, 'empty') and not est.empty:
                    if '+1y' in est.index:
                        growth_val = est.loc['+1y', 'growth']
                        try:
                            growth_estimate = float(growth_val)
                        except Exception:
                            growth_estimate = None
                    if '0y' in est.index:
                        try:
                            eps_current = float(est.loc['0y', 'yearAgoEps'])
                            eps_forward = float(est.loc['0y', 'avg'])
                        except Exception:
                            eps_current = eps_forward = 0.0
                    else:
                        try:
                            eps_current = float(est.iloc[0]['yearAgoEps'])
                            eps_forward = float(est.iloc[0]['avg'])
                        except Exception:
                            eps_current = eps_forward = 0.0
                else:
                    val_trailing = info.get('trailingEps') or info.get('trailingEps')
                    val_forward = info.get('forwardEps')
                    eps_current = float(val_trailing) if val_trailing is not None else 0.0
                    eps_forward = float(val_forward) if val_forward is not None else 0.0
            except Exception:
                try:
                    val_trailing = info.get('trailingEps')
                    val_forward = info.get('forwardEps')
                    eps_current = float(val_trailing) if val_trailing is not None else 0.0
                    eps_forward = float(val_forward) if val_forward is not None else 0.0
                except Exception:
                    eps_current = eps_forward = 0.0

            # --- Normalization & sanity checks for growth_estimate ---
            if growth_estimate is not None:
                raw = growth_estimate
                # If value looks like a percent (e.g., 10 or 1068), convert to fraction
                # Expected typical growth_estimate values are small fractions (e.g., 0.25 for 25%)
                if abs(raw) > 5:
                    # treat as percent -> divide by 100
                    try:
                        growth_estimate = raw / 100.0
                    except Exception:
                        growth_estimate = None
                # clamp absurd outliers to +/-500% (5.0) to avoid UI blowups
                if growth_estimate is not None and abs(growth_estimate) > 5.0:
                    growth_estimate = 5.0 if growth_estimate > 0 else -5.0
                # debug: log suspicious values (very large or NaN)
                if growth_estimate is None or abs(growth_estimate) > 1.0:
                    # only print for debugging during development; comment out in production if noisy
                    print(f"⚠ [{symbol}] normalized growth_estimate from {raw} -> {growth_estimate}")

            # 如果仍為 None，嘗試使用 cluster 的 fallback_growth
            if growth_estimate is None:
                try:
                    fb = cfg.get('default_params', {}).get('fallback_growth')
                    if fb is not None:
                        growth_estimate = float(fb)
                        # 若看起來像百分比值 (例如 10 或 1068)，則除以100
                        if abs(growth_estimate) > 5:
                            growth_estimate = growth_estimate / 100.0
                        # clamp 到 +/-500%
                        if abs(growth_estimate) > 5.0:
                            growth_estimate = 5.0 if growth_estimate > 0 else -5.0
                        print(f"ℹ [{symbol}] applied fallback_growth from cluster: {fb} -> {growth_estimate}")
                except Exception:
                    growth_estimate = None

            # compute shares_outstanding defensively FIRST so it's available for fallback calculations
            so = None
            if info.get('sharesOutstanding'):
                so = clean_val(info.get('sharesOutstanding'))
            else:
                mcap = market.get('market_cap_value')
                mprice = market.get('price')
                if mcap and mprice:
                    try:
                        so = clean_val(float(mcap) / float(mprice))
                    except Exception:
                        so = None
            shares_outstanding = so

            # --- 強化版通用前瞻營收抓取 ---
            revenue_estimate = None
            try:
                # 1. 優先權最高：抓取 yfinance 新版的 revenue_estimate 表
                # 這會直接回傳包含 '0y' 當前財年預估的 DataFrame
                rev_est_table = getattr(ticker, 'revenue_estimate', None)
                if rev_est_table is not None and not rev_est_table.empty:
                    if '0y' in rev_est_table.index and 'avg' in rev_est_table.columns:
                        revenue_estimate = clean_val(rev_est_table.loc['0y', 'avg'])
                        if revenue_estimate is not None:
                            print(f"  🎯 [{symbol}] 從 revenue_estimate 抓到 Forward Revenue: {revenue_estimate/1e9:.2f}B")

                # 2. 如果 1 沒抓到，嘗試從 earnings_estimate 找 (舊版邏輯)
                if not revenue_estimate:
                    est_table = getattr(ticker, 'earnings_estimate', None)
                    if est_table is not None and not est_table.empty:
                        if '0y' in est_table.index and 'revenue' in est_table.columns:
                            potential_rev = est_table.loc['0y', 'revenue']
                            if potential_rev and potential_rev > 0:
                                revenue_estimate = clean_val(potential_rev)

                # 3. 嘗試利用 .calendar
                if not revenue_estimate:
                    cal = getattr(ticker, 'calendar', None)
                    if isinstance(cal, dict) and 'Revenue Estimate' in cal:
                        revenue_estimate = clean_val(cal['Revenue Estimate'].get('Avg'))

                # 4. 從 info 的 forward target 挖掘
                if not revenue_estimate:
                    revenue_estimate = clean_val(info.get('revenueEstimate') or info.get('targetRevenue'))

                # 5. 終極 Fallback：如果連分析師預估都沒有，才用 TTM
                if not revenue_estimate:
                    revenue_estimate = clean_val(info.get('totalRevenue') or info.get('revenue'))

            except Exception as e:
                print(f"  ⚠ [{symbol}] 通用營收抓取失敗，回退至 TTM: {e}")
                revenue_estimate = clean_val(info.get('totalRevenue') or info.get('revenue'))
            
            # --- 最終計算：這會自動套用到所有股票 ---
            future_rev_ps = None
            if revenue_estimate and shares_outstanding and shares_outstanding > 0:
                future_rev_ps = round(float(revenue_estimate) / float(shares_outstanding), 4)
            elif info.get('revenuePerShare'):
                future_rev_ps = clean_val(info.get('revenuePerShare'))

            # current price
            current_price = clean_val(market.get('price') or info.get('currentPrice') or info.get('regularMarketPrice'))

            # compute ps and pb
            ps_val = None
            try:
                mcap_val = market.get('market_cap_value')
                if mcap_val and revenue_estimate and revenue_estimate > 0:
                    ps_val = round(float(mcap_val) / float(revenue_estimate), 2)
            except Exception:
                ps_val = None

            pb_val = None
            try:
                book_val = info.get('bookValue')
                if book_val and current_price:
                    pb_val = round(current_price / float(book_val), 2)
            except Exception:
                pb_val = None

            # default params
            default_params = cfg.get('default_params', {})

            growth = (eps_forward - eps_current) / eps_current if eps_current and eps_current > 0 else None

            master_data[symbol].update({
                'theme': theme,
                'theme_display_name': theme_display_name,
                'sector_id': sector_id,
                'sector_name': cfg.get('name'),
                'calc_type': (cfg.get('logic_type', 'ps').split('_')[0] if isinstance(cfg.get('logic_type', 'ps'), str) else 'ps'),
                'insight_link': cfg.get('insight_link', master_data[symbol].get('insight_link')),
                'tag': cfg.get('tag', master_data[symbol].get('tag', 'grey')),
                'market_consensus_eps_current': secure_round(eps_current, 4),
                'market_consensus_eps_forward': secure_round(eps_forward, 4),
                'calc_growth': secure_round(growth, 4) if growth is not None else None,
                'growth_estimate': secure_round(growth_estimate, 4) if growth_estimate is not None else None,
                'revenue_estimate': revenue_estimate,
                'future_revenue_per_share': secure_round(future_rev_ps, 4),
                'shares_outstanding': shares_outstanding,
                'current_price': current_price,
                'ps': ps_val,
                'pb': pb_val,
                'default_params': default_params,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

# write out
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(master_data, f, ensure_ascii=False, indent=4)

print(f"\n✅ 所有主題與板塊更新完成！輸出檔案：{output_path}")