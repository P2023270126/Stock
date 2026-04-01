import yfinance as yf
import requests
import os

# 從 GitHub Secrets 讀取加密資料
WHATSAPP_PHONE = os.getenv('WA_PHONE')
WHATSAPP_API_KEY = os.getenv('WA_API_KEY')

def send_whatsapp(message):
    # 使用 quote 處理特殊字元與 Emoji
    safe_msg = requests.utils.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={safe_msg}&apikey={WHATSAPP_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        print("WhatsApp 訊息傳送成功！")
    else:
        print(f"傳送失敗，錯誤碼：{response.status_code}，請檢查 Secret 設定。")

def check_market():
    # 獲取標普 500 數據
    ticker = yf.Ticker("^GSPC")
    hist = ticker.history(period="250d")
    
    current_price = hist['Close'].iloc[-1]
    ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
    
    # 獲取 VIX 數據
    vix_data = yf.Ticker("^VIX").history(period="1d")
    vix = vix_data['Close'].iloc[-1]
    
    print(f"SPX: {round(current_price)} | 200MA: {round(ma200)} | VIX: {round(vix, 2)}")
    
    # 買入訊號邏輯
    is_below_200ma = current_price < ma200
    is_panic_vix = vix >= 30
    
    if is_below_200ma and is_panic_vix:
        msg = f"🚀【P股票】金色買入訊號！\n市場進入極度恐慌區\nSPX 已跌破 200MA\nVIX: {round(vix, 2)}"
        send_whatsapp(msg)
    else:
        print("未達買入門檻，保持耐心。")

if __name__ == "__main__":
