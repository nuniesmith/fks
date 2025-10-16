# FKS Trading Django App

This is a complete Django conversion of your Streamlit fks trading application, integrated with AI features from portfolio-ai including forecasting, chatbot, and RAG (Retrieval-Augmented Generation) for document querying.

## 🚀 Features

### Trading Features (Migrated from Streamlit)
- **Real-time Data Fetching**: Pull OHLCV data from Binance and other exchanges
- **Signal Generation**: RSI, MACD, Bollinger Bands, ATR-based trading signals
- **Backtesting Engine**: Test strategies with historical data, calculate metrics (Sharpe, Drawdown, Win Rate)
- **Strategy Optimization**: Optuna-based hyperparameter tuning
- **Position Management**: Track open positions, calculate P&L
- **Trade Logging**: Store all trades in PostgreSQL with TimescaleDB
- **Discord Notifications**: Send trade alerts to Discord
- **ML-Enhanced Trading**: HMM regime detection, LSTM price prediction

### AI Features (from portfolio-ai)
- **AI Forecasting**: AutoTS and XGBoost-based price forecasting
- **Chatbot**: OpenAI/Gemini-powered assistant for trading guidance
- **RAG Document Query**: Upload trade reports/PDFs and query with FAISS vector search
- **Daily Trading Plans**: ML-generated recommendations for positions and opportunities

## 📁 Project Structure

```
fks_django/
├── manage.py
├── fks_project/
│   ├── settings.py          # Django settings with AI API configs
│   ├── urls.py               # Main URL routing
│   ├── wsgi.py
│   └── asgi.py
├── trading/                  # Main trading app
│   ├── models.py            # Account, Position, Trade, Signal, BacktestResult
│   ├── views.py             # Dashboard, signals, backtest, positions
│   ├── admin.py             # Django admin configuration
│   ├── forms.py             # Strategy forms
│   ├── api_urls.py          # REST API endpoints
│   ├── tasks.py             # Celery tasks for async processing
│   ├── utils/
│   │   ├── data_fetcher.py  # Binance API integration
│   │   ├── signal_generator.py  # RSI, MACD, signals
│   │   ├── backtest_engine.py   # Backtesting logic
│   │   ├── ml_models.py     # HMM, LSTM models
│   │   └── optimizer.py     # Optuna optimization
│   └── templates/trading/
│       ├── dashboard.html    # Main dashboard
│       ├── signals.html      # Current signals
│       ├── backtest.html     # Backtest results
│       ├── positions.html    # Open positions
│       └── trades.html       # Trade history
├── forecasting/              # AI Forecasting app
│   ├── models.py            # Forecast results
│   ├── views.py             # Forecasting interface
│   ├── forecast_engine.py   # AutoTS/XGBoost logic
│   └── templates/forecasting/
│       └── forecast.html
├── chatbot/                  # AI Chatbot app
│   ├── views.py             # Chat interface
│   ├── chatbot_engine.py    # OpenAI/Gemini integration
│   └── templates/chatbot/
│       └── chat.html
├── rag/                      # Document RAG app
│   ├── models.py            # Document uploads
│   ├── views.py             # RAG interface
│   ├── rag_engine.py        # FAISS vector store
│   └── templates/rag/
│       ├── upload.html
│       └── query.html
├── templates/                # Global templates
│   ├── base.html            # Base template with navbar
│   └── home.html            # Landing page
├── static/                   # CSS, JS, images
│   ├── css/
│   │   └── styles.css
│   └── js/
│       └── charts.js        # Chart.js for visualizations
├── media/                    # User uploads
├── ml_models/                # Saved ML models
└── logs/                     # Application logs
```

## 🛠️ Installation

### Prerequisites
- Python 3.10+
- PostgreSQL 13+ with TimescaleDB extension
- Redis 6+
- Docker & Docker Compose (optional)
- CUDA-capable GPU (optional, for ML acceleration)

### Option 1: Docker Setup (Recommended)

1. **Clone and navigate:**
   ```bash
   cd fks_django
   ```

2. **Create `.env` file:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Build and start services:**
   ```bash
   docker-compose up --build -d
   ```

4. **Run migrations:**
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   ```

5. **Collect static files:**
   ```bash
   docker-compose exec web python manage.py collectstatic --noinput
   ```

6. **Access the app:**
   - Main app: http://localhost:8000
   - Admin panel: http://localhost:8000/admin

### Option 2: Local Setup

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL:**
   ```sql
   CREATE DATABASE trading_db;
   CREATE EXTENSION IF NOT EXISTS timescaledb;
   ```

4. **Configure environment:**
   ```bash
   export POSTGRES_HOST=localhost
   export POSTGRES_USER=your_user
   export POSTGRES_PASSWORD=your_password
   export OPENAI_API_KEY=your_openai_key
   export GEMINI_API_KEY=your_gemini_key
   export BINANCE_API_KEY=your_binance_key
   export BINANCE_API_SECRET=your_binance_secret
   ```

5. **Run migrations:**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Start Redis:**
   ```bash
   redis-server
   ```

7. **Start Celery (in separate terminals):**
   ```bash
   celery -A fks_project worker -l info
   celery -A fks_project beat -l info
   ```

8. **Run development server:**
   ```bash
   python manage.py runserver
   ```

## 🔑 Required Environment Variables

Create a `.env` file with:

```env
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
POSTGRES_DB=trading_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/0

# Trading APIs
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret

# AI APIs
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key

# Notifications
DISCORD_WEBHOOK_URL=your_discord_webhook_url

# CORS (for frontend)
CORS_ORIGINS=http://localhost:3000
```

## 📊 Usage Guide

### 1. Dashboard
Navigate to `/trading/` to see:
- Portfolio overview
- Recent signals
- Open positions
- Performance charts

### 2. Signal Generation
Go to `/trading/signals/` to:
- View current buy/sell signals for multiple symbols
- See RSI, MACD, Bollinger Band indicators
- Get recommended entry/exit prices with stop-loss/take-profit levels

### 3. Backtesting
Visit `/trading/backtest/` to:
- Select symbols and date ranges
- Configure strategy parameters (M, threshold, stop-loss, take-profit)
- Run backtests and view results (Sharpe ratio, max drawdown, win rate)
- Visualize equity curves

### 4. Strategy Optimization
At `/trading/optimize/`:
- Use Optuna to find optimal parameters
- Set optimization goals (maximize Sharpe, minimize drawdown)
- Run multiple trials and save best configurations

### 5. AI Forecasting
Go to `/forecasting/` to:
- Upload CSV files or use existing fks data
- Select target column (e.g., close price)
- Choose forecast horizon (days/weeks)
- Generate predictions with AutoTS or XGBoost
- Download forecast results

### 6. AI Chatbot
Visit `/chatbot/` to:
- Ask questions about trading strategies
- Get explanations of indicators (RSI, MACD, etc.)
- Request position recommendations
- Chat powered by OpenAI GPT-4 or Gemini

### 7. RAG Document Query
At `/rag/`:
- Upload trade reports, PDFs, or market analysis documents
- Query documents with natural language
- Get AI-powered answers with source references
- Uses FAISS vector search + LangChain

## 🤖 AI Features Deep Dive

### Forecasting Engine
- **Models**: AutoTS (ensemble), XGBoost (gradient boosting)
- **Input**: Historical OHLCV data
- **Output**: Price predictions with confidence intervals
- **Use Case**: Predict next 7-30 days of fks prices

**Example:**
```python
from forecasting.forecast_engine import CryptoForecaster

forecaster = CryptoForecaster()
forecast = forecaster.predict(
    data=df_btc,
    target_column='close',
    horizon=30,
    frequency='D'
)
```

### Chatbot
- **Models**: OpenAI GPT-4, Google Gemini Pro
- **Features**:
  - Contextual responses about your portfolio
  - Technical indicator explanations
  - Market sentiment analysis
  - Strategy recommendations

**Example conversation:**
```
User: "Should I buy BTC now based on RSI?"
Bot: "BTC's RSI is currently at 32, indicating oversold conditions.
     Combined with bullish MACD crossover, this suggests a potential
     entry point. Consider setting stop-loss at $42,000."
```

### RAG Document Query
- **Embedding Model**: SentenceTransformers (all-MiniLM-L6-v2)
- **Vector Store**: FAISS
- **LLM**: OpenAI GPT-3.5-turbo
- **Supported Files**: PDF, CSV, TXT, DOCX

**Example:**
```
Upload: "Q1_2024_Trading_Report.pdf"
Query: "What was the best performing strategy in January?"
Answer: "Based on the report, the momentum strategy with M=20
         achieved a 15.3% return in January, outperforming
         mean reversion strategies."
```

## 🔄 Migration from Streamlit

Key differences and improvements:

### Database
- **Before**: SQLAlchemy with direct session management
- **After**: Django ORM with migrations, automatic admin interface

### UI
- **Before**: Streamlit widgets and session state
- **After**: Django templates with Bootstrap, Chart.js for interactive charts

### API
- **Before**: No API
- **After**: Django REST Framework API for mobile/external integrations

### Background Tasks
- **Before**: Inline execution
- **After**: Celery for async data fetching, signal generation, and backtesting

### Caching
- **Before**: Redis with manual cache management
- **After**: Django's cache framework with automatic invalidation

### Deployment
- **Before**: `streamlit run app.py`
- **After**: Production-ready with Gunicorn, Nginx, Docker

## 🧪 Testing

Run the comprehensive test suite:

```bash
# All tests
python manage.py test

# Specific app
python manage.py test trading

# With coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Open htmlcov/index.html
```

## 📈 Performance Optimization

### Database
- TimescaleDB for time-series data (hypertables on `trades`, `balance_history`)
- Database indexes on commonly queried fields
- Connection pooling with pgBouncer

### Caching
- Redis for session storage, signal caching
- Cache backtest results for 1 hour
- Cache exchange data for 5 minutes

### ML Models
- Pre-trained models loaded at startup
- CUDA acceleration for LSTM/HMM if GPU available
- Model inference caching

### Celery Tasks
- Async data fetching from exchanges
- Background backtest execution
- Scheduled signal generation every 5 minutes

## 🔐 Security

- HTTPS only in production (configure Nginx)
- API keys stored in environment variables, never in code
- CSRF protection enabled
- Rate limiting on API endpoints
- File upload validation (max 10MB, whitelist extensions)
- SQL injection protection via Django ORM

## 📡 API Endpoints

```
GET  /api/signals/?symbol=BTC/USD
GET  /api/positions/
POST /api/trades/
GET  /api/backtest-results/?strategy=momentum
POST /api/forecast/
POST /api/chatbot/message/
```

See `/api/docs/` for full API documentation (install `drf-spectacular`).

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open pull request

## 📝 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- Original Streamlit app: Your fks trading tool
- AI Features inspired by: [portfolio-ai](https://pypi.org/project/portfolio-ai/)
- ML Models: PyTorch, hmmlearn, scikit-learn
- Forecasting: AutoTS, XGBoost
- RAG: LangChain, FAISS, SentenceTransformers

## 📧 Support

For issues, questions, or feature requests:
- Open a GitHub issue
- Email: your-email@example.com
- Discord: Join our trading community

## 🗺️ Roadmap

- [ ] React frontend for better UX
- [ ] Mobile app (React Native)
- [ ] More exchange integrations (Coinbase Pro, FTX)
- [ ] Advanced ML models (Transformers for time-series)
- [ ] Social trading features (copy trading)
- [ ] Automated trading execution
- [ ] Real-time WebSocket updates
- [ ] Multi-user support with team collaboration
