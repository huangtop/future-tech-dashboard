
import json

def get_growth_linkage(growth_estimate, user_growth_pct):
    analyst_pct = (growth_estimate or 0) * 100
    user_pct = user_growth_pct
    
    base_denom = max(0.05, 1 + analyst_pct / 100)
    user_numer = max(0.05, 1 + user_pct / 100)
    growth_ratio = user_numer / base_denom
    
    def clamp(x, lo, hi):
        return min(hi, max(lo, x))
        
    return {
        "epsFactor": clamp(growth_ratio, 0.10, 3.00),
        "rpsFactor": clamp(growth_ratio, 0.10, 3.00),
        "bvpsFactor": clamp(1 + ((user_pct - analyst_pct) / 100) * 0.35, 0.30, 2.00),
        "ebitdaFactor": clamp(growth_ratio**0.50, 0.35, 2.20),
        "peMultipleFactor": clamp(growth_ratio**0.60, 0.45, 2.20),
        "psMultipleFactor": clamp(growth_ratio**0.45, 0.50, 2.00),
        "pbMultipleFactor": clamp(growth_ratio**0.25, 0.70, 1.50)
    }

def do_calc_smoke_test(symbol, data):
    r = data.get(symbol)
    if not r: return f"Error: {symbol} not found"
    
    calc_type = r.get("calc_type", "peg")
    price = r.get("current_price", 0)
    eps_fwd = r.get("market_consensus_eps_forward") or r.get("eps_forward") or 0
    growth_est = r.get("growth_estimate", 0)
    user_growth_pct = growth_est * 100 # assume matching analyst for smoke test
    
    gl = get_growth_linkage(growth_est, user_growth_pct)
    
    fair = 0
    if calc_type == "peg":
        # PEG Logic: fEPS * 0.9 * gPct
        fair = eps_fwd * 0.9 * user_growth_pct
    elif calc_type == "pe":
        # PE Logic: fEPS_adj * target_pe * peMultFactor
        target_pe = r.get("target_pe_market") or user_growth_pct
        eps_adj = eps_fwd * gl["epsFactor"]
        fair = eps_adj * target_pe * gl["peMultipleFactor"]
    elif calc_type == "ps":
        # PS Logic: RPS_adj * target_ps * psMultFactor
        rps = r.get("future_revenue_per_share") or 0
        target_ps = r.get("ps") or r.get("default_params", {}).get("target_ps", 8.0)
        rps_adj = rps * gl["rpsFactor"]
        fair = rps_adj * target_ps * gl["psMultipleFactor"]
    elif calc_type == "pb":
        # PB Logic: BVPS_adj * target_pb * pbMultFactor
        bvps = r.get("book_value_per_share") or (price / r.get("pb", 1))
        target_pb = r.get("target_pb") or r.get("pb") or 5.5
        bvps_adj = bvps * gl["bvpsFactor"]
        fair = bvps_adj * target_pb * gl["pbMultipleFactor"]
    elif calc_type == "milestone":
        # Milestone: price * (sM * prob + fM * (1-prob))
        prob = r.get("default_params", {}).get("success_prob", 0.2)
        sM = 6 + (user_growth_pct / 10)
        fM = 0.5
        fair = price * (sM * prob + fM * (1 - prob))
        
    margin = ((fair - price) / price * 100) if price != 0 else 0
    return {
        "symbol": symbol,
        "calc_type": calc_type,
        "current_price": price,
        "mode_fair": round(fair, 2),
        "margin_pct": round(margin, 1)
    }

if __name__ == "__main__":
    with open("/Users/toppyhuang/Desktop/Python Code/Streamlit Project/Stock_Grabber/research_report.json") as f:
        data = json.load(f)
        
    stocks_to_test = ["WOLF", "AXTI", "QCOM", "MRVL", "INTC", "NNE", "LEU", "CIEN", "MU", "RKLB"]
    print(f"{'SYM':<6} | {'TYPE':<10} | {'PRICE':<8} | {'FAIR':<8} | {'MARGIN'}")
    print("-" * 50)
    for s in stocks_to_test:
        res = do_calc_smoke_test(s, data)
        print(f"{res['symbol']:<6} | {res['calc_type']:<10} | {res['current_price']:<8} | {res['mode_fair']:<8} | {res['margin_pct']}%")
