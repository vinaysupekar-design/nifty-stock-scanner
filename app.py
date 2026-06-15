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

if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None

# --- 2. COMPREHENSIVE INDICATOR MAPPING ---
INDICATOR_MAP = {
    "Simple Moving Average (SMA)": "sma",
    "Exponential Moving Average (EMA)": "ema",
    "MACD": "macd",
    "Average Directional Index (ADX)": "adx",
    "Supertrend": "supertrend",
    "Relative Strength Index (RSI)": "rsi",
    "Stochastic Oscillator": "stoch",
    "Commodity Channel Index (CCI)": "cci",
    "Williams %R": "willr",
    "Money Flow Index (MFI)": "mfi",
    "Bollinger Bands": "bbands"
}

# --- 3. DATA FETCHING ---
@st.cache_data(ttl=86400) # Data now caches for 24 hours
def fetch_nse_tickers(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        return (df['Symbol'].astype(str).str.strip() + ".NS").tolist()
    except:
        return []

@st.cache_data(ttl=86400) # Data now caches for 24 hours
def fetch_and_analyze_data(index_choice, selected_indicators):
    url_100 = "https://niftyindices.com/IndexConstituent/ind_nifty100list.csv"
    url_250 = "https://niftyindices.com/IndexConstituent/ind_niftylargemidcap250list.csv"

    tickers = fetch_nse_tickers(url_100) if index_choice == "Nifty 100" else fetch_nse_tickers(url_250)
    if not tickers:
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
            ta_function = INDICATOR_MAP.get(indicator_name)
            if ta_function:
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

if st.sidebar.button("Fetch & Calculate Data"):
    st.session_state.processed_data = fetch_and_analyze_data(index_choice, selected_indicators)
    st.sidebar.success("Data loaded! Use filters below.")

# --- 5. DYNAMIC SLIDERS & FILTERING ---
if st.session_state.processed_data is not None:
    df = st.session_state.processed_data.copy()
    
    st.sidebar.header("2. Dynamic Filters")
    available_cols = df.columns.tolist()
    
    # Trend Filter
    ma_logic = st.sidebar.radio("Trend Filter", ["None", "Price > 50 SMA", "Price > 200 SMA", "Golden Cross (50>200)"])
    if ma_logic == "Price > 50 SMA":
        df = df[df['Close_Price'] > df['SMA_50']]
    elif ma_logic == "Price > 200 SMA":
        df = df[df['Close_Price'] > df['SMA_200']]
    elif ma_logic == "Golden Cross (50>200)":
        df = df[df['SMA_50'] > df['SMA_200']]

    # Dynamic Sliders
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

    # --- 6. DISPLAY RESULTS (NEW UI) ---
    st.divider()
    
    # Step A: Show a clean, simplified summary table
    st.subheader(f"✅ {len(df)} Stocks Passed Your Filters")
    
    # Only show the bare minimum in the main table to keep it clean
    summary_cols = ['Ticker', 'Close_Price', 'SMA_50', 'SMA_200']
    
    # Add RSI to summary if it was calculated
    if rsi_cols and rsi_cols[0] in df.columns:
        summary_cols.append(rsi_cols[0])
        
    display_df = df[summary_cols].set_index('Ticker').round(2)
    st.dataframe(display_df, use_container_width=True)

    # Step B: The Deep Dive Section
    st.divider()
    st.subheader("🔍 Stock Deep Dive")
    st.markdown("Select a stock from the filtered list to view all calculated indicators.")
    
    if not df.empty:
        selected_stock = st.selectbox("Select Ticker:", df['Ticker'].tolist())
        
        if selected_stock:
            # Isolate the data for just this one stock
            stock_data = df[df['Ticker'] == selected_stock].iloc[0]
            
            # Create a 3-column layout for a beautiful dashboard feel
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Close Price", f"₹ {stock_data['Close_Price']:.2f}")
                st.metric("50-Day SMA", f"{stock_data['SMA_50']:.2f}")
                st.metric("200-Day SMA", f"{stock_data['SMA_200']:.2f}")
                
            with col2:
                # Dynamically display momentum indicators if they exist
                if rsi_cols:
                    st.metric(rsi_cols[0], f"{stock_data[rsi_cols[0]]:.2f}")
                if adx_cols:
                    st.metric(adx_cols[0], f"{stock_data[adx_cols[0]]:.2f}")
                if mfi_cols:
                    st.metric(mfi_cols[0], f"{stock_data[mfi_cols[0]]:.2f}")
                    
            with col3:
                # Show all the raw data generated by pandas_ta in a clean table
                st.markdown("**All Generated Indicators:**")
                standard_ohlcv = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume', 'Ticker', 'Close_Price', 'SMA_50', 'SMA_200']
                ta_data = stock_data.drop(labels=[col for col in standard_ohlcv if col in stock_data.index])
                
                # Format the data into a clean vertical dataframe
                ta_df = pd.DataFrame(ta_data).reset_index()
                ta_df.columns = ['Indicator', 'Value']
                st.dataframe(ta_df, hide_index=True, use_container_width=True)
    else:
        st.warning("No stocks match your current slider settings. Loosen the filters to see data.")

else:
    st.info("👈 Step 1: Select your universe and indicators, then click 'Fetch & Calculate Data'.")
