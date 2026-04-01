import yfinance as yf
import requests
import os
from datetime import datetime

# 從 GitHub Secrets 讀取加密資料
WHATSAPP_PHONE = os.getenv('WA_PHONE')
WHATSAPP_API_KEY = os.getenv('WA_API_KEY')

def send_whatsapp(message):
    # 使用 quote 處理特殊字元、空格與 Emoji
    safe_msg = requests.utils.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={safe_msg}&apikey={WHATSAPP_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        print("WhatsApp 訊息傳送成功！")
    else:
        print(f"傳送失敗，錯誤碼：{response.status_code}")

def generate_html(spx, ma200, vix):
    # 計算偏離度
    diff = ((spx - ma200) / ma200) * 100
    # 顏色邏輯：SPX > 200MA 為綠色，否則為紅色；VIX >= 30 為紅色，否則為綠色
    status_color = "#2ecc71" if spx > ma200 else "#e74c3c"
    vix_color = "#e74c3c" if vix >= 30 else "#2ecc71"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>P股票 投資儀表板</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
            .card {{ background: white; padding: 30px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); width: 90%; max-width: 400px; text-align: center; }}
            h1 {{ color: #1c1e21; font-size: 22px; margin-bottom: 25px; }}
            .metric {{ margin: 15px 0; padding: 20px; border-radius: 15px; background: #f8f9fa; border: 1px solid #eee; }}
            .label {{ font-size: 14px; color: #606770; text-transform: uppercase; letter-spacing: 1px; }}
            .value {{ font-size: 32px; font-weight: 800; margin-top: 8px; }}
            .sub-value {{ font-size: 13px; margin-top: 5px; color: #90949c; }}
            .status-banner {{ padding: 12px; border-radius: 10px; color: white; font-weight: bold; margin-top: 25px; font-size: 16px; }}
            .footer {{ font-size: 11px; color: #bcc0c4; margin-top: 25px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>📊 P股票 監控儀表板</h1>
            
            <div class="metric">
                <div class="label">S&P 500 Index</div>
                <div class="value" style="color: {status_color};">{round(spx, 2)}</div>
                <div class="sub-value">200MA: {round(ma200, 2)} ({"+" if diff > 0 else ""}{round(diff, 2)}%)</div>
            </div>

            <div class="metric">
                <div class="label">VIX Index (Fear)</div>
                <div class="value" style="color: {vix_color};">{round(vix, 2)}</div>
            </div>

            <div class="status-banner" style="background: {status_color if vix < 30 else '#f1c40f'};">
                {"✅ 市場趨勢向上" if spx > ma200 and vix < 30 else "⚠️ 警告：進入買入觀察區" if spx < ma200 else "🕒 市場情緒波動"}
            </div>

            <div class="footer">Last Update: {now} (UTC)</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("成功生成 index.html")

def check_market():
    # 獲取標普 500 數據
    ticker = yf.Ticker("^GSPC")
    hist = ticker.history(period="250d")
    current_price = hist['Close'].iloc[-1]
    ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
    
    # 獲取 VIX 數據
    vix_ticker = yf.Ticker("^VIX")
    vix_hist = vix_ticker.history(period="1d")
    vix = vix_hist['Close'].iloc[-1]
    
    # 在日誌中打印當前數據
    print(f"當前數據 - SPX: {round(current_price)} | 200MA: {round(ma200)} | VIX: {round(vix, 2)}")
    
    # 生成 HTML 檔案
    generate_html(current_price, ma200, vix)
    
    # 買入訊號邏輯
    if current_price < ma200 and vix >= 30:
        msg = f"🚀【P股票】金色買入訊號！\n市場進入極度恐慌區\nSPX 已跌破 200MA\nVIX: {round(vix, 2)}"
        send_whatsapp(msg)
    else:
        print("未達買入訊號，僅更新儀表板。")

if __name__ == "__main__":
    check_market()
