import yfinance as yf
import requests
import os
from datetime import datetime

WHATSAPP_PHONE = os.getenv('WA_PHONE')
WHATSAPP_API_KEY = os.getenv('WA_API_KEY')

def send_whatsapp(message):
    safe_msg = requests.utils.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={safe_msg}&apikey={WHATSAPP_API_KEY}"
    requests.get(url)

def generate_html(spx, ma200, vix):
    # 計算偏離度
    diff = ((spx - ma200) / ma200) * 100
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
            body {{ font-family: sans-serif; background: #f4f7f6; display: flex; justify-content: center; padding: 20px; }}
            .card {{ background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }}
            h1 {{ color: #2c3e50; font-size: 24px; text-align: center; }}
            .metric {{ margin: 20px 0; padding: 15px; border-radius: 10px; background: #f9f9f9; }}
            .label {{ font-size: 14px; color: #7f8c8d; }}
            .value {{ font-size: 28px; font-weight: bold; margin-top: 5px; }}
            .status {{ text-align: center; padding: 10px; border-radius: 5px; color: white; font-weight: bold; margin-top: 20px; }}
            .time {{ font-size: 12px; color: #bdc3c7; text-align: center; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>📊 P股票 監控儀表板</h1>
            <div class="metric">
                <div class="label">S&P 500 指數</div>
                <div class="value" style="color: {status_color};">{round(spx, 2)}</div>
                <div class="label">200日平均線: {round(ma200, 2)} ({round(diff, 2)}%)</div>
            </div>
            <div class="metric">
                <div class="label">VIX 恐慌指數</div>
                <div class="value" style="color: {vix_color};">{round(vix, 2)}</div>
            </div>
            <div class="status" style="background: {status_color if vix < 30 else '#f1c40f'};">
                {"✅ 市場平穩" if spx > ma200 and vix < 30 else "⚠️ 警告：進入買入觀察區" if spx < ma200 else "🕒 等待訊號"}
            </div>
            <div class="time">最後更新：{now} (UTC)</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

def check_market():
    ticker = yf.Ticker("^GSPC")
    hist = ticker.history(period="250d")
    current_price = hist['Close'].iloc[-1]
    ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
    vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    
    # 生成網頁檔案
    generate_html(current_price, ma200, vix)
    
    if current_price < ma200 and vix >= 30:
        msg = f"🚀【P股票】金色買入訊號！\nSPX: {round(current_price)}\nVIX: {round(vix, 2)}"
        send_whatsapp(msg)

if __name__ == "__main__":
    check_market()
