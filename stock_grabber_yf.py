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
        'calc_type': (cfg.get('logic_type', 'ps') if isinstance(cfg.get('logic_type', 'ps'), str) else 'ps'),
        'insight_link': cfg.get('insight_link', f"/insight/{symbol.lower()}"),
        'tag': cfg.get('tag', 'grey'),
        'default_params': cfg.get('default_params', {}),
        'market_consensus_eps_current': None,  # TTM EPS
        'market_consensus_eps_forward': None,  # Forward EPS
        'growth_estimate': None,  # 分析師預估成長率（移除 calc_growth 冗余字段）
        'revenue_estimate': None,
        'future_revenue_per_share': None,
        'ps_forward': None,  # Forward P/S（隱含）
        'target_pe_market': None,
        'analyst_target': None,
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
except (FileNotFoundError, json.JSONDecodeError):
    master_data = {}

# iterate through themes -> sectors -> clusters
for theme, theme_info in themes_config.items():
    theme_display_name = theme_info.get('display_name', theme)
    sectors = theme_info.get('sectors', {})
    
    for sector_id, sector_info in sectors.items():
        sector_name = sector_info.get('name', sector_id)
        clusters = sector_info.get('clusters', {})
        
        for cluster_id, cfg in clusters.items():
            cfg['theme_display_name'] = theme_display_name
            cfg['sector_name'] = sector_name
            print(f"\n📂 主題: {theme_display_name} | 板塊: {sector_name} | 群組: {cfg.get('name')}")
            
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

                # --- 修改後的 EPS 抓取邏輯 ---
                eps_current = 0.0
                eps_forward = 0.0
                growth_estimate = None
            
                try:
                    est = getattr(ticker, 'earnings_estimate', None)
                    if est is not None and hasattr(est, 'empty') and not est.empty:
                        # 1. 優先抓取 +1y (明年) 的平均預估，這才是分析師目標價的基準
                        if '+1y' in est.index:
                            eps_forward = float(est.loc['+1y', 'avg'])
                            # 同時抓取明年相對於今年的成長率
                            if '0y' in est.index:
                                eps_current = float(est.loc['0y', 'avg']) # 把今年當作基準
                            else:
                                eps_current = float(est.loc['+1y', 'yearAgoEps'])
                            growth_estimate = float(est.loc['+1y', 'growth'])
                    
                        # 2. 如果沒有 +1y，退而求其次用 0y (今年)
                        elif '0y' in est.index:
                            eps_current = float(est.loc['0y', 'yearAgoEps'])
                            eps_forward = float(est.loc['0y', 'avg'])
                            if 'growth' in est.columns:
                                growth_estimate = float(est.loc['0y', 'growth'])
                            
                        else:
                            try:
                                eps_current = float(est.iloc[0]['yearAgoEps'])
                                eps_forward = float(est.iloc[0]['avg'])
                                if 'growth' in est.columns:
                                    growth_estimate = float(est.iloc[0]['growth'])
                            except Exception:
                                eps_current = eps_forward = 0.0
                    else:
                        # Fallback to info
                        val_trailing = info.get('trailingEps')
                        val_forward = info.get('forwardEps') # yfinance 的 forwardEps 通常指未來 12 個月
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

                # === 修正：確保 eps_current 和 eps_forward 至少有一個是正數 ===
                # 如果 eps_current 為 0 但 eps_forward > 0，或反之，進行補救性查詢
                if eps_current <= 0 or eps_forward <= 0:
                    try:
                        # 最後的降級方案：嘗試從 info 中的其他欄位獲取
                        if eps_current <= 0:
                            eps_current = float(info.get('trailingEps') or info.get('epsTrailingTwelveMonths') or 0)
                        if eps_forward <= 0:
                            eps_forward = float(info.get('forwardEps') or info.get('epsCurrentYear') or info.get('epsForward') or 0)
                    except Exception:
                        pass

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
            
                # --- 貨幣轉換修正 (如 TSM 台幣營收轉美金) ---
                if revenue_estimate:
                    fin_currency = info.get('financialCurrency')
                    currency = info.get('currency')
                    if fin_currency and currency and fin_currency != currency:
                        try:
                            # 使用 yfinance 抓取即時匯率 (例如 TWDUSD=X)
                            fx_symbol = f"{fin_currency}{currency}=X"
                            fx_ticker = yf.Ticker(fx_symbol)
                            fx_info = fx_ticker.info or {}
                            fx_rate = fx_info.get('regularMarketPrice') or fx_info.get('previousClose')
                        
                            if not fx_rate:
                                # Fallback using history if info is empty
                                fx_hist = fx_ticker.history(period="1d")
                                if not fx_hist.empty:
                                    fx_rate = float(fx_hist['Close'].iloc[-1])

                            if fx_rate and fx_rate > 0:
                                # 轉換營收：原始貨幣金額 * 匯率 (例如 TWD -> USD，匯率 0.0307)
                                revenue_estimate = revenue_estimate * fx_rate
                                print(f"  💱 [{symbol}] 執行 {fin_currency} 到 {currency} 轉換，即時匯率: {fx_rate:.4f}，校正後營收: {revenue_estimate/1e9:.2f}B")
                            elif fin_currency == 'TWD' and currency == 'USD':
                                # 最後防線 fallback
                                revenue_estimate = revenue_estimate / 32.5
                                print(f"  💱 [{symbol}] 執行 TWD 到 USD 轉換 (Fallback 32.5)，校正後營收: {revenue_estimate/1e9:.2f}B")
                        except Exception as e:
                            print(f"  ⚠ [{symbol}] 貨幣轉換嘗試失敗: {e}")
                            if fin_currency == 'TWD' and currency == 'USD':
                                revenue_estimate = revenue_estimate / 32.5
                                print(f"  💱 [{symbol}] 執行 TWD 到 USD 轉換 (Fallback 32.5)，校正後營收: {revenue_estimate/1e9:.2f}B")

                # --- 最終計算：這會自動套用到所有股票 ---
                future_rev_ps = None
                if revenue_estimate and shares_outstanding and shares_outstanding > 0:
                    future_rev_ps = round(float(revenue_estimate) / float(shares_outstanding), 4)
                elif info.get('revenuePerShare'):
                    future_rev_ps = clean_val(info.get('revenuePerShare'))

                # current price
                current_price = clean_val(market.get('price') or info.get('currentPrice') or info.get('regularMarketPrice'))
                # TTM revenue (for fallback usage)
                revenue_ttm = clean_val(market.get('revenue_ttm') or info.get('totalRevenue') or info.get('revenue'))

                # Normalize revenue_ttm currency to match revenue_estimate when possible
                try:
                    fin_currency = info.get('financialCurrency')
                    currency = info.get('currency')
                    if revenue_ttm and fin_currency and currency and fin_currency != currency:
                        fx_symbol = f"{fin_currency}{currency}=X"
                        fx_ticker = yf.Ticker(fx_symbol)
                        fx_info = fx_ticker.info or {}
                        fx_rate = fx_info.get('regularMarketPrice') or fx_info.get('previousClose')
                        if not fx_rate:
                            fx_hist = fx_ticker.history(period="1d")
                            if not fx_hist.empty:
                                fx_rate = float(fx_hist['Close'].iloc[-1])
                        if fx_rate and fx_rate > 0:
                            revenue_ttm = revenue_ttm * fx_rate
                            print(f"  💱 [{symbol}] TTM revenue converted {fin_currency}->{currency} rate {fx_rate:.4f}")
                except Exception:
                    pass

                # compute ps (TTM) and target_ps_market
                ps_val = None
                try:
                    # 優先使用 TTM 每股營收（由 revenue_ttm / shares_outstanding 計算），因為不同來源可能有幣別或單位差異
                    revps_ttm = None
                    if revenue_ttm and shares_outstanding and shares_outstanding > 0:
                        try:
                            revps_ttm = float(revenue_ttm) / float(shares_outstanding)
                        except Exception:
                            revps_ttm = None

                    if revps_ttm and current_price and revps_ttm > 0:
                        ps_val = round(float(current_price) / float(revps_ttm), 2)
                    else:
                        # 次選：若 info 裡有 revenuePerShare，也可用之
                        revps_info = clean_val(info.get('revenuePerShare'))
                        if revps_info and current_price and revps_info > 0:
                            ps_val = round(float(current_price) / float(revps_info), 2)
                        else:
                            # 再次選：使用 yfinance 提供的 priceToSalesTrailing12Months
                            ps_val = clean_val(info.get('priceToSalesTrailing12Months'))
                            if ps_val is None or ps_val <= 0:
                                # 最後 fallback: 手動計算 TTM P/S（market_cap / revenue_ttm）
                                mcap_val = market.get('market_cap_value')
                                revenue_ttm = clean_val(market.get('revenue_ttm') or info.get('totalRevenue') or info.get('revenue'))
                                if mcap_val and revenue_ttm and revenue_ttm > 0:
                                    ps_val = round(float(mcap_val) / float(revenue_ttm), 2)
                except Exception:
                    ps_val = None

                target_ps_market = None
                try:
                    mcap_val = market.get('market_cap_value')
                    if mcap_val and revenue_estimate and revenue_estimate > 0:
                        # 使用前瞻營收算出來的 forward PS 作為目標參考
                        target_ps_market = round(float(mcap_val) / float(revenue_estimate), 2)
                except Exception:
                    target_ps_market = None

                # ✅ Forward P/S：用 current_price / forward_revenue_per_share
                # 這樣不會逆推，而是基於對未來營收的獨立估計
                ps_forward = None
                try:
                    if current_price and future_rev_ps and future_rev_ps > 0:
                        # Forward P/S = 當前股價 / 預估的每股營收
                        ps_forward = round(float(current_price) / float(future_rev_ps), 2)
                except Exception:
                    ps_forward = None

                pb_val = None
                try:
                    book_val = info.get('bookValue')
                    if book_val and current_price:
                        pb_val = round(current_price / float(book_val), 2)
                except Exception:
                    pb_val = None

                # compute book value per share (BVPS) with fallbacks
                book_value_per_share = None
                try:
                    if book_val:
                        book_value_per_share = clean_val(book_val)
                    else:
                        # try total shareholder equity divided by shares_outstanding
                        total_equity = info.get('totalStockholderEquity') or info.get('totalStockholdersEquity') or info.get('totalEquity') or info.get('totalShareholderEquity')
                        if total_equity and shares_outstanding and shares_outstanding > 0:
                            book_value_per_share = clean_val(float(total_equity) / float(shares_outstanding))
                except Exception:
                    book_value_per_share = None

                analyst_target = clean_val(info.get('targetMedianPrice') or info.get('targetMeanPrice'))

                target_pb = None
                try:
                    at = master_data[symbol].get('analyst_target') or analyst_target
                    if at and book_value_per_share and book_value_per_share > 0:
                        target_pb = round(float(at) / float(book_value_per_share), 2)
                except Exception:
                    target_pb = None

                # sector/cluster median P/B - compute over this cluster's symbols if not too large
                sector_median_pb = None
                try:
                    peers = cfg.get('symbols', [])
                    pb_list = []
                    if peers and len(peers) <= 30:
                        for peer in peers:
                            if peer == symbol:
                                continue
                            try:
                                peer_t = yf.Ticker(peer)
                                pinfo = peer_t.info or {}
                                p_price = clean_val(pinfo.get('currentPrice') or pinfo.get('regularMarketPrice'))
                                p_book = pinfo.get('bookValue')
                                if not p_book:
                                    p_total_eq = pinfo.get('totalStockholderEquity') or pinfo.get('totalEquity')
                                    shares_out = clean_val(pinfo.get('sharesOutstanding'))
                                    if p_total_eq and shares_out:
                                        try:
                                            p_book = float(p_total_eq) / float(shares_out)
                                        except Exception:
                                            p_book = None
                                if p_book and p_price:
                                    try:
                                        p_pb = float(p_price) / float(p_book)
                                        if p_pb and p_pb > 0:
                                            pb_list.append(p_pb)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            time.sleep(0.05)
                        if pb_list:
                            sector_median_pb = round(float(np.median(pb_list)), 2)
                except Exception:
                    sector_median_pb = None

                # default params
                default_params = cfg.get('default_params', {})

                # Capture additional target metrics from info
                target_pe_market = clean_val(info.get('forwardPE'))
                # enterprise / ebitda / debt / cash fields
                enterprise_value = clean_val(info.get('enterpriseValue'))
                enterprise_to_ebitda = clean_val(info.get('enterpriseToEbitda') or info.get('enterpriseValueToEbitda'))
                ebitda = clean_val(info.get('ebitda') or info.get('ebitdaTTM') or info.get('ebitda_ttm'))
                total_debt = clean_val(info.get('totalDebt') or info.get('totalDebtRaw') or info.get('total_liabilities'))
                total_cash = clean_val(info.get('totalCash') or info.get('cash') or info.get('totalCashRaw'))
                net_debt = None
                try:
                    if total_debt is not None and total_cash is not None:
                        net_debt = round(float(total_debt) - float(total_cash), 2)
                except Exception:
                    net_debt = None
                # implied EV/price using available multipliers (prefer enterprise_to_ebitda)
                implied_ev = None
                implied_ev_multiplier = None
                try:
                    # prefer explicit enterprise_to_ebitda
                    if enterprise_to_ebitda:
                        implied_ev_multiplier = float(enterprise_to_ebitda)
                        if ebitda:
                            implied_ev = float(implied_ev_multiplier) * float(ebitda)
                    else:
                        # fallback: use cluster default if provided
                        if default_params and default_params.get('target_ev_ebitda'):
                            implied_ev_multiplier = float(default_params.get('target_ev_ebitda'))
                            if ebitda:
                                implied_ev = float(implied_ev_multiplier) * float(ebitda)
                except Exception:
                    implied_ev = None

                implied_price = None
                try:
                    if implied_ev is not None and net_debt is not None and shares_outstanding:
                        implied_price = float(implied_ev - net_debt) / float(shares_outstanding)
                except Exception:
                    implied_price = None
                master_data[symbol].update({
                    'theme': theme,
                    'theme_display_name': theme_display_name,
                    'sector_id': sector_id,
                    'sector_name': cfg.get('name'),
                        'calc_type': (cfg.get('logic_type', 'ps') if isinstance(cfg.get('logic_type', 'ps'), str) else 'ps'),
                    'insight_link': cfg.get('insight_link', master_data[symbol].get('insight_link')),
                    'tag': cfg.get('tag', master_data[symbol].get('tag', 'grey')),
                    'market_consensus_eps_current': secure_round(eps_current, 4),
                    'market_consensus_eps_forward': secure_round(eps_forward, 4),
                    'growth_estimate': secure_round(growth_estimate, 4) if growth_estimate is not None else None,
                    'revenue_estimate': revenue_estimate,
                    'future_revenue_per_share': secure_round(future_rev_ps, 4),
                    'revenue_ttm': revenue_ttm,
                    'target_pe_market': secure_round(target_pe_market, 4),
                    'ps_forward': ps_forward,
                    'analyst_target': secure_round(analyst_target, 2),
                    'shares_outstanding': shares_outstanding,
                    'current_price': current_price,
                    'ps': ps_val,
                    'pb': pb_val,
                    'enterprise_value': enterprise_value,
                    'enterprise_to_ebitda': enterprise_to_ebitda,
                    'ebitda': ebitda,
                    'total_debt': total_debt,
                    'total_cash': total_cash,
                    'net_debt': net_debt,
                    'implied_ev': implied_ev,
                    'implied_ev_multiplier': implied_ev_multiplier,
                    'implied_price': implied_price,
                    # record the growth estimate used for forward adjustments (analyst fallback)
                    'implied_growth_used': growth_estimate,
                    'book_value_per_share': secure_round(book_value_per_share, 4) if book_value_per_share is not None else None,
                    'target_pb': secure_round(target_pb, 2) if target_pb is not None else None,
                    'sector_median_pb': secure_round(sector_median_pb, 2) if sector_median_pb is not None else None,
                    'default_params': default_params,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                # --- earnings: cache-aware per-symbol fetch (single attempt) ---
                try:
                    from earning_report import fetch_earnings_for_symbol, read_cache

                    cache = read_cache()
                    entry = cache.get(symbol)
                    need_fetch = False

                    today = datetime.utcnow().date()

                    # decide whether we need to fetch:
                    # - missing cache entry
                    # - cached data missing
                    # - cached next_earnings_date <= today (event passed or is today) -> fetch next
                    if not entry or not entry.get('data'):
                        need_fetch = True
                    else:
                        data = entry.get('data') or {}
                        nd = data.get('next_earnings_date')
                        if not nd:
                            need_fetch = True
                        else:
                            try:
                                nd_dt = datetime.strptime(nd[:10], '%Y-%m-%d').date()
                                if nd_dt <= today:
                                    need_fetch = True
                            except Exception:
                                # if parse fails, attempt fetch once
                                need_fetch = True

                    if need_fetch:
                        # single attempt fetch; fetch_earnings_for_symbol already falls back to cache on failure
                        res = fetch_earnings_for_symbol(symbol, force=False)
                        if res and isinstance(res, dict) and res.get('next_earnings_date'):
                            master_data[symbol]['next_earnings_date'] = res.get('next_earnings_date')
                            master_data[symbol]['earnings_countdown'] = res.get('earnings_countdown')
                        else:
                            # fetch failed -> keep old cached data if available
                            if entry and entry.get('data'):
                                old = entry.get('data')
                                if old.get('next_earnings_date'):
                                    master_data[symbol]['next_earnings_date'] = old.get('next_earnings_date')
                                    master_data[symbol]['earnings_countdown'] = old.get('earnings_countdown')
                            # else nothing to do
                    else:
                        # cache is fresh and date is in future -> use cached value
                        if entry and entry.get('data') and entry['data'].get('next_earnings_date'):
                            cd = entry['data']
                            master_data[symbol]['next_earnings_date'] = cd.get('next_earnings_date')
                            master_data[symbol]['earnings_countdown'] = cd.get('earnings_countdown')

                except Exception as e:
                    # fail silently; earnings update is best-effort
                    # do not retry here
                    pass

# write out
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(master_data, f, ensure_ascii=False, indent=4)

print(f"\n✅ 所有主題與板塊更新完成！輸出檔案：{output_path}")

# --- Integrate earnings update: only run if explicitly enabled via env var
EARNINGS_ENABLED = os.getenv('EARNINGS_ENABLED', '1')
if EARNINGS_ENABLED == '1':
    try:
        import earning_report

        # avoid duplicate fetch: if earnings_dates.json was just generated (within 1 hour), skip
        earnings_cache = os.path.join(base_dir, 'earnings_dates.json')
        do_fetch = True
        if os.path.exists(earnings_cache):
            try:
                mtime = os.path.getmtime(earnings_cache)
                age = time.time() - mtime
                if age < 3600:  # less than 1 hour old
                    print(f"ℹ earnings_dates.json is recent ({int(age)}s); skipping re-fetch.")
                    do_fetch = False
            except Exception:
                do_fetch = True

        if do_fetch:
            print('\n🔁 開始更新 earnings dates (透過 earning_report.py) ...')
            try:
                earning_report.main()
                print('🔁 earnings dates 更新完成並已合併至 research_report.json（如有）。')
            except Exception as e:
                print('⚠ earning_report.main() 執行失敗：', e)
        else:
            print('ℹ 跳過 earnings 更新。')
    except Exception as e:
        print('⚠ 無法載入 earning_report 模組：', e)
else:
    print('ℹ earnings integration disabled (set EARNINGS_ENABLED=1 to enable)')