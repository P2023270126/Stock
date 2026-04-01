import yfinance as yf
import requests
import os

# 從 GitHub Secrets 讀取加密資料
WHATSAPP_PHONE = os.getenv('WA_PHONE')
WHATSAPP_API_KEY = os.getenv('WA_API_KEY')

def send_whatsapp(message):
    # 使用你確認的新號碼對應的 API 接口
    url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={message}&apikey={WHATSAPP_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        print("WhatsApp 訊息傳送成功！")
    else:
        print(f"傳送失敗，錯誤碼：{response.status_code}")

def check_market():
    # 獲取標普 500 數據
    ticker = yf.Ticker("^GSPC")
    hist = ticker.history(period="250d")
    
    current_price = hist['Close'].iloc[-1]
    ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
    vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    
    # 買入訊號邏輯 (茄利略策略)
    is_below_200ma = current_price < ma200
    is_panic_vix = vix >= 30
    
    print(f"SPX: {round(current_price)} | 200MA: {round(ma200)} | VIX: {round(vix, 2)}")
    
    # 如果觸發買入條件 (例如：破線且極度恐慌)
    if is_below_200ma and is_panic_vix:
        msg = f"🚀【P股票】金色買入訊號！%0A市場進入極度恐慌區%0ASPX 已跌破 200MA%0AVIX: {round(vix, 2)}"
        send_whatsapp(msg)
    else:
        print("未達買入門檻，保持耐心。")

if __name__ == "__main__":
    check_market()
