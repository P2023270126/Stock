import html
import json
import os
import re
from datetime import datetime, timezone

import requests
import yfinance as yf


WHATSAPP_PHONE = os.getenv("WA_PHONE")
WHATSAPP_API_KEY = os.getenv("WA_API_KEY")
SOS_URL = "https://www.richmondfed.org/research/national_economy/sos_recession_indicator"
ALERT_STATE_FILE = "alert_state.json"


def send_whatsapp(message):
    if not WHATSAPP_PHONE or not WHATSAPP_API_KEY:
        print("WhatsApp secrets are not configured; alert skipped.")
        return False
    try:
        response = requests.get(
            "https://api.callmebot.com/whatsapp.php",
            params={"phone": WHATSAPP_PHONE, "text": message, "apikey": WHATSAPP_API_KEY},
            timeout=20,
        )
        response.raise_for_status()
        print("WhatsApp alert sent successfully.")
        return True
    except requests.RequestException as error:
        # A notification problem must never prevent the dashboard from updating.
        print(f"WhatsApp alert warning: {error}")
        return False


def load_alert_state():
    defaults = {"extreme_oversold": False, "bull_trap": False, "sos_recession": False}
    try:
        with open(ALERT_STATE_FILE, encoding="utf-8") as state_file:
            stored = json.load(state_file)
        return {key: bool(stored.get(key, False)) for key in defaults}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return defaults


def save_alert_state(state):
    with open(ALERT_STATE_FILE, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=2, sort_keys=True)
        state_file.write("\n")


def process_alerts(data):
    """Send once on entry into a signal; re-arm after that signal clears."""
    previous = load_alert_state()
    bull_trap = data["recovery_label"] == "假反彈警號"
    active = {
        "extreme_oversold": data["vix"] >= 30 and data["drawdown"] <= -10,
        "bull_trap": bull_trap,
        "sos_recession": data["sos"] is not None and data["sos"] > 0.2,
    }
    messages = {
        "extreme_oversold": (
            f'🚀【P股票】極度超賣觀察訊號\nVIX: {data["vix"]:.2f}\n'
            f'52週回調: {data["drawdown"]:.2f}%\n請再查看 Stockbee T2108 是否低於 10%。'
        ),
        "bull_trap": (
            f'⚠️【P股票】200MA 假反彈警告\n{data["recovery_note"]}\n'
            f'SPX: {data["price"]:.2f}\n200MA: {data["ma200"]:.2f}'
        ),
        "sos_recession": (
            f'🔴【P股票】SOS 衰退警告\nRichmond Fed SOS: {data["sos"]:.3f}\n'
            '指標已升穿 0.2 警戒線。'
        ) if data["sos"] is not None else "",
    }

    next_state = {}
    for signal, is_active in active.items():
        if not is_active:
            next_state[signal] = False
        elif previous.get(signal, False):
            next_state[signal] = True
            print(f"{signal}: still active; duplicate alert suppressed.")
        else:
            # Keep it unarmed after failure so the next scheduled run retries.
            next_state[signal] = send_whatsapp(messages[signal])
    save_alert_state(next_state)


def market_history(symbol, period):
    data = yf.Ticker(symbol).history(period=period, auto_adjust=False)
    if data.empty or "Close" not in data:
        raise RuntimeError(f"No market data returned for {symbol}")
    return data["Close"].dropna()


def fetch_sos():
    """Read the latest official Richmond Fed SOS value; return None if unavailable."""
    try:
        response = requests.get(
            SOS_URL,
            timeout=20,
            headers={"User-Agent": "P-Stock-Dashboard/1.0"},
        )
        response.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", response.text)
        text = html.unescape(re.sub(r"\s+", " ", text))
        patterns = (
            r"SOS indicator (?:was|is|rose to|fell to|increased to|decreased to)\s+(-?\d+(?:\.\d+)?)",
            r"Latest Reading.{0,500}?\b(-?0\.\d+)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
    except (requests.RequestException, ValueError) as error:
        print(f"SOS fetch warning: {error}")
    return None


def consecutive_days(condition):
    count = 0
    for value in reversed(condition.tolist()):
        if not value:
            break
        count += 1
    return count


def analyse_market():
    spx = market_history("^GSPC", "2y")
    vix_series = market_history("^VIX", "1mo")
    ma200_series = spx.rolling(200).mean()
    valid = ma200_series.notna()
    spx, ma200_series = spx[valid], ma200_series[valid]

    price = float(spx.iloc[-1])
    ma200 = float(ma200_series.iloc[-1])
    distance = (price / ma200 - 1) * 100
    above = spx >= ma200_series
    current_above = bool(above.iloc[-1])
    position_days = consecutive_days(above if current_above else ~above)
    crossings_up = above & ~above.shift(1, fill_value=False)
    recent_up = crossings_up.iloc[-15:].any()

    if current_above and position_days <= 15:
        recovery_key, recovery_label = "watch", "收復觀察期"
        recovery_note = f"重上 200 天線 {position_days} 個交易日，仍在 5–15 日確認期"
    elif current_above:
        recovery_key, recovery_label = "good", "已企穩"
        recovery_note = f"連續 {position_days} 個交易日守在 200 天線之上"
    elif recent_up:
        recovery_key, recovery_label = "risk", "假反彈警號"
        recovery_note = "收復後 15 個交易日內再次失守 200 天線"
    else:
        recovery_key, recovery_label = "risk", "仍在 200 天線下"
        recovery_note = f"連續 {position_days} 個交易日低於 200 天線"

    high_52w = float(spx.iloc[-252:].max())
    drawdown = (price / high_52w - 1) * 100
    vix = float(vix_series.iloc[-1])
    if vix >= 30:
        vix_key, vix_label = "risk", "極度恐慌"
    elif vix >= 20:
        vix_key, vix_label = "watch", "尷尬區"
    else:
        vix_key, vix_label = "good", "情緒平穩"

    sos = fetch_sos()
    sos_key = "muted" if sos is None else ("risk" if sos > 0.2 else "good")
    sos_label = "暫未取得" if sos is None else ("衰退警號" if sos > 0.2 else "未觸發")

    return {
        "price": price, "ma200": ma200, "distance": distance,
        "position_days": position_days, "above": current_above,
        "recovery_key": recovery_key, "recovery_label": recovery_label,
        "recovery_note": recovery_note, "high_52w": high_52w,
        "drawdown": drawdown, "vix": vix, "vix_key": vix_key,
        "vix_label": vix_label, "sos": sos, "sos_key": sos_key,
        "sos_label": sos_label,
    }


def metric_card(title, value, detail, key="muted", badge=""):
    badge_html = f'<span class="badge {key}">{badge}</span>' if badge else ""
    return f'''<article class="metric-card">
      <div class="metric-head"><span>{title}</span>{badge_html}</div>
      <div class="metric-value">{value}</div><p>{detail}</p>
    </article>'''


def generate_html(data):
    trend_key = "good" if data["above"] else "risk"
    trend_label = "趨勢向上" if data["above"] else "趨勢受壓"
    position = "之上" if data["above"] else "之下"
    drawdown_key = "risk" if data["drawdown"] <= -10 else ("watch" if data["drawdown"] <= -5 else "good")
    drawdown_label = "超過 10%" if data["drawdown"] <= -10 else ("5–10%" if data["drawdown"] <= -5 else "少於 5%")
    signals = int(data["vix"] >= 30) + int(data["drawdown"] <= -10)
    sos_value = "—" if data["sos"] is None else f'{data["sos"]:.3f}'
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    cards = "".join([
        metric_card("S&P 500", f'{data["price"]:,.2f}', "最新收市價", trend_key, trend_label),
        metric_card("200 天移動平均線", f'{data["ma200"]:,.2f}', "長期市場趨勢基準", trend_key, "200MA"),
        metric_card("距離 200 天線", f'{data["distance"]:+.2f}%', f'現價位於平均線{position}', trend_key, position),
        metric_card("趨勢持續日數", f'{data["position_days"]} 日', f'連續交易日位於 200MA {position}', trend_key, "連續日數"),
        metric_card("收復／假反彈監察", data["recovery_label"], data["recovery_note"], data["recovery_key"], "5–15 日"),
        metric_card("52 週高位回調", f'{data["drawdown"]:.2f}%', f'52 週最高收市價 {data["high_52w"]:,.2f}', drawdown_key, drawdown_label),
        metric_card("VIX 恐慌指數", f'{data["vix"]:.2f}', "20–30 為觀察區；30 以上為極度恐慌", data["vix_key"], data["vix_label"]),
        metric_card("Richmond Fed SOS", sos_value, "0.2 以上觸發衰退警號；每週更新", data["sos_key"], data["sos_label"]),
    ])

    html_doc = f'''<!doctype html>
<html lang="zh-HK"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="美股趨勢、恐慌、回調及衰退風險監察儀表板">
<title>P股票 · 市場雷達</title>
<style>
:root{{--bg:#07111f;--panel:#0d1b2d;--line:#1f334b;--text:#f6f8fb;--muted:#91a2b8;--cyan:#63d8e8;--good:#61d39b;--watch:#f5bd57;--risk:#ff7383}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 80% 0,#153654 0,transparent 35%),var(--bg);color:var(--text);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.shell{{width:min(1180px,calc(100% - 32px));margin:auto;padding:34px 0 48px}} header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:24px}}
.eyebrow{{color:var(--cyan);font-size:12px;font-weight:800;letter-spacing:.16em;text-transform:uppercase}}h1{{font-size:clamp(30px,5vw,52px);line-height:1;margin:9px 0 10px;letter-spacing:-.04em}}.intro{{color:var(--muted);margin:0;max-width:650px;line-height:1.6}}
.header-actions{{display:flex;flex-direction:column;align-items:flex-end;gap:12px}}.updated{{color:var(--muted);font-size:12px;white-space:nowrap}}.source-button{{display:inline-flex;align-items:center;gap:8px;padding:10px 15px;border:1px solid rgba(99,216,232,.35);border-radius:12px;background:rgba(99,216,232,.1);color:var(--cyan);font-size:12px;font-weight:800;text-decoration:none;transition:.2s ease}}.source-button:hover{{background:rgba(99,216,232,.18);border-color:var(--cyan);transform:translateY(-1px)}}.source-button:focus-visible{{outline:2px solid var(--cyan);outline-offset:3px}}.hero{{display:grid;grid-template-columns:1.5fr 1fr;gap:16px;margin-bottom:16px}}.panel,.metric-card{{background:linear-gradient(145deg,rgba(18,39,62,.92),rgba(10,24,40,.92));border:1px solid var(--line);box-shadow:0 18px 50px rgba(0,0,0,.18)}}.panel{{border-radius:22px;padding:26px}}
.signal-row{{display:flex;justify-content:space-between;gap:20px;align-items:center}}.signal-label{{color:var(--muted);font-size:13px}}.signal-title{{font-size:clamp(24px,4vw,38px);font-weight:800;margin-top:7px}}.score{{font-size:42px;font-weight:850;color:var(--watch)}}.score small{{font-size:16px;color:var(--muted)}}.bar{{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:22px}}.bar span{{height:6px;border-radius:6px;background:#26394e}}.bar .on{{background:var(--watch)}}
.method{{display:grid;gap:12px}}.method div{{display:flex;justify-content:space-between;padding-bottom:11px;border-bottom:1px solid var(--line)}}.method div:last-child{{border:0;padding:0}}.method span{{color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}.metric-card{{border-radius:18px;padding:20px;min-height:176px;display:flex;flex-direction:column}}.metric-head{{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:13px}}.metric-value{{font-size:clamp(25px,3vw,34px);font-weight:820;letter-spacing:-.03em;margin:26px 0 8px}}.metric-card p{{color:var(--muted);font-size:12px;line-height:1.55;margin:auto 0 0}}
.badge{{border-radius:20px;padding:4px 8px;font-size:10px;font-weight:800;white-space:nowrap}}.badge.good{{color:var(--good);background:rgba(97,211,155,.12)}}.badge.watch{{color:var(--watch);background:rgba(245,189,87,.12)}}.badge.risk{{color:var(--risk);background:rgba(255,115,131,.12)}}.badge.muted{{color:var(--muted);background:rgba(145,162,184,.12)}}
footer{{display:flex;justify-content:space-between;gap:20px;margin-top:24px;color:var(--muted);font-size:11px;line-height:1.6}}footer a{{color:var(--cyan)}}
@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,1fr)}}.hero{{grid-template-columns:1fr}}}}@media(max-width:560px){{.shell{{width:min(100% - 20px,1180px);padding-top:22px}}header,footer{{display:block}}.header-actions{{align-items:flex-start;margin-top:14px}}.grid{{grid-template-columns:1fr}}.metric-card{{min-height:156px}}}}
</style></head><body><main class="shell">
<header><div><div class="eyebrow">P Stock · Market Radar</div><h1>市場溫度，一眼掌握。</h1><p class="intro">以趨勢、恐慌、回調與衰退風險四個角度，協助你保持耐性，等待條件真正成熟。</p></div><div class="header-actions"><div class="updated">更新：{updated}</div><a class="source-button" href="https://stockbee.blogspot.com/p/mm.html" target="_blank" rel="noopener noreferrer">Stockbee T2108 <span aria-hidden="true">↗</span></a></div></header>
<section class="hero"><article class="panel"><div class="signal-row"><div><div class="signal-label">極度超賣條件（暫不包括 T2108）</div><div class="signal-title">已觸發 {signals} 個可用條件</div></div><div class="score">{signals}<small>/2</small></div></div><div class="bar"><span class="{'on' if signals > 0 else ''}"></span><span class="{'on' if signals > 1 else ''}"></span><span></span></div></article>
<aside class="panel method"><div><span>市場趨勢</span><strong>{trend_label}</strong></div><div><span>VIX 狀態</span><strong>{data['vix_label']}</strong></div><div><span>衰退監察</span><strong>{data['sos_label']}</strong></div></aside></section>
<section class="grid" aria-label="八項市場指標">{cards}</section>
<footer><span>資料：Yahoo Finance 及 Richmond Fed。數據可能延遲或修訂。</span><span>只供資訊及教育用途，並非投資建議。<a href="{SOS_URL}">SOS 官方來源</a></span></footer>
</main></body></html>'''
    with open("index.html", "w", encoding="utf-8") as output:
        output.write(html_doc)


def check_market():
    data = analyse_market()
    generate_html(data)
    print(f'SPX {data["price"]:.2f} | 200MA {data["ma200"]:.2f} | VIX {data["vix"]:.2f}')
    process_alerts(data)


if __name__ == "__main__":
    check_market()
