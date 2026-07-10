import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import io
import time

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Nifty Dash Terminal", layout="wide", initial_sidebar_state="expanded")

if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None

# --- 2. INDICATOR MAPPING ---
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

# --- 3. DATA FETCHING & CALCULATION ---
@st.cache_data(ttl=86400) 
def fetch_nse_tickers(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        return (df['Symbol'].astype(str).str.strip() + ".NS").tolist()
    except:
        return []

@st.cache_data(ttl=86400) 
def fetch_and_analyze_data(index_choice):
    url_100 = "https://niftyindices.com/IndexConstituent/ind_nifty100list.csv"
    url_250 = "https://niftyindices.com/IndexConstituent/ind_niftylargemidcap250list.csv"

    tickers = fetch_nse_tickers(url_100) if index_choice == "Nifty 100" else fetch_nse_tickers(url_250)
    if not tickers:
        tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "TRENT.NS", "BEL.NS"]

    latest_data = []
    
    # Bulk Threaded Download for massive speed improvement
    with st.spinner(f"Bulk downloading market data for {len(tickers)} stocks..."):
        raw_data = yf.download(tickers, period="1y", group_by="ticker", threads=True, progress=False)

    my_bar = st.progress(0, text="Calculating ALL Technical Indicators. Please wait...")

    for i, ticker in enumerate(tickers):
        try:
            df = raw_data[ticker].copy().dropna() if len(tickers) > 1 else raw_data.copy().dropna()
            
            if df.empty or len(df) < 50:
                continue

            # Base calculations for Market Pulse
            df['Close_Price'] = df['Close']
            df['Prev_Close'] = df['Close'].shift(1)
            df['Change_%'] = ((df['Close'] - df['Prev_Close']) / df['Prev_Close']) * 100
            df['Turnover_Cr'] = (df['Close'] * df['Volume']) / 10000000 

            df['SMA_50'] = df.ta.sma(length=50)
            df['SMA_200'] = df.ta.sma(length=200)

            # Calculate EVERY indicator in the map upfront
            for ta_function in INDICATOR_MAP.values():
                try:
                    getattr(df.ta, ta_function)(append=True)
                except Exception:
                    pass 

            latest_row = df.iloc[-1:].copy()
            latest_row['Ticker'] = ticker.replace(".NS", "")
            latest_data.append(latest_row)
            
        except Exception:
            continue

        my_bar.progress((i + 1) / len(tickers))

    my_bar.empty()
    return pd.concat(latest_data, ignore_index=True)

# --- 4. SIDEBAR SETTINGS ---
st.sidebar.title("⚙️ Terminal Settings")
index_choice = st.sidebar.radio("1. Select Universe", ["Nifty 100", "LargeMidcap 250"])

# The button now just fetches data. We don't pass selected_indicators to the calculation engine anymore.
if st.sidebar.button("Fetch Market Data", use_container_width=True):
    st.session_state.processed_data = fetch_and_analyze_data(index_choice)

# --- 5. MAIN DASHBOARD ---
if st.session_state.processed_data is not None:
    df = st.session_state.processed_data.copy()
    
    tab1, tab2 = st.tabs(["📊 Market Pulse", "🎯 Interactive Screener"])

    # ==========================================
    # TAB 1: MARKET PULSE
    # ==========================================
    with tab1:
        st.subheader(f"Market Pulse ({time.strftime('%Y-%m-%d')})")
        
        advancers = len(df[df['Change_%'] > 0])
        decliners = len(df[df['Change_%'] < 0])
        total_turnover = df['Turnover_Cr'].sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📈 Advancers vs Decliners", f"{advancers} / {decliners}")
        m2.metric("💸 Total Index Turnover", f"₹ {total_turnover:,.0f} Cr")
        m3.metric("🔥 Top Gainer", df.loc[df['Change_%'].idxmax()]['Ticker'], f"{df['Change_%'].max():.2f}%")
        m4.metric("🩸 Top Loser", df.loc[df['Change_%'].idxmin()]['Ticker'], f"{df['Change_%'].min():.2f}%")
        
        st.divider()
        
        def color_change(val):
            if pd.isna(val): return ''
            return 'color: green' if val > 0 else 'color: red'

        col_g, col_l, col_t = st.columns(3)
        
        with col_g:
            st.markdown("### 🔥 Top Gainers")
            gainers = df.nlargest(5, 'Change_%')[['Ticker', 'Close_Price', 'Change_%']].set_index('Ticker')
            st.dataframe(gainers.style.map(color_change, subset=['Change_%']).format({"Close_Price": "₹{:.2f}", "Change_%": "{:.2f}%"}), use_container_width=True)

        with col_l:
            st.markdown("### 🩸 Top Losers")
            losers = df.nsmallest(5, 'Change_%')[['Ticker', 'Close_Price', 'Change_%']].set_index('Ticker')
            st.dataframe(losers.style.map(color_change, subset=['Change_%']).format({"Close_Price": "₹{:.2f}", "Change_%": "{:.2f}%"}), use_container_width=True)

        with col_t:
            st.markdown("### 💸 Highest Turnover")
            turnover = df.nlargest(5, 'Turnover_Cr')[['Ticker', 'Close_Price', 'Turnover_Cr']].set_index('Ticker')
            st.dataframe(turnover.style.format({"Close_Price": "₹{:.2f}", "Turnover_Cr": "₹{:.2f} Cr"}), use_container_width=True)


    # ==========================================
    # TAB 2: MASTER-DETAIL SCREENER
    # ==========================================
    with tab2:
        st.sidebar.divider()
        st.sidebar.subheader("2. Filter Screener")
        
        # User selects which pre-calculated indicators to filter by
        selected_indicators = st.sidebar.multiselect(
            "Select Indicators to Filter By:",
            options=list(INDICATOR_MAP.keys()),
            default=["Relative Strength Index (RSI)", "MACD"]
        )
        
        available_cols = df.columns.tolist()
        
        # Base Trend Logic
        ma_logic = st.sidebar.radio("Trend Filter", ["None", "Price > 50 SMA", "Price > 200 SMA"])
        if ma_logic == "Price > 50 SMA": df = df[df['Close_Price'] > df['SMA_50']]
        elif ma_logic == "Price > 200 SMA": df = df[df['Close_Price'] > df['SMA_200']]

        display_cols = ['Ticker', 'Close_Price', 'Change_%']
        
        # Dynamically generate sliders ONLY for the selected indicators
        for ind_name in selected_indicators:
            ta_func = INDICATOR_MAP[ind_name]
            
            # Find the exact column name generated by pandas_ta (e.g., finding 'RSI_14' from 'rsi')
            matched_cols = [c for c in available_cols if c.startswith(ta_func.upper() + '_') or c.startswith(ta_func.upper())]
            
            if matched_cols:
                col_name = matched_cols[0]
                display_cols.append(col_name) # Add it to the main table display
                
                # Build the dynamic slider
                min_val = float(df[col_name].min())
                max_val = float(df[col_name].max())
                
                if pd.isna(min_val) or min_val == max_val: 
                    continue
                    
                if ta_func in ['rsi', 'mfi', 'adx']:
                    s_min, s_max = 0.0, 100.0
                elif ta_func == 'willr':
                    s_min, s_max = -100.0, 0.0
                else:
                    buf = abs(max_val - min_val) * 0.05
                    s_min, s_max = min_val - buf, max_val + buf
                    
                user_range = st.sidebar.slider(f"{ind_name}", float(s_min), float(s_max), (float(min_val), float(max_val)))
                df = df[(df[col_name] >= user_range[0]) & (df[col_name] <= user_range[1])]

        t_col1, t_col2 = st.columns([4, 1])
        t_col1.markdown(f"**{len(df)} Stocks Match Criteria**")
        
        csv_data = df.to_csv(index=False).encode('utf-8')
        t_col2.download_button("📥 Download Data", data=csv_data, file_name="screener_data.csv", mime="text/csv", use_container_width=True)

        sc1, sc2 = st.columns([2.5, 1])
        
        with sc1:
            clean_df = df[display_cols].set_index('Ticker').round(2)
            
            event = st.dataframe(
                clean_df.style.map(color_change, subset=['Change_%']).format({"Change_%": "{:.2f}%"}),
                use_container_width=True,
                height=600,
                on_select="rerun",
                selection_mode="single-row"
            )

        with sc2:
            st.markdown("### 📊 Detail Panel")
            selected_rows = event.selection.rows
            
            if selected_rows:
                selected_ticker = clean_df.index[selected_rows[0]]
                stock_data = df[df['Ticker'] == selected_ticker].iloc[0]
                
                st.markdown(f"## {selected_ticker}")
                st.markdown(f"### ₹ {stock_data['Close_Price']:.2f}")
                
                change_color = "🟢" if stock_data['Change_%'] > 0 else "🔴"
                st.markdown(f"{change_color} **{stock_data['Change_%']:.2f}%**")
                
                st.divider()
                
                c1, c2 = st.columns(2)
                with c1:
                    st.caption("TREND")
                    st.markdown(f"**SMA 50:**<br>₹{stock_data['SMA_50']:.2f}", unsafe_allow_html=True)
                    st.markdown(f"**SMA 200:**<br>₹{stock_data['SMA_200']:.2f}", unsafe_allow_html=True)
                
                with c2:
                    st.caption("KEY METRICS")
                    # Dynamically show metrics if they exist in the row
                    rsi_search = [c for c in available_cols if c.startswith('RSI_')]
                    if rsi_search:
                        st.markdown(f"**RSI:**<br>{stock_data[rsi_search[0]]:.2f}", unsafe_allow_html=True)
                        
                    macd_search = [c for c in available_cols if c.startswith('MACD_')]
                    if macd_search:
                        st.markdown(f"**MACD:**<br>{stock_data[macd_search[0]]:.2f}", unsafe_allow_html=True)
            else:
                st.info("👆 Click on any row in the table to the left to view a deep-dive analysis of that stock here.")

else:
    st.title("NIFTY.DASH")
    st.markdown("### Market Intelligence Terminal")
    st.info("👈 Please select your universe in the sidebar, then click **Fetch Market Data** to begin.")
