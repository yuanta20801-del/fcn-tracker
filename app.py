import json
import urllib.parse
import urllib.request
import feedparser
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="客戶部位每日動態追蹤系統", layout="wide")

# 產品關鍵參數 (SNGSELN01866)
PRODUCT_INFO = {
    "code": "SNGSELN01866",
    "name": "高盛 12M 美元固定配息 FCN (NVDA/TSM)",
    "trade_date": "2026-10-14",
    "issue_date": "2026-10-21",
    "autocall_start_date": "2026-11-23",  # 提前買回起始日
    "final_evaluation_date": "2027-10-21",  # 最後評價日
    "maturity_date": "2027-10-25",
    "coupon_rate_annual": 0.10008,
    "stocks": {
        "NVDA": {
            "ticker": "NVDA",
            "name": "輝達 (NVIDIA)",
            "initial": 221.3000,
            "autocall": 232.3650,  # KO (105.00%)
            "strike": 173.1230,  # 履約價 (78.23%)
            "ki": 143.8450,  # (A)KI (65.00%)
        },
        "TSM": {
            "ticker": "TSM",
            "name": "台積電 ADR (TSM)",
            "initial": 430.0000,
            "autocall": 451.5000,  # KO (105.00%)
            "strike": 336.3890,  # 履約價 (78.23%)
            "ki": 279.5000,  # (A)KI (65.00%)
        },
    },
}

def get_stock_data_direct(ticker_symbol, start_date="2026-10-14"):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}?range=1y&interval=1d"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        close_prices = result["indicators"]["quote"][0]["close"]
        df = pd.DataFrame({"Close": close_prices}, index=pd.to_datetime(timestamps, unit="s"))
        df = df.dropna()
        df.index = df.index.tz_localize(None)
        df_filtered = df[df.index >= pd.to_datetime(start_date)]
        if df_filtered.empty:
            df_filtered = df.tail(15)
        current_price = float(df_filtered["Close"].iloc[-1])
        return current_price, df_filtered
    except Exception:
        return 0.0, None

def get_stock_news(query):
    try:
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:5]:
            news_items.append({"title": entry.title, "link": entry.link, "published": entry.published})
        return news_items
    except Exception:
        return []

# 頁面主標題
st.title("📊 客戶境外結構型商品 (FCN) 每日即時監控儀表板")
st.caption(f"商品代碼：{PRODUCT_INFO['code']} | 交易日：{PRODUCT_INFO['trade_date']} | 最後評價日：{PRODUCT_INFO['final_evaluation_date']}")
st.markdown("---")

for symbol, info in PRODUCT_INFO["stocks"].items():
    current_price, df_hist = get_stock_data_direct(info["ticker"], PRODUCT_INFO["trade_date"])
    if current_price == 0 or df_hist is None:
        st.error(f"⚠️ 無法取得 {symbol} 行情，請檢查網路連線。")
        continue

    pct_from_initial = (current_price / info["initial"] - 1) * 100
    dist_to_autocall = (info["autocall"] - current_price) / current_price * 100
    dist_to_strike = (current_price - info["strike"]) / current_price * 100
    dist_to_ki = (current_price - info["ki"]) / current_price * 100

    if current_price < info["ki"]:
        status = "🔴 已跌破 KI 下限"
    elif current_price < info["strike"]:
        status = "🟡 低於履約價 (Strike)"
    elif current_price >= info["autocall"]:
        status = "🚀 符合 Autocall 條件"
    else:
        status = "🟢 正常運作中 (安全區間)"

    st.subheader(f"{info['name']} ({symbol})")
    st.write(f"**目前狀態**：{status}")

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("最新收盤價", f"${current_price:.2f}", f"{pct_from_initial:+.2f}%")
    col_m2.metric("距履約價 (78.23%)", f"${info['strike']:.2f}", f"{dist_to_strike:+.2f}%")
    col_m3.metric("距 KI 下限 (65%)", f"${info['ki']:.2f}", f"{dist_to_ki:+.2f}%")

    fig = go.Figure()

    # 1. 股價折線
    fig.add_trace(go.Scatter(x=df_hist.index, y=df_hist["Close"], mode="lines+markers", name=symbol, line=dict(color="#1f77b4", width=2.5), marker=dict(size=4)))

    # 2. 三大水平關卡線
    fig.add_hline(y=info["autocall"], line_color="#ff7f0e", line_width=1.8, annotation_text="KO (105%)", annotation_position="top left")
    fig.add_hline(y=info["strike"], line_color="#bcbd22", line_width=1.8, annotation_text="履約價 (78.23%)", annotation_position="bottom left")
    fig.add_hline(y=info["ki"], line_color="#7f7f7f", line_width=1.8, annotation_text="(A)KI (65%)", annotation_position="bottom left")

    # 3. 關鍵垂直標記線
    autocall_start_ts = pd.to_datetime(PRODUCT_INFO["autocall_start_date"]).timestamp() * 1000
    fig.add_vline(x=autocall_start_ts, line_color="#2ca02c", line_dash="dash", line_width=1.8, annotation_text="提前買回起始日 (11/23)", annotation_position="top left", annotation_font_size=11, annotation_font_color="#2ca02c")

    final_eval_ts = pd.to_datetime(PRODUCT_INFO["final_evaluation_date"]).timestamp() * 1000
    fig.add_vline(x=final_eval_ts, line_color="#d62728", line_dash="dash", line_width=2.0, annotation_text="最後評價日 (10/21)", annotation_position="top right", annotation_font_size=11, annotation_font_color="#d62728")

    # 4. 關鍵數據點標籤
    max_idx = df_hist["Close"].idxmax()
    max_val = df_hist["Close"].max()
    min_idx = df_hist["Close"].idxmin()
    min_val = df_hist["Close"].min()
    latest_idx = df_hist.index[-1]

    fig.add_trace(go.Scatter(x=[max_idx], y=[max_val], mode="markers+text", name="區間最高", marker=dict(size=7, color="green"), text=[f"High ${max_val:.2f}"], textposition="top center", textfont=dict(size=10, color="green")))
    fig.add_trace(go.Scatter(x=[min_idx], y=[min_val], mode="markers+text", name="區間最低", marker=dict(size=7, color="red"), text=[f"Low ${min_val:.2f}"], textposition="bottom center", textfont=dict(size=10, color="red")))
    fig.add_trace(go.Scatter(x=[latest_idx], y=[current_price], mode="markers+text", name="最新價", marker=dict(size=8, color="#1f77b4"), text=[f"最新 ${current_price:.2f}"], textposition="middle right", textfont=dict(size=11, color="#1f77b4")))

    latest_date_str = df_hist.index[-1].strftime("%m/%d")
    fig.update_layout(
        title=dict(text=f"<b>{symbol} {latest_date_str}</b>", x=0.5, xanchor="center", font=dict(size=22, color="#333333")),
        xaxis=dict(title="", tickformat="%m月%d日", tickangle=-45, range=["2026-10-10", "2027-10-28"], showgrid=True, gridcolor="#E5E5E5", showline=True, linecolor="#333333"),
        yaxis=dict(title="", showgrid=True, gridcolor="#E5E5E5", showline=True, linecolor="#333333"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=450,
        margin=dict(l=40, r=40, t=60, b=80),
        legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5, font=dict(size=12))
    )

    st.plotly_chart(fig, use_container_width=True)

    st.write("📰 **最新相關新聞**")
    news = get_stock_news(f"{info['name']} 股票新聞")
    if news:
        for item in news:
            st.markdown(f"- [{item['title']}]({item['link']}) _({item['published'][:16]})_")
    else:
        st.write("暫無最新新聞資料。")

    st.markdown("---")