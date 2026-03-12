# stock_grabber.py - 使用 IEX Cloud API 版本（商業合法）
#
# IEX Cloud 是業界領先的金融數據提供商，提供合法的商業級 API
# 免費方案包括：每月 100,000 個請求，足以支持中小型應用
# 官網：https://iexcloud.io/
#
import requests
import json
import os
import math
from datetime import datetime
import time

# IEX Cloud API 配置
# 免費帳戶註冊地址：https://iexcloud.io/console/register
IEX_CLOUD_API_KEY = 'pk_test_YOUR_API_KEY_HERE'  # 請更換為你的 IEX Cloud API Token
IEX_BASE_URL = 'https://cloud.iexapis.com/stable'

def update_research_report():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, 'structure.json')
    file_path = os.path.join(base_dir, 'research_report.json')

    # 讀取設定檔
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            themes_config = config_data.get('themes', {})
    except FileNotFoundError:
        print("❌ 找不到 structure.json，請確認檔案路徑。")
        return

    # 預設值輔助函式
    def get_default_fields(symbol, theme_id, cluster_id, cluster_config):
        return {
            "symbol": symbol,
            "theme_id": theme_id,
            "cluster_id": cluster_id,
            "sector_name": cluster_config.get('name', ''),
            "theme_display_name": cluster_config.get('display_name', theme_id),
            "calc_type": cluster_config.get('logic_type', 'ps'),
            "insight_link": cluster_config.get('insight_link', f"/insight/{symbol.lower()}"),
            "tag": cluster_config.get('tag', 'grey'),
            "default_params": cluster_config.get('default_params', {}),
            "market_consensus_eps_current": None,
            "market_consensus_eps_forward": None,
            "calc_growth": None,
            "growth_estimate": None,
            "revenue_estimate": None,
            "shares_outstanding": None,
            "current_price": None,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # 讀取現有的 research_report.json
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            master_data = json.load(f)
    except FileNotFoundError:
        master_data = {}

    # 輔助函式：確保數值符合 JSON 標準
    def clean_val(val):
        try:
            if isinstance(val, str) and val.replace('.', '', 1).isdigit():
                return float(val)
            elif isinstance(val, (int, float)):
                return float(val)
        except:
            return None
        return None

    def secure_round(val, precision):
        cleaned = clean_val(val)
        if cleaned is None:
            return None
        return round(cleaned, precision)

    def fetch_iex_data(symbol):
        # IEX Cloud 請求
        url = f"{IEX_BASE_URL}/stock/{symbol}/quote"
        params = {'token': IEX_CLOUD_API_KEY}
        response = requests.get(url, params=params)
        if response.status_code != 200:
            return None
        return response.json()

    # 遍歷主題和類群
    for theme_id, theme_info in themes_config.items():
        theme_display_name = theme_info.get('display_name', theme_id)
        clusters = theme_info.get('clusters', {})
        
        for cluster_id, cluster_config in clusters.items():
            cluster_config['theme_display_name'] = theme_display_name
            print(f"\n📂 主題: {theme_display_name} | 板塊：{cluster_config['name']}")
            
            for symbol in cluster_config.get('symbols', []):
                print(f"  > 抓取數據中: {symbol}")
                
                if symbol not in master_data:
                    master_data[symbol] = get_default_fields(symbol, theme_id, cluster_id, cluster_config)
                else:
                    defaults = get_default_fields(symbol, theme_id, cluster_id, cluster_config)
                    for key, val in defaults.items():
                        if key not in master_data[symbol]:
                            master_data[symbol][key] = val

                try:
                    data = fetch_iex_data(symbol)
                    if data:
                        price = data.get('latestPrice', 0.0)
                        
                        master_data[symbol].update({
                            "theme_id": theme_id,
                            "theme_display_name": theme_display_name,
                            "cluster_id": cluster_id,
                            "sector_name": cluster_config['name'],
                            "calc_type": cluster_config.get('logic_type', 'ps'),
                            "insight_link": cluster_config.get('insight_link', master_data[symbol].get('insight_link', f"/insight/{symbol.lower()}")),
                            "tag": cluster_config.get('tag', master_data[symbol].get('tag', 'grey')),
                            "current_price": clean_val(price),
                            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        
                        if 'default_params' in cluster_config:
                            master_data[symbol]['default_params'] = cluster_config['default_params']
                    
                    # IEX Cloud 控制速率
                    time.sleep(0.1)

                except Exception as e:
                    print(f"  ❌ {symbol} 失敗: {str(e)}")

    # 存檔
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(master_data, f, ensure_ascii=False, indent=4)
    
    print(f"\n✅ 所有主題與板塊更新完成！輸出檔案：{file_path}")

if __name__ == "__main__":
    update_research_report()