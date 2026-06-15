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
def fetch_and_analyze_data(index_choice, selected_indicators):
    url_100 = "https://niftyindices.com/IndexConstituent/ind_nifty100list.csv"
    url_250 = "https://niftyindices.com/IndexConstituent/ind_niftylargemidcap250list.csv"

    tickers = fetch_nse_tickers(url_100) if index_choice == "Nifty 100" else fetch_nse_tickers(url_250)
    if not tickers:
        tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "TRENT.NS", "BEL.NS"]

    latest_data = []
    progress_text = "Downloading Market Data. Please wait..."
    my_bar = st.progress(0, text=progress_text)

    for i, ticker in enumerate(tickers):
        df = yf.download(ticker, period="1y", progress=False)
        if df.empty or len(df) < 50:
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        # Base calculations for Market Pulse
        df['Close_Price'] = df['Close']
        df['Prev_Close'] = df['Close'].shift(1)
        df['Change_%'] = ((df['Close'] - df['Prev_Close']) / df['Prev_Close']) * 100
        df['Turnover_Cr'] = (df['Close'] * df['Volume']) / 10000000 # Convert to Crores

        df['SMA_50'] = df.ta.sma(length=50)
        df['SMA_200'] = df.ta.sma(length=200)

        # Dynamic Indicators
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

# --- 4. SIDEBAR SETTINGS ---
st.sidebar.title("⚙️ Terminal Settings")
index_choice = st.sidebar.radio("1. Select Universe", ["Nifty 100", "LargeMidcap 250"])

selected_indicators = st.sidebar.multiselect(
    "2. Add Indicators to Screener",
    options=list(INDICATOR_MAP.keys()),
    default=["Relative Strength Index (RSI)", "MACD", "Average Directional Index (ADX)"]
)

if st.sidebar.button("Fetch Market Data", use_container_width=True):
    st.session_state.processed_data = fetch_and_analyze_data(index_choice, selected_indicators)

# --- 5. MAIN DASHBOARD ---
if st.session_state.processed_data is not None:
    df = st.session_state.processed_data.copy()
    
    # Create the two main views
    tab1, tab2 = st.tabs(["📊 Market Pulse", "🎯 Interactive Screener"])

    # ==========================================
    # TAB 1: MARKET PULSE (Image 1 Replica)
    # ==========================================
    with tab1:
        st.subheader(f"Market Pulse ({time.strftime('%Y-%m-%d')})")
        
        # Top Level Metrics
        advancers = len(df[df['Change_%'] > 0])
        decliners = len(df[df['Change_%'] < 0])
        total_turnover = df['Turnover_Cr'].sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📈 Advancers vs Decliners", f"{advancers} / {decliners}")
        m2.metric("💸 Total Index Turnover", f"₹ {total_turnover:,.0f} Cr")
        m3.metric("🔥 Top Gainer", df.loc[df['Change_%'].idxmax()]['Ticker'], f"{df['Change_%'].max():.2f}%")
        m4.metric("🩸 Top Loser", df.loc[df['Change_%'].idxmin()]['Ticker'], f"{df['Change_%'].min():.2f}%")
        
        st.divider()
        
        # Color styling function for dataframes
        def color_change(val):
            color = 'green' if val > 0 else 'red'
            return f'color: {color}'

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
    # TAB 2: MASTER-DETAIL SCREENER (Image 2 Replica)
    # ==========================================
    with tab2:
        # Dynamic Sidebar Filters (Only show in Tab 2)
        st.sidebar.divider()
        st.sidebar.subheader("3. Active Filters")
        available_cols = df.columns.tolist()
        
        ma_logic = st.sidebar.radio("Trend Filter", ["None", "Price > 50 SMA", "Price > 200 SMA"])
        if ma_logic == "Price > 50 SMA":
            df = df[df['Close_Price'] > df['SMA_50']]
        elif ma_logic == "Price > 200 SMA":
            df = df[df['Close_Price'] > df['SMA_200']]

        rsi_cols = [c for c in available_cols if c.startswith('RSI_')]
        if rsi_cols:
            rsi_min, rsi_max = st.sidebar.slider(f"Target {rsi_cols[0]}", 0, 100, (0, 100))
            df = df[(df[rsi_cols[0]] >= rsi_min) & (df[rsi_cols[0]] <= rsi_max)]
            
        adx_cols = [c for c in available_cols if c.startswith('ADX_')]
        if adx_cols:
            adx_min = st.sidebar.slider(f"Min {adx_cols[0]}", 0, 100, 0)
            df = df[df[adx_cols[0]] >= adx_min]

        # Top Bar: Stock Count & Download Button
        t_col1, t_col2 = st.columns([4, 1])
        t_col1.markdown(f"**{len(df)} Stocks Match Criteria**")
        
        csv_data = df.to_csv(index=False).encode('utf-8')
        t_col2.download_button("📥 Download Data", data=csv_data, file_name="nifty_screener_data.csv", mime="text/csv", use_container_width=True)

        # The Master-Detail Layout (70% Left Table, 30% Right Panel)
        sc1, sc2 = st.columns([2.5, 1])
        
        with sc1:
            # Prepare clean dataframe for the left side
            display_cols = ['Ticker', 'Close_Price', 'Change_%']
            if rsi_cols: display_cols.append(rsi_cols[0])
            if adx_cols: display_cols.append(adx_cols[0])
            
            clean_df = df[display_cols].set_index('Ticker').round(2)
            
            # Interactive Dataframe: on_select allows clicking a row to update the UI
            event = st.dataframe(
                clean_df.style.map(color_change, subset=['Change_%']).format({"Change_%": "{:.2f}%"}),
                use_container_width=True,
                height=600,
                on_select="rerun",
                selection_mode="single-row"
            )

        with sc2:
            st.markdown("### 📊 Detail Panel")
            
            # Catch the row selected by the user
            selected_rows = event.selection.rows
            
            if selected_rows:
                # Get the ticker name from the selected row index
                selected_ticker = clean_df.index[selected_rows[0]]
                stock_data = df[df['Ticker'] == selected_ticker].iloc[0]
                
                # Big Header Card
                st.markdown(f"## {selected_ticker}")
                st.markdown(f"### ₹ {stock_data['Close_Price']:.2f}")
                
                change_color = "🟢" if stock_data['Change_%'] > 0 else "🔴"
                st.markdown(f"{change_color} **{stock_data['Change_%']:.2f}%**")
                
                st.divider()
                
                # RSI Visual Gauge
                if rsi_cols:
                    rsi_val = stock_data[rsi_cols[0]]
                    st.caption("RSI GAUGE")
                    st.progress(int(rsi_val), text=f"RSI: {rsi_val:.1f}")
                
                # Categorized Indicators
                c1, c2 = st.columns(2)
                with c1:
                    st.caption("TREND")
                    st.markdown(f"**SMA 50:**<br>₹{stock_data['SMA_50']:.2f}", unsafe_allow_html=True)
                    st.markdown(f"**SMA 200:**<br>₹{stock_data['SMA_200']:.2f}", unsafe_allow_html=True)
                
                with c2:
                    st.caption("MOMENTUM")
                    if adx_cols:
                        st.markdown(f"**ADX:**<br>{stock_data[adx_cols[0]]:.2f}", unsafe_allow_html=True)
                    
                    macd_cols = [c for c in available_cols if c.startswith('MACD_')]
                    if macd_cols:
                        st.markdown(f"**MACD:**<br>{stock_data[macd_cols[0]]:.2f}", unsafe_allow_html=True)

            else:
                # Default empty state
                st.info("👆 Click on any row in the table to the left to view a deep-dive analysis of that stock here.")

else:
    # Landing page before data is fetched
    st.title("NIFTY.DASH")
    st.markdown("### Market Intelligence Terminal")
    st.info("👈 Please select your universe and indicators in the sidebar, then click **Fetch Market Data** to begin.")
