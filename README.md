<<<<<<< HEAD
# future-tech-dashboard
Daily Update Stock Data to json file
=======
# Stock Grabber - IEX Cloud 版本

## 簡介

本程式使用 **IEX Cloud API** 獲取股票數據，完全合法用於商業用途。

## 為什麼選擇 IEX Cloud？

✅ **商業合法** - 業界領先的金融數據供應商，完全合規  
✅ **完整數據** - 包含價格、市值、PE、EPS 等所有必要指標  
✅ **免費方案充足** - 每月 100,000 個請求（足以支持中小型應用）  
✅ **可靠穩定** - 機構級別的服務品質  
✅ **無法律風險** - 明確的商業授權，適合商用

## 快速開始

### 1. 註冊 IEX Cloud 帳戶

訪問 [https://iexcloud.io/](https://iexcloud.io/) 並註冊免費帳戶

### 2. 獲取 API Token

- 登錄 IEX Cloud 控制台
- 進入 **Account** → **API Tokens**
- 複製你的 **Publishable Token**（以 `pk_` 開頭）

### 3. 更新 API Key

編輯 `stock_grabber.py`，找到這一行：

```python
IEX_CLOUD_API_KEY = 'pk_test_YOUR_API_KEY_HERE'
```

替換為你的實際 Token：

```python
IEX_CLOUD_API_KEY = 'pk_YOUR_ACTUAL_TOKEN'
```

### 4. 安裝依賴

```bash
pip install requests numpy
```

### 5. 運行程式

```bash
python3 stock_grabber.py
```

## 輸出檔案

執行後會生成 `stock_data.json`，包含：

- 11 個不同領域的股票分類
- 每支股票的實時價格、漲跌%
- 市值、PE 比率、EPS 等關鍵指標
- 各扇區的平均統計數據

## 示例輸出

```json
{
  "updated": "2026-01-02 23:19:30",
  "sectors": {
    "AI/科技": {
      "stocks": [
        {
          "symbol": "NVDA",
          "price": 191.01,
          "change_percent": 2.42,
          "market_cap": "4.7T",
          "pe_ratio": 47.16,
          "eps": 4.05,
          ...
        }
      ],
      "avg_change": "+2.42%",
      "avg_pe": 45.67,
      "count": 16
    }
  }
}
```

## 價格

### 免費方案
- **100,000 請求/月** - 足以支持日常使用
- 適合測試和中小型應用

### 商業方案
- **無限請求** - 從 $99/月 起
- 適合大規模商業應用

更多信息：[IEX Cloud 價格](https://iexcloud.io/pricing/)

## 支援的股票

程式支持 120+ 支股票，分為 11 個分類：

- AI/科技（NVDA、MSFT、GOOGL 等）
- 新能源（ENPH、TSLA、FSLR 等）
- 量子電腦（IONQ、QBTS 等）
- 機器人（BOTZ、ISRG 等）
- 電動車/自動駕駛（TSLA、RIVN 等）
- 生物科技（ARKG、CRSP 等）
- 區塊鏈/Web3（COIN、MSTR 等）
- 太空科技（UFO、RKLB 等）
- 奈米科技（ARKQ、TSM 等）
- 金融科技（SOFI、PYPL 等）
- 腦機介面/元宇宙（META、AAPL 等）

## 常見問題

**Q: 免費方案夠用嗎？**  
A: 是的。100,000 請求/月 = 3,300 請求/天，足以每天執行程式多次。

**Q: 可以商業使用嗎？**  
A: 完全可以。IEX Cloud 明確授權商業使用，包括 SaaS 應用、投資服務等。

**Q: 如何擴展到付費方案？**  
A: 代碼無需改動，只需升級 IEX Cloud 帳戶即可。

## 許可證

本程式供商業使用，符合 IEX Cloud 服務條款。
>>>>>>> 87bd349 (chore: update yfinance script - normalize growth_estimate, fallback_growth, calc_type mapping; include ps/pb/default_params)
