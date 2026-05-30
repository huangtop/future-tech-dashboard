import json
import math

def clamp(x, lo, hi):
    return min(hi, max(lo, x))

def get_growth_linkage(growth_estimate, user_growth_pct):
    analyst_pct = (growth_estimate or 0) * 100
    user_pct = user_growth_pct
    base_denom = max(0.05, 1 + analyst_pct / 100)
    user_numer = max(0.05, 1 + user_pct / 100)
    growth_ratio = user_numer / base_denom
    return {
        "epsFactor": clamp(growth_ratio, 0.10, 3.00),
        "rpsFactor": clamp(growth_ratio, 0.10, 3.00),
        "bvpsFactor": clamp(1 + ((user_pct - analyst_pct) / 100) * 0.35, 0.30, 2.00),
        "ebitdaFactor": clamp(growth_ratio**0.50, 0.35, 2.20),
        "peMultipleFactor": clamp(growth_ratio**0.60, 0.45, 2.20),
        "psMultipleFactor": clamp(growth_ratio**0.45, 0.50, 2.00),
        "pbMultipleFactor": clamp(growth_ratio**0.25, 0.70, 1.50)
    }

def calculate_fair(symbol, r):
    price = r.get("current_price", 0) or 0
    fEPS = r.get("market_consensus_eps_forward") or r.get("eps_forward") or 0
    growth_est = r.get("growth_estimate")
    if growth_est is None:
        growth_est = 0
    user_growth_pct = growth_est * 100
    calc_type = r.get("calc_type", "peg")
    gl = get_growth_linkage(growth_est, user_growth_pct)
    
    fair = 0
    if calc_type == "peg":
        if user_growth_pct <= 0 or fEPS <= 0:
            fair = fEPS * 15 if fEPS > 0 else 0
        else:
            fair = fEPS * 0.9 * user_growth_pct
    elif calc_type == "pe":
        target_pe = r.get("target_pe_market") or user_growth_pct
        eps_adj = fEPS * gl["epsFactor"]
        fair = eps_adj * target_pe * gl["peMultipleFactor"]
    elif calc_type == "ps":
        rps = r.get("future_revenue_per_share") or 0
        target_ps = r.get("ps") or r.get("default_params", {}).get("target_ps", 8.0)
        rps_adj = rps * gl["rpsFactor"]
        fair = rps_adj * target_ps * gl["psMultipleFactor"]
    elif calc_type == "pb":
        bvps = r.get("book_value_per_share") or (price / r.get("pb", 1) if r.get("pb") else 0)
        target_pb = r.get("target_pb") or r.get("sector_median_pb") or r.get("pb") or 5.5
        bvps_adj = bvps * gl["bvpsFactor"]
        fair = bvps_adj * target_pb * gl["pbMultipleFactor"]
    elif calc_type == "ev_ebitda":
        ebitda = r.get("ebitda_estimate") or r.get("ebitda") or r.get("operating_income")
        shares = r.get("shares_outstanding")
        net_debt = r.get("net_debt")
        if net_debt is None and r.get("total_debt") is not None and r.get("total_cash") is not None:
             net_debt = r["total_debt"] - r["total_cash"]
        target_v = r.get("target_ev_ebitda") or (45 if user_growth_pct > 50 else 35)
        if ebitda and shares and shares > 0:
            ebitda_adj = ebitda * gl["ebitdaFactor"]
            implied_ev = ebitda_adj * target_v
            net_debt = net_debt or 0
            fair = (implied_ev - net_debt) / shares
    elif calc_type == "milestone":
        prob = r.get("default_params", {}).get("success_prob", 0.2)
        sM = 6 + (user_growth_pct / 10)
        fM = 0.5
        fair = price * (sM * prob + fM * (1 - prob))
    return fair

def run():
    with open('/Users/toppyhuang/Desktop/Python Code/Streamlit Project/Stock_Grabber/research_report.json') as f:
        data = json.load(f)

    final_data = []
    for s, r in data.items():
        price = r.get("current_price", 0) or 0
        analyst = r.get("analyst_target", 0) or 0
        growth_raw = r.get("growth_estimate")
        growth = (growth_raw * 100) if growth_raw is not None else 0
        fair = calculate_fair(s, r)
        
        # Margin calculations
        price_analyst_diff = ((price - analyst) / analyst * 100) if analyst and analyst > 0 else 0
        fair_analyst_diff = ((fair - analyst) / analyst * 100) if analyst and analyst > 0 else 0
        
        final_data.append({
            "id": s,
            "symbol": s,
            "current_price": round(float(price), 2),
            "analyst_target": round(float(analyst), 2),
            "growth_estimate": round(float(growth), 2),
            "system_fair": round(float(fair), 2),
            "price_analyst_diff": round(float(price_analyst_diff), 2),
            "fair_analyst_diff": round(float(fair_analyst_diff), 2),
            "calc_type": r.get("calc_type", "peg")
        })

    with open('/Users/toppyhuang/Desktop/Python Code/Streamlit Project/Stock_Grabber/valuation_combined_data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
    print("Generated valuation_combined_data.json successfully.")

if __name__ == "__main__":
    run()
