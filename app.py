import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import io
import time

# --- 1. PAGE CONFIGURATION & STATE ---
st.set_page_config(page_title="Mega Interactive Stock Scanner", layout="wide")
st.title("📊 Mega-Indicator Interactive Scanner")
st.markdown("Select from 50+ indicators, fetch data, and use dynamic sliders to filter results.")

# Initialize session state to hold our calculated data so it doesn't vanish on slider move
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None

# --- 2. COMPREHENSIVE INDICATOR MAPPING ---
INDICATOR_MAP = {
    # Trend
    "Simple Moving Average (SMA)": "sma",
    "Exponential Moving Average (EMA)": "ema",
    "Double EMA (DEMA)": "dema",
    "MACD": "macd",
    "Average Directional Index (ADX)": "adx",
    "Parabolic SAR": "psar",
    "Supertrend": "supertrend",
    "Ichimoku Clouds": "ichimoku",
    "Aroon": "aroon",
    "Detrended Price Oscillator (DPO)": "dpo",
    "Linear Regression": "linreg",
    # Momentum
    "Relative Strength Index (RSI)": "rsi",
    "Stochastic Oscillator": "stoch",
    "Stochastic RSI": "stochrsi",
    "Commodity Channel Index (CCI)": "cci",
    "Williams %R": "willr",
    "Money Flow Index (MFI)": "mfi",
    "Rate of Change (ROC)": "roc",
    "Awesome Oscillator (AO)": "ao",
    "Balance of Power (BOP)": "bop",
    "Chande Momentum Oscillator (CMO)": "cmo",
    "Coppock Curve": "coppock",
    "Momentum (MOM)": "mom",
    "Ultimate Oscillator (UO)": "uo",
    "Percentage Price Oscillator (PPO)": "ppo",
    # Volatility
    "Bollinger Bands": "bbands",
    "Average True Range (ATR)": "atr",
    "Keltner Channel": "kc",
    "Donchian Channels": "donchian",
    "True Range": "true_range",
    "Ulcer Index": "ui",
    # Volume
    "Accumulation/Distribution (AD)": "ad",
    "On-Balance Volume (OBV)": "obv",
    "Chaikin Money Flow (CMF)": "cmf",
    "Volume Weighted Average Price (VWAP)": "vwap",
    "Positive Volume Index (PVI)": "pvi",
    "Negative Volume Index (NVI)": "nvi"
}

# --- 3. DATA FETCHING ---
@st.cache_data(ttl=3600)
def fetch_nse_tickers(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        return (df['Symbol'].astype(str).str.strip() + ".NS").tolist()
    except:
        return []

@st.cache_data(ttl=3600)
def fetch_and_analyze_data(index_choice, selected_indicators):
    url_100 = "https://niftyindices.com/IndexConstituent/ind_nifty100list.csv"
    url_250 = "https://niftyindices.com/IndexConstituent/ind_niftylargemidcap250list.csv"

    tickers = fetch_nse_tickers(url_100) if index_choice == "Nifty 100" else fetch_nse_tickers(url_250)

    if not tickers:
        st.warning("NSE server blocked the ticker request. Using fallback list.")
        tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "TRENT.NS", "BEL.NS"]

    latest_data = []
    progress_text = "Fetching data and calculating indicators. Please wait..."
    my_bar = st.progress(0, text=progress_text)

    for i, ticker in enumerate(tickers):
        df = yf.download(ticker, period="2y", progress=False)
        if df.empty or len(df) < 200:
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        df['Close_Price'] = df['Close']
        df['SMA_50'] = df.ta.sma(length=50)
        df['SMA_200'] = df.ta.sma(length=200)

        for indicator_name in selected_indicators:
            ta_function = INDICATOR_MAP[indicator_name]
            try:
                getattr(df.ta, ta_function)(append=True)
            except Exception:
                pass 

        latest_row = df.iloc[-1:].copy()
        latest_row['Ticker'] = ticker.replace(".NS", "")
        latest_data.append(latest_row)

        my_bar.progress((i + 1) / len(tickers), text=progress_text)
        time.sleep(0.01)

    my_bar.empty()
    return pd.concat(latest_data, ignore_index=True)

# --- 4. SIDEBAR: SETUP & FETCH ---
st.sidebar.header("1. Scanner Setup")
index_choice = st.sidebar.radio("Select Universe:", ["Nifty 100", "LargeMidcap 250"])

selected_indicators = st.sidebar.multiselect(
    "Choose Indicators to Calculate:",
    options=list(INDICATOR_MAP.keys()),
    default=["Relative Strength Index (RSI)", "MACD", "Average Directional Index (ADX)"]
)

# Fetch data and store in session state
if st.sidebar.button("Fetch & Calculate Data"):
    st.session_state.processed_data = fetch_and_analyze_data(index_choice, selected_indicators)
    st.sidebar.success("Data loaded! Use filters below.")

# --- 5. DYNAMIC SLIDERS & FILTERING ---
if st.session_state.processed_data is not None:
    df = st.session_state.processed_data.copy()
    
    st.sidebar.header("2. Dynamic Filters")
    st.sidebar.markdown("Adjust the sliders to filter the table in real-time.")
    
    available_cols = df.columns.tolist()
    
    # Base Trend Filter
    ma_logic = st.sidebar.radio("Trend Filter", ["None", "Price > 50 SMA", "Price > 200 SMA", "Golden Cross (50>200)"])
    if ma_logic == "Price > 50 SMA":
        df = df[df['Close_Price'] > df['SMA_50']]
    elif ma_logic == "Price > 200 SMA":
        df = df[df['Close_Price'] > df['SMA_200']]
    elif ma_logic == "Golden Cross (50>200)":
        df = df[df['SMA_50'] > df['SMA_200']]

    # Dynamic Sliders based on selected indicators
    rsi_cols = [c for c in available_cols if c.startswith('RSI_')]
    if rsi_cols:
        rsi_min, rsi_max = st.sidebar.slider(f"Target {rsi_cols[0]}", 0, 100, (30, 70))
        df = df[(df[rsi_cols[0]] >= rsi_min) & (df[rsi_cols[0]] <= rsi_max)]

    adx_cols = [c for c in available_cols if c.startswith('ADX_')]
    if adx_cols:
        adx_min = st.sidebar.slider(f"Min {adx_cols[0]} (Trend Strength)", 0, 100, 25)
        df = df[df[adx_cols[0]] >= adx_min]

    mfi_cols = [c for c in available_cols if c.startswith('MFI_')]
    if mfi_cols:
        mfi_min, mfi_max = st.sidebar.slider(f"Target {mfi_cols[0]}", 0, 100, (20, 80))
        df = df[(df[mfi_cols[0]] >= mfi_min) & (df[mfi_cols[0]] <= mfi_max)]
        
    cci_cols = [c for c in available_cols if c.startswith('CCI_')]
    if cci_cols:
        cci_min, cci_max = st.sidebar.slider(f"Target {cci_cols[0]}", -300, 300, (-100, 100))
        df = df[(df[cci_cols[0]] >= cci_min) & (df[cci_cols[0]] <= cci_max)]
        
    willr_cols = [c for c in available_cols if c.startswith('WILLR_')]
    if willr_cols:
        willr_min, willr_max = st.sidebar.slider(f"Target {willr_cols[0]}", -100, 0, (-80, -20))
        df = df[(df[willr_cols[0]] >= willr_min) & (df[willr_cols[0]] <= willr_max)]

    # --- 6. DISPLAY RESULTS ---
    base_cols = ['Ticker', 'Close_Price', 'SMA_50', 'SMA_200']
    standard_ohlcv = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    ta_cols = [col for col in df.columns if col not in standard_ohlcv and col not in base_cols]
    
    display_df = df[base_cols + ta_cols].dropna(axis=1, how='all').set_index('Ticker').round(2)

    def highlight_indicators(val, col_name):
        if pd.isna(val):
            return ''
        color = ''
        if 'RSI' in col_name:
            color = 'color: #00FF00' if val < 30 else ('color: #FF0000' if val > 70 else '')
        elif 'MACD' in col_name and len(col_name.split('_')) == 4: 
            color = 'color: #00FF00' if val > 0 else 'color: #FF0000'
        return color

    styled_df = display_df.style.apply(lambda x: [highlight_indicators(v, x.name) for v in x], axis=0)

    st.subheader(f"Results: {len(display_df)} stocks match your slider criteria")
    st.dataframe(styled_df, use_container_width=True, height=600)

else:
    st.info("👈 Step 1: Select your universe and indicators, then click 'Fetch & Calculate Data'.")