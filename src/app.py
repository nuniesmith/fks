# src/app.py
"""
Enhanced Streamlit app with:
- Live WebSocket price updates
- Persistent session state
- Live charts
- Multi-account support
- Real-time PnL tracking
"""

import os
os.environ['TZ'] = 'America/Toronto'

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pytz
import json
import uuid
from datetime import datetime, timedelta

from config import SYMBOLS, MAINS, ALTS, TIMEFRAMES, DISCORD_WEBHOOK_URL
from data import (
    get_historical_data, get_current_price, get_live_prices, 
    get_price_stats, is_live_data_available, get_websocket_status
)
from backtest import run_backtest
from signals import get_current_signal
from utils import log_trade, send_discord_notification
from cache import session_manager, price_cache
from db_utils import (
    get_accounts, create_account, get_positions, update_position,
    record_trade, get_balance_history, get_ohlcv_data, get_sync_status
)
from database import Session

# Set timezone
TIMEZONE = pytz.timezone('America/Toronto')

# Page config
st.set_page_config(
    page_title="FKS Trading Tool",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Get or create session ID
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

SESSION_ID = st.session_state.session_id


def load_session_state():
    """Load session state from Redis"""
    saved_state = session_manager.load_state(SESSION_ID)
    if saved_state:
        for key, value in saved_state.items():
            if not key.startswith('_'):  # Skip internal keys
                st.session_state[key] = value


def save_session_state():
    """Save session state to Redis"""
    state_to_save = {
        key: value for key, value in st.session_state.items()
        if not key.startswith('_') and key != 'session_id'
    }
    session_manager.save_state(SESSION_ID, state_to_save)


# Load saved state on startup
if 'state_loaded' not in st.session_state:
    load_session_state()
    st.session_state.state_loaded = True


# Sidebar - Connection Status & Account Selection
with st.sidebar:
    st.title("📈 FKS Trading Tool")
    
    # WebSocket Status
    st.subheader("🔌 Connection Status")
    ws_status = get_websocket_status()
    
    if ws_status['status'] == 'connected':
        st.success("✅ Live Data Connected")
    elif ws_status['status'] == 'disconnected':
        st.warning("⚠️ Live Data Disconnected")
    else:
        st.info("ℹ️ Live Data Status Unknown")
    
    if ws_status['timestamp']:
        st.caption(f"Last update: {ws_status['timestamp'][:19]}")
    
    # Account Selection
    st.subheader("💼 Account")
    accounts = get_accounts(active_only=True)
    
    if accounts:
        account_options = {f"{acc.name} (${float(acc.current_balance):,.2f})": acc.id for acc in accounts}
        selected_account_name = st.selectbox(
            "Select Account",
            options=list(account_options.keys()),
            key="selected_account_dropdown"
        )
        selected_account_id = account_options[selected_account_name]
        st.session_state.selected_account_id = selected_account_id
        
        # Show account details
        selected_account = next(acc for acc in accounts if acc.id == selected_account_id)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Balance", f"${float(selected_account.current_balance):,.2f}")
        with col2:
            pnl = float(selected_account.current_balance) - float(selected_account.initial_balance)
            st.metric("PnL", f"${pnl:,.2f}", f"{(pnl/float(selected_account.initial_balance)*100):.2f}%")
    else:
        st.warning("No accounts found. Create one below.")
        
        with st.expander("➕ Create Account"):
            acc_name = st.text_input("Account Name")
            acc_type = st.selectbox("Type", ["personal", "prop_firm"])
            initial_bal = st.number_input("Initial Balance", min_value=100.0, value=10000.0)
            
            if st.button("Create"):
                create_account(acc_name, acc_type, initial_bal)
                st.success("Account created!")
                st.rerun()
    
    # Refresh button
    if st.button("🔄 Refresh Data"):
        save_session_state()
        st.rerun()


# Main Content Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Live Prices", 
    "📈 Data & Analysis",
    "🎯 Optimization",
    "💡 Signals",
    "📋 Positions",
    "📜 Trade History",
    "💬 Notifications",
    "🧠 Intelligence"  # NEW: RAG Intelligence Tab
])

# TAB 1: Live Prices
with tab1:
    st.header("📊 Live Market Prices")
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("Auto-refresh (every 5 seconds)", value=False, key="auto_refresh_prices")
    
    if auto_refresh:
        st_autorefresh = st.empty()
        with st_autorefresh:
            st.info("Auto-refreshing every 5 seconds...")
        
        import time
        time.sleep(5)
        st.rerun()
    
    # Get live prices
    live_prices = get_live_prices(SYMBOLS)
    
    # Display as table
    price_data = []
    for symbol in SYMBOLS:
        stats = get_price_stats(symbol)
        if stats:
            price_data.append({
                'Symbol': symbol,
                'Price': f"${stats['price']:,.2f}",
                '24h Change': f"{stats['price_change_percent_24h']:+.2f}%",
                '24h High': f"${stats['high_24h']:,.2f}",
                '24h Low': f"${stats['low_24h']:,.2f}",
                'Volume': f"{stats['volume_24h']:,.2f}"
            })
    
    if price_data:
        df_prices_display = pd.DataFrame(price_data)
        st.dataframe(df_prices_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No live price data available. Check WebSocket connection.")
    
    # Mini charts
    st.subheader("📉 Price Charts (Last 100 candles)")
    
    chart_timeframe = st.selectbox("Timeframe", TIMEFRAMES, index=5, key="live_chart_tf")
    
    cols = st.columns(2)
    for idx, symbol in enumerate(SYMBOLS[:4]):  # Show first 4 symbols
        with cols[idx % 2]:
            try:
                df = get_ohlcv_data(symbol, chart_timeframe, limit=100)
                if not df.empty:
                    fig, ax = plt.subplots(figsize=(6, 3))
                    df['close'].plot(ax=ax, title=f"{symbol} - {chart_timeframe}", color='blue')
                    ax.grid(True, alpha=0.3)
                    st.pyplot(fig)
                    plt.close()
            except Exception as e:
                st.error(f"Error loading chart for {symbol}: {e}")


# TAB 2: Data & Analysis
with tab2:
    st.header("📈 Historical Data & Analysis")
    
    col1, col2 = st.columns(2)
    with col1:
        interval = st.selectbox('Timeframe', TIMEFRAMES, index=5, key="hist_interval")
    with col2:
        limit = st.number_input('Number of Candles', min_value=100, max_value=10000, value=1000, key="hist_limit")
    
    if st.button('📥 Load Data from Database'):
        with st.spinner('Loading data...'):
            try:
                df_prices = {}
                for sym in SYMBOLS:
                    df = get_ohlcv_data(sym, interval, limit=limit)
                    if not df.empty:
                        df_prices[sym] = df
                
                if df_prices:
                    st.session_state.df_prices = df_prices
                    common_index = df_prices[SYMBOLS[0]].index
                    for df in list(df_prices.values())[1:]:
                        common_index = common_index.intersection(df.index)
                    
                    st.success(f'✅ Loaded {len(common_index)} candles from {common_index[0].date()} to {common_index[-1].date()}')
                    save_session_state()
                else:
                    st.error('No data found. Run data sync first.')
            except Exception as e:
                st.error(f'Error: {e}')
    
    # Display loaded data
    if 'df_prices' in st.session_state and st.session_state.df_prices:
        st.subheader("📊 Data Preview")
        selected_symbol = st.selectbox("View Symbol", SYMBOLS, key="preview_symbol")
        st.dataframe(st.session_state.df_prices[selected_symbol].tail(20))
        
        # Plot
        fig, ax = plt.subplots(figsize=(12, 6))
        st.session_state.df_prices[selected_symbol]['close'].plot(ax=ax, title=f"{selected_symbol} Price History")
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)
        plt.close()


# TAB 3: Optimization & Backtest
with tab3:
    st.header("🎯 Strategy Optimization & Backtesting")
    
    if 'df_prices' in st.session_state:
        import optuna
        from optimizer import objective
        
        col1, col2 = st.columns(2)
        with col1:
            n_trials = st.number_input("Optimization Trials", min_value=10, max_value=500, value=50)
        
        if st.button('🚀 Run Optimization'):
            with st.spinner(f'Running {n_trials} trials...'):
                study = optuna.create_study(direction='maximize')
                study.optimize(
                    lambda trial: objective(trial, st.session_state.df_prices), 
                    n_trials=n_trials,
                    show_progress_bar=False
                )
                st.session_state.best_params = study.best_params
                st.success(f'✅ Best Sharpe Ratio: {study.best_value:.3f}')
                st.json(study.best_params)
                save_session_state()
        
        if 'best_params' in st.session_state:
            st.subheader("📊 Backtest Results")
            
            if st.button('▶️ Run Backtest'):
                with st.spinner('Running backtest...'):
                    metrics, returns, cum_ret, trades = run_backtest(
                        st.session_state.df_prices, 
                        **st.session_state.best_params
                    )
                    
                    # Display metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Sharpe Ratio", f"{metrics['Sharpe']:.2f}")
                    with col2:
                        st.metric("Sortino Ratio", f"{metrics['Sortino']:.2f}")
                    with col3:
                        st.metric("Max Drawdown", f"{metrics['Max Drawdown']:.2%}")
                    with col4:
                        st.metric("Total Return", f"{metrics['Total Return']:.2%}")
                    
                    # Equity curve
                    fig, ax = plt.subplots(figsize=(12, 6))
                    cum_ret.plot(ax=ax, title='Equity Curve')
                    ax.grid(True, alpha=0.3)
                    st.pyplot(fig)
                    plt.close()
                    
                    # Trades table
                    if trades:
                        st.subheader("📋 Trade Log")
                        trades_df = pd.DataFrame(trades)
                        st.dataframe(trades_df, use_container_width=True)
    else:
        st.info("⬅️ Load historical data first in the 'Data & Analysis' tab")


# TAB 4: Signals
with tab4:
    st.header("💡 Current Trading Signal")
    
    if 'selected_account_id' in st.session_state:
        account = next((acc for acc in get_accounts() if acc.id == st.session_state.selected_account_id), None)
        if account:
            account_size = float(account.current_balance)
            
            if 'df_prices' in st.session_state and 'best_params' in st.session_state:
                if st.button('🎯 Generate Signal'):
                    with st.spinner('Analyzing market...'):
                        try:
                            signal, suggestions = get_current_signal(
                                st.session_state.df_prices,
                                st.session_state.best_params,
                                account_size
                            )
                            
                            if signal == 1:
                                st.success("📈 Signal: HOLD ASSETS (50% BTC/ETH mix, 50% Alts)")
                            else:
                                st.warning("💵 Signal: HOLD USDT / CASH")
                            
                            st.session_state.current_suggestions = suggestions
                            save_session_state()
                            
                            # Display suggestions
                            if suggestions:
                                st.dataframe(pd.DataFrame(suggestions), use_container_width=True)
                        except Exception as e:
                            st.error(f"Error: {e}")
            else:
                st.info("⬅️ Load data and run optimization first")
    else:
        st.warning("⬅️ Select an account in the sidebar")


# TAB 5: Positions
with tab5:
    st.header("📋 Open Positions")
    
    if 'selected_account_id' in st.session_state:
        positions = get_positions(st.session_state.selected_account_id)
        
        if positions:
            pos_data = []
            for pos in positions:
                pos_data.append({
                    'Symbol': pos.symbol,
                    'Type': pos.position_type,
                    'Quantity': float(pos.quantity),
                    'Entry Price': f"${float(pos.entry_price):,.2f}",
                    'Current Price': f"${float(pos.current_price):,.2f}",
                    'Unrealized PnL': f"${float(pos.unrealized_pnl):,.2f}",
                    'PnL %': f"{float(pos.unrealized_pnl_percent):.2f}%",
                    'Stop Loss': f"${float(pos.stop_loss):,.2f}" if pos.stop_loss else "N/A",
                    'Take Profit': f"${float(pos.take_profit):,.2f}" if pos.take_profit else "N/A"
                })
            
            df_positions = pd.DataFrame(pos_data)
            st.dataframe(df_positions, use_container_width=True, hide_index=True)
        else:
            st.info("No open positions")
    else:
        st.warning("⬅️ Select an account in the sidebar")


# TAB 6: Trade History  
with tab6:
    st.header("📜 Trade History")
    
    if 'selected_account_id' in st.session_state:
        from db_utils import get_trades
        
        trades = get_trades(st.session_state.selected_account_id, limit=100)
        
        if trades:
            trades_data = []
            for trade in trades:
                trades_data.append({
                    'Time': trade.time.strftime('%Y-%m-%d %H:%M'),
                    'Symbol': trade.symbol,
                    'Type': trade.trade_type,
                    'Quantity': float(trade.quantity),
                    'Price': f"${float(trade.price):,.2f}",
                    'Fee': f"${float(trade.fee):,.2f}" if trade.fee else "N/A",
                    'PnL': f"${float(trade.realized_pnl):,.2f}" if trade.realized_pnl else "N/A",
                    'Strategy': trade.strategy_name or "Manual"
                })
            
            df_trades = pd.DataFrame(trades_data)
            st.dataframe(df_trades, use_container_width=True, hide_index=True)
        else:
            st.info("No trade history")
    else:
        st.warning("⬅️ Select an account in the sidebar")


# TAB 7: Notifications
with tab7:
    st.header("💬 Discord Notifications")
    
    webhook_url = st.text_input(
        'Discord Webhook URL (optional)',
        value=DISCORD_WEBHOOK_URL or '',
        type='password'
    )
    
    use_env = st.checkbox('Use .env DISCORD_WEBHOOK_URL', value=bool(DISCORD_WEBHOOK_URL))
    final_webhook = DISCORD_WEBHOOK_URL if use_env else webhook_url
    
    if 'current_suggestions' in st.session_state and final_webhook:
        if st.button('📤 Send Signal to Discord'):
            try:
                message = f"**Trading Signal**\n```json\n{json.dumps(st.session_state.current_suggestions, indent=2)}\n```"
                send_discord_notification(final_webhook, message)
                st.success('✅ Notification sent!')
            except Exception as e:
                st.error(f'Error: {e}')
    else:
        st.info("Generate a signal first, or provide webhook URL")


# TAB 8: Intelligence (RAG)
with tab8:
    st.header("🧠 FKS Intelligence - Trading Knowledge Base")
    st.caption("Ask questions about your trading history, strategies, and get AI-powered insights")
    
    # Initialize RAG service
    try:
        from services import get_rag_service
        rag_service = get_rag_service()
        rag_available = True
    except Exception as e:
        st.error(f"⚠️ RAG service unavailable: {e}")
        st.info("Make sure pgvector is enabled and RAG modules are installed")
        rag_available = False
    
    if rag_available:
        # Query interface
        st.subheader("💬 Ask FKS Intelligence")
        
        # Pre-defined questions
        example_questions = [
            "What strategy works best for BTCUSDT?",
            "Analyze my recent losing trades",
            "What are the best entry indicators for SOLUSDT?",
            "Compare RSI and MACD strategies",
            "What went wrong with my ETHUSDT trades?",
            "Predict trend for AVAXUSDT based on history",
        ]
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            query = st.text_area(
                "Your Question",
                height=100,
                placeholder="e.g., What strategy performs best in volatile markets?",
                key="intelligence_query"
            )
        
        with col2:
            st.write("**Quick Questions:**")
            for i, example in enumerate(example_questions):
                if st.button(example, key=f"example_{i}"):
                    st.session_state.intelligence_query = example
                    st.rerun()
        
        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                top_k = st.slider("Number of sources", 1, 20, 5, 
                                 help="How many relevant documents to retrieve")
            
            with col2:
                symbol_filter = st.selectbox(
                    "Filter by symbol",
                    ["All"] + SYMBOLS,
                    help="Limit results to specific trading pair"
                )
            
            with col3:
                doc_type_filter = st.multiselect(
                    "Document types",
                    ["trade_outcome", "backtest_result", "strategy_insight", "optimization_result"],
                    default=[],
                    help="Filter by document type"
                )
        
        # Query button
        if st.button("🔍 Ask", type="primary", use_container_width=True):
            if query:
                with st.spinner("🤔 Thinking..."):
                    try:
                        # Build filters
                        filters = {}
                        if symbol_filter != "All":
                            filters['symbol'] = symbol_filter
                        if doc_type_filter:
                            filters['doc_type'] = doc_type_filter
                        
                        # Query RAG
                        result = rag_service.query_with_rag(
                            query=query,
                            top_k=top_k,
                            filters=filters if filters else None,
                            include_sources=True
                        )
                        
                        # Display answer
                        st.success("✅ Answer generated!")
                        
                        # Answer box
                        st.markdown("### 📝 Answer")
                        st.markdown(result['answer'])
                        
                        # Metadata
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Sources Used", result['num_sources'])
                        with col2:
                            st.metric("Response Time", f"{result['response_time']:.2f}s")
                        with col3:
                            st.metric("Model", result['model'])
                        
                        # Show sources
                        if result.get('sources'):
                            with st.expander(f"📚 View {len(result['sources'])} Sources"):
                                for i, source in enumerate(result['sources'], 1):
                                    st.markdown(f"**Source {i}** (Relevance: {source.get('similarity_score', 0):.1%})")
                                    st.text(source.get('content', '')[:500] + "...")
                                    
                                    metadata = source.get('metadata', {})
                                    if metadata:
                                        st.caption(f"Symbol: {metadata.get('symbol', 'N/A')} | Type: {metadata.get('doc_type', 'N/A')}")
                                    st.markdown("---")
                        
                        # Save to session
                        if 'query_history' not in st.session_state:
                            st.session_state.query_history = []
                        st.session_state.query_history.append({
                            'query': query,
                            'answer': result['answer'],
                            'timestamp': datetime.now().isoformat()
                        })
                        
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                        st.exception(e)
            else:
                st.warning("Please enter a question")
        
        # Specialized queries
        st.markdown("---")
        st.subheader("🎯 Specialized Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Strategy Suggestions")
            strat_symbol = st.selectbox("Select symbol", SYMBOLS, key="strat_symbol")
            market_cond = st.selectbox(
                "Market condition",
                ["trending", "ranging", "volatile", "quiet"],
                key="market_cond"
            )
            
            if st.button("Get Strategy Suggestion", key="get_strategy"):
                with st.spinner("Analyzing..."):
                    try:
                        result = rag_service.suggest_strategy(
                            symbol=strat_symbol,
                            market_condition=market_cond
                        )
                        st.success("Strategy Recommendation:")
                        st.markdown(result['strategy'])
                        st.caption(f"Based on {result['sources_count']} historical documents")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        with col2:
            st.markdown("#### 🔮 Trend Prediction")
            pred_symbol = st.selectbox("Select symbol", SYMBOLS, key="pred_symbol")
            pred_timeframe = st.selectbox("Timeframe", TIMEFRAMES, key="pred_timeframe")
            lookback = st.slider("Lookback days", 7, 90, 30, key="pred_lookback")
            
            if st.button("Predict Trend", key="predict_trend"):
                with st.spinner("Predicting..."):
                    try:
                        result = rag_service.predict_trend(
                            symbol=pred_symbol,
                            timeframe=pred_timeframe,
                            lookback_days=lookback
                        )
                        st.success("Trend Prediction:")
                        st.markdown(result['prediction'])
                        st.metric("Confidence", f"{result['confidence']:.1%}")
                        st.caption(f"Based on {result['sources_count']} sources")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # Query history
        if 'query_history' in st.session_state and st.session_state.query_history:
            st.markdown("---")
            with st.expander(f"📜 Query History ({len(st.session_state.query_history)} queries)"):
                for i, item in enumerate(reversed(st.session_state.query_history[-10:]), 1):
                    st.markdown(f"**{i}. {item['query']}**")
                    st.caption(f"Time: {item['timestamp'][:19]}")
                    with st.expander("View answer"):
                        st.write(item['answer'])
                    st.markdown("---")
        
        # System stats
        st.markdown("---")
        st.subheader("📊 Intelligence System Stats")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📈 Get Analytics", key="get_analytics"):
                try:
                    analytics = rag_service.get_query_analytics(days=7)
                    st.json(analytics)
                except Exception as e:
                    st.error(f"Error: {e}")
        
        with col2:
            if st.button("🗄️ Database Stats", key="db_stats"):
                try:
                    from database import Session as DBSession, Document, DocumentChunk
                    session = DBSession()
                    doc_count = session.query(Document).filter(Document.is_deleted == False).count()
                    chunk_count = session.query(DocumentChunk).filter(DocumentChunk.is_deleted == False).count()
                    session.close()
                    
                    st.metric("Documents", doc_count)
                    st.metric("Chunks", chunk_count)
                except Exception as e:
                    st.error(f"Error: {e}")
        
        with col3:
            st.caption("**Model Info**")
            st.text(f"LLM: {'Local' if rag_service.use_local else 'OpenAI'}")
            st.text(f"Model: {rag_service.local_model if rag_service.use_local else rag_service.openai_model}")


# Footer
st.sidebar.markdown("---")
st.sidebar.caption(f"Session ID: {SESSION_ID[:8]}...")
st.sidebar.caption(f"Last updated: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")

# Auto-save session state periodically
save_session_state()
