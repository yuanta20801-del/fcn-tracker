import json
import urllib.parse
import urllib.request
import feedparser
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="客戶多部位 FCN 每日監控控制台", layout="wide"
)

# 預設內建部位資料 (備援機制)
DEFAULT_POSITIONS = [
    {
        "id": "POS001",
        "client_name": "陳大通",
        "code": "SNGSELN01866",
        "product_name": "高盛 12M 美元固定配息 FCN (NVDA/TSM)",
        "amount": 100000,
        "trade_date": "2026-10-14",
        "autocall_start_date": "2026-11-23",
        "final_evaluation_date": "2027-10-21",
        "coupon_rate_annual": 0.10008,
        "stocks": {
            "NVDA": {
                "ticker": "NVDA",
                "name": "輝達 (NVIDIA)",
                "initial": 221.3000,
                "autocall": 232.3650,
                "strike": 173.1230,
                "ki": 143.8450,
            },
            "TSM": {
                "ticker": "TSM",
                "name": "台積電 ADR (TSM)",
                "initial": 430.0000,
                "autocall": 451.5000,
                "strike": 336.3890,
                "ki": 279.5000,
            },
        },
    },
    {
        "id": "POS002",
        "client_name": "林美玲",
        "code": "SNGSELN01988",
        "product_name": "高盛 12M 美元固定配息 FCN (AMD/AMZN)",
        "amount": 50000,
        "trade_date": "2026-09-15",
        "autocall_start_date": "2026-10-25",
        "final_evaluation_date": "2027-09-15",
        "coupon_rate_annual": 0.1050,
        "stocks": {
            "AMD": {
                "ticker": "AMD",
                "name": "超微 (AMD)",
                "initial": 150.0000,
                "autocall": 157.5000,
                "strike": 117.3450,
                "ki": 97.5000,
            },
            "AMZN": {
                "ticker": "AMZN",
                "name": "亞馬遜 (Amazon)",
                "initial": 180.0000,
                "autocall": 189.0000,
                "strike": 140.8140,
                "ki": 117.0000,
            },
        },
    },
]


@st.cache_data(ttl=60)
def load_positions_from_gsheet(csv_url):
  """動態讀取 Google Sheets CSV 試算表"""
  try:
    df = pd.read_csv(csv_url)
    positions = []
    for idx, row in df.iterrows():
      pos = {
          "id": f"POS_{idx+1:03d}",
          "client_name": str(row.get("客戶名稱", "未知客戶")).strip(),
          "code": str(row.get("商品代號", "FCN")).strip(),
          "product_name": str(row.get("商品名稱", "FCN 結構型商品")).strip(),
          "amount": float(row.get("申購金額USD", 100000)),
          "coupon_rate_annual": float(row.get("年化配息率", 0.1)),
          "trade_date": str(row.get("交易日", "2026-10-14")).strip(),
          "autocall_start_date": str(
              row.get("提前買回起始日", "2026-11-23")
          ).strip(),
          "final_evaluation_date": str(
              row.get("最後評價日", "2027-10-21")
          ).strip(),
          "stocks": {},
      }
      # 處理標的 1
      if pd.notna(row.get("標的1代碼")):
        s1_ticker = str(row["標的1代碼"]).strip()
        pos["stocks"][s1_ticker] = {
            "ticker": s1_ticker,
            "name": str(row.get("標的1名稱", s1_ticker)).strip(),
            "initial": float(row.get("標的1期初價", 100)),
            "autocall": float(row.get("標的1KO價", 105)),
            "strike": float(row.get("標的1履約價", 78.23)),
            "ki": float(row.get("標的1KI價", 65)),
        }
      # 處理標的 2
      if pd.notna(row.get("標的2代碼")):
        s2_ticker = str(row["標的2代碼"]).strip()
        pos["stocks"][s2_ticker] = {
            "ticker": s2_ticker,
            "name": str(row.get("標的2名稱", s2_ticker)).strip(),
            "initial": float(row.get("標的2期初價", 100)),
            "autocall": float(row.get("標的2KO價", 105)),
            "strike": float(row.get("標的2履約價", 78.23)),
            "ki": float(row.get("標的2KI價", 65)),
        }
      positions.append(pos)
    return positions if positions else DEFAULT_POSITIONS
  except Exception:
    return DEFAULT_POSITIONS


@st.cache_data(ttl=1800)
def get_stock_data_cached(ticker_symbol, start_date="2026-09-01"):
  try:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}?range=1y&interval=1d"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
      data = json.loads(response.read().decode())
    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    close_prices = result["indicators"]["quote"][0]["close"]
    df = pd.DataFrame(
        {"Close": close_prices}, index=pd.to_datetime(timestamps, unit="s")
    )
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
      news_items.append({
          "title": entry.title,
          "link": entry.link,
          "published": entry.published,
      })
    return news_items
  except Exception:
    return []


# ================= 介面佈局與側邊欄設定 =================
st.title("💼 客戶 FCN 結構型商品部位多維度控制台")
st.caption("線上 Google Sheets 即時同步 | 全部位動態監控與警示系統")

st.sidebar.header("⚙️ 資料源與部位篩選")

# Google Sheet 預設發布 URL
default_sheet_url = "https://docs.google.com/spreadsheets/d/1cKGR9R1dUfFXOg5vF8igHNr3eYGbF12xrNGeIY-Qzpo/export?format=csv"
gsheet_url = st.sidebar.text_input(
    "Google Sheets CSV 串接網址：", value=default_sheet_url
)

# 載入資料
positions_data = load_positions_from_gsheet(gsheet_url)

# 客戶篩選
clients = ["全部客戶"] + sorted(
    list(set(p["client_name"] for p in positions_data))
)
selected_client = st.sidebar.selectbox("選擇客戶：", clients)

# 狀態過濾
status_filter = st.sidebar.selectbox(
    "部位狀態篩選：",
    ["全部狀態", "🟢 正常運作中", "🟡 低於履約價", "🔴 已跌破 KI"],
)

# 篩選邏輯
filtered_positions = positions_data
if selected_client != "全部客戶":
  filtered_positions = [
      p for p in filtered_positions if p["client_name"] == selected_client
  ]

evaluated_positions = []
total_aum = 0
total_monthly_coupon = 0
status_counts = {"🟢 正常運作中": 0, "🟡 低於履約價": 0, "🔴 已跌破 KI": 0}

for pos in filtered_positions:
  pos_total_amount = pos["amount"]
  monthly_coupon = (pos_total_amount * pos["coupon_rate_annual"]) / 12
  worst_dist_ki = 999.0
  pos_status = "🟢 正常運作中"

  for sym, info in pos["stocks"].items():
    cur_p, _ = get_stock_data_cached(info["ticker"], pos["trade_date"])
    if cur_p > 0:
      dist_ki = (cur_p - info["ki"]) / cur_p * 100
      if dist_ki < worst_dist_ki:
        worst_dist_ki = dist_ki

      if cur_p < info["ki"]:
        pos_status = "🔴 已跌破 KI"
      elif cur_p < info["strike"] and pos_status != "🔴 已跌破 KI":
        pos_status = "🟡 低於履約價"

  if status_filter != "全部狀態" and pos_status != status_filter:
    continue

  evaluated_positions.append({
      "raw": pos,
      "status": pos_status,
      "worst_dist_ki": worst_dist_ki,
      "monthly_coupon": monthly_coupon,
  })

  total_aum += pos_total_amount
  total_monthly_coupon += monthly_coupon
  status_counts[pos_status] = status_counts.get(pos_status, 0) + 1

# 頂層 KPI 卡片
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
kpi_col1.metric("當前受託總額", f"${total_aum:,.0f} USD")
kpi_col2.metric("預計每月派息總額", f"${total_monthly_coupon:,.2f} USD")
kpi_col3.metric("🟢 正常部位數", f"{status_counts.get('🟢 正常運作中', 0)} 檔")
kpi_col4.metric(
    "⚠️ 警戒部位數 (🟡/🔴)",
    f"{status_counts.get('🟡 低於履約價', 0) + status_counts.get('🔴 已跌破 KI', 0)} 檔",
)

st.markdown("---")

# 部位總覽表格
st.subheader("📋 客戶部位總覽表 (同步自 Google Sheets)")
if evaluated_positions:
  table_rows = []
  for item in evaluated_positions:
    p = item["raw"]
    stock_names = " / ".join(
        [info["name"] for info in p["stocks"].values()]
    )
    table_rows.append({
        "客戶名稱": p["client_name"],
        "商品代號": p["code"],
        "申購金額 (USD)": f"${p['amount']:,.0f}",
        "預計月配息 (USD)": f"${item['monthly_coupon']:,.2f}",
        "年化配息率": f"{p['coupon_rate_annual']*100:.2f}%",
        "連結標的": stock_names,
        "距 KI 安全距離": (
            f"+{item['worst_dist_ki']:.2f}%"
            if item["worst_dist_ki"] > 0
            else f"{item['worst_dist_ki']:.2f}%"
        ),
        "當前狀態": item["status"],
        "交易日": p["trade_date"],
        "最後評價日": p["final_evaluation_date"],
    })
  st.dataframe(pd.DataFrame(table_rows), use_container_width=True)
else:
  st.info("尚無符合條件之部位資料。")

st.markdown("---")

# 單一部位走勢圖與新聞
st.subheader("🔍 單一部位走勢圖與最新動態明細")
pos_options = {
    f"{item['raw']['client_name']} - {item['raw']['product_name']} (金額: ${item['raw']['amount']:,.0f})": item[
        "raw"
    ]
    for item in evaluated_positions
}

if pos_options:
  selected_pos_label = st.selectbox("選擇欲檢視深度走勢圖的部位：", list(pos_options.keys()))
  selected_pos = pos_options[selected_pos_label]

  st.caption(
      f"商品代碼：{selected_pos['code']} | 交易日：{selected_pos['trade_date']} |"
      f" 最後評價日：{selected_pos['final_evaluation_date']}"
  )

  for symbol, info in selected_pos["stocks"].items():
    current_price, df_hist = get_stock_data_cached(
        info["ticker"], selected_pos["trade_date"]
    )

    if current_price == 0 or df_hist is None:
      st.error(f"⚠️ 無法取得 {symbol} 行情。")
      continue

    pct_from_initial = (current_price / info["initial"] - 1) * 100
    dist_to_autocall = (info["autocall"] - current_price) / current_price * 100
    dist_to_strike = (current_price - info["strike"]) / current_price * 100
    dist_to_ki = (current_price - info["ki"]) / current_price * 100

    st.markdown(f"#### 標的：{info['name']} ({symbol})")

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("最新收盤價", f"${current_price:.2f}", f"{pct_from_initial:+.2f}%")
    col_m2.metric(
        "距履約價 (78.23%)", f"${info['strike']:.2f}", f"{dist_to_strike:+.2f}%"
    )
    col_m3.metric("距 KI 下限 (65%)", f"${info['ki']:.2f}", f"{dist_to_ki:+.2f}%")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df_hist.index,
            y=df_hist["Close"],
            mode="lines+markers",
            name=symbol,
            line=dict(color="#1f77b4", width=2.5),
            marker=dict(size=4),
        )
    )

    fig.add_hline(
        y=info["autocall"],
        line_color="#ff7f0e",
        line_width=1.8,
        annotation_text="KO (105%)",
        annotation_position="top left",
    )
    fig.add_hline(
        y=info["strike"],
        line_color="#bcbd22",
        line_width=1.8,
        annotation_text="履約價",
        annotation_position="bottom left",
    )
    fig.add_hline(
        y=info["ki"],
        line_color="#7f7f7f",
        line_width=1.8,
        annotation_text="(A)KI",
        annotation_position="bottom left",
    )

    autocall_start_ts = (
        pd.to_datetime(selected_pos["autocall_start_date"]).timestamp() * 1000
    )
    fig.add_vline(
        x=autocall_start_ts,
        line_color="#2ca02c",
        line_dash="dash",
        line_width=1.8,
        annotation_text="提前買回起始日",
        annotation_position="top left",
        annotation_font_size=11,
        annotation_font_color="#2ca02c",
    )

    final_eval_ts = (
        pd.to_datetime(selected_pos["final_evaluation_date"]).timestamp()
        * 1000
    )
    fig.add_vline(
        x=final_eval_ts,
        line_color="#d62728",
        line_dash="dash",
        line_width=2.0,
        annotation_text="最後評價日",
        annotation_position="top right",
        annotation_font_size=11,
        annotation_font_color="#d62728",
    )

    max_idx = df_hist["Close"].idxmax()
    max_val = df_hist["Close"].max()
    min_idx = df_hist["Close"].idxmin()
    min_val = df_hist["Close"].min()
    latest_idx = df_hist.index[-1]

    fig.add_trace(
        go.Scatter(
            x=[max_idx],
            y=[max_val],
            mode="markers+text",
            name="區間最高",
            marker=dict(size=7, color="green"),
            text=[f"High ${max_val:.2f}"],
            textposition="top center",
            textfont=dict(size=10, color="green"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[min_idx],
            y=[min_val],
            mode="markers+text",
            name="區間最低",
            marker=dict(size=7, color="red"),
            text=[f"Low ${min_val:.2f}"],
            textposition="bottom center",
            textfont=dict(size=10, color="red"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[latest_idx],
            y=[current_price],
            mode="markers+text",
            name="最新價",
            marker=dict(size=8, color="#1f77b4"),
            text=[f"最新 ${current_price:.2f}"],
            textposition="middle right",
            textfont=dict(size=11, color="#1f77b4"),
        )
    )

    latest_date_str = df_hist.index[-1].strftime("%m/%d")
    fig.update_layout(
        title=dict(
            text=f"<b>{symbol} {latest_date_str}</b>",
            x=0.5,
            xanchor="center",
            font=dict(size=20, color="#333333"),
        ),
        xaxis=dict(
            title="",
            tickformat="%m月%d日",
            tickangle=-45,
            showgrid=True,
            gridcolor="#E5E5E5",
            showline=True,
            linecolor="#333333",
        ),
        yaxis=dict(
            title="",
            showgrid=True,
            gridcolor="#E5E5E5",
            showline=True,
            linecolor="#333333",
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=420,
        margin=dict(l=40, r=40, t=50, b=70),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.38,
            xanchor="center",
            x=0.5,
            font=dict(size=12),
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.write("📰 **最新相關新聞**")
    news = get_stock_news(f"{info['name']} 股票新聞")
    if news:
      for item in news:
        st.markdown(
            f"- [{item['title']}]({item['link']}) _({item['published'][:16]})_"
        )
    else:
      st.write("暫無最新新聞資料。")

    st.markdown("---")
