# Mermaid.js & Manual Notifications - Quick Start Guide

## 🚀 Quick Setup (5 minutes)

### 1. Set Discord Webhook
```bash
# Edit .env file
nano .env

# Add your webhook URL (replace with actual URL)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

### 2. Start Services
```bash
# Standard mode
make up

# With GPU/RAG support
make gpu-up
```

### 3. Test Pages
- **Intelligence Dashboard**: http://localhost:8000/intelligence/
- **Signals with Manual Approval**: http://localhost:8000/signals/

---

## 🎨 What You'll See

### Intelligence Dashboard (`/intelligence/`)
✅ **System Status Cards**
- RAG Status (Active/Offline)
- Monitored Symbols count (12)
- Active Strategies (Scalp/Swing/Long-term)
- Current Risk Level (LOW/MEDIUM/HIGH)

✅ **FKS Intelligence Flowchart** (Interactive Mermaid diagram)
- Central Intelligence Core
- Risk Checks & 1% Rule
- Opportunity Categorization
- Prop Firm Account Stacking
- Crypto Exchange Integration

✅ **Opportunity Categories**
- Scalp/Intraday: 5m-1h timeframe, 0.5%-2% target
- Swing Trading: 4h-1d timeframe, 3%-10% target
- Long-Term: 1w-1M timeframe, 20%+ target

✅ **Prop Firm Stacking**
- FXIFY accounts table
- Topstep accounts table
- Active/Pending status indicators

### Signals Page (`/signals/`)
✅ **Pending Approval Section** (yellow highlight)
- List of signals awaiting review
- Approve/Reject buttons per signal
- Batch approve/reject all buttons
- Risk/Reward ratios
- Confidence percentages

✅ **Active Signals Table**
- Currently executing trades
- Real-time status updates
- Performance metrics

---

## 📱 Discord Webhook Setup

### Step-by-Step:
1. **Open Discord** → Go to your server
2. **Server Settings** → Integrations → Webhooks
3. **Create Webhook**:
   - Name: `FKS Trading Alerts`
   - Channel: `#trading-alerts` (or create new)
   - Copy URL
4. **Paste in `.env`**:
   ```bash
   DISCORD_WEBHOOK_URL=<paste_url_here>
   ```
5. **Restart services**: `make restart`

### Test Notification:
```bash
# Open Django shell
docker-compose exec web python manage.py shell

# Run test
from trading.tasks import send_discord_notification
send_discord_notification("✅ FKS Platform is online!")
```

---

## 🧪 Manual Approval Workflow

### Current Flow (Manual):
```
Signal Generated → Discord Alert → Web UI Review → Approve/Reject → Execute/Discard
```

### Example Notifications:
- **New Signal**: "🚀 **BUY Signal Generated** BTCUSDT @ $67,450"
- **Approved**: "✅ **Signal Approved** Signal #123 - Executing trade..."
- **Rejected**: "❌ **Signal Rejected** Signal #123 - User rejected"
- **Risk Alert**: "⚠️ **HIGH RISK ALERT** Portfolio exposure 85%"
- **Stop Loss**: "🛑 **STOP LOSS TRIGGERED** ETHUSDT - Loss: $-150"

### Testing (Once Signal Model Exists):
1. Generate signals via Celery: `generate_signals_task()`
2. Check `/signals/` for pending signals
3. Click "Approve" → Verify Discord notification
4. Click "Reject" → Verify Discord notification

---

## 🎯 Future Automation (After 1-2 Weeks)

### Transition Plan:
1. **Week 1-2**: Manual approval for all signals
2. **Week 3**: Auto-approve high-confidence signals (>80%)
3. **Week 4**: Full automation, manual override available

### Code Changes Required:
```python
# In generate_signals_task() - after manual verification period
if signal.confidence >= 0.8 and verified_performance_good:
    signal.status = 'approved'  # Auto-approve
    execute_trade(signal)       # Immediate execution
else:
    signal.status = 'pending'   # Still needs manual review
    send_notification.delay("⚠️ Low confidence signal - review required")
```

---

## 📋 Key Files Reference

### Templates:
- `src/web/templates/pages/intelligence.html` - Intelligence dashboard
- `src/web/templates/pages/signals.html` - Signals with approval
- `src/web/templates/base.html` - Mermaid CDN integration

### Views:
- `src/web/views.py` - IntelligenceView, approve/reject handlers

### URLs:
- `src/web/urls.py` - Route definitions

### Styles:
- `src/web/static/css/main.css` - Mermaid + approval styling

### Tasks:
- `src/trading/tasks.py` - send_discord_notification, generate_signals_task

### Config:
- `.env` - DISCORD_WEBHOOK_URL configuration

---

## 🐛 Common Issues

### Mermaid Not Showing:
```bash
# Check browser console (F12)
# Verify CDN loaded:
# https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js
```

### Discord Not Working:
```bash
# Test webhook directly
curl -X POST $DISCORD_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"content": "Test from curl"}'
```

### Views Not Found:
```bash
# Restart Django
make restart

# Check logs
make logs | grep -i error
```

---

## 📚 Documentation

- **Full Implementation Guide**: `docs/MERMAID_NOTIFICATION_IMPLEMENTATION.md`
- **Architecture Overview**: `docs/ARCHITECTURE.md`
- **Celery Tasks**: `docs/CELERY_TASKS.md`
- **Project Copilot Instructions**: `.github/copilot-instructions.md`

---

## ✅ Quick Verification Checklist

- [ ] Set `DISCORD_WEBHOOK_URL` in `.env`
- [ ] Restart services: `make restart`
- [ ] Visit http://localhost:8000/intelligence/
- [ ] Verify Mermaid flowchart renders
- [ ] Test Discord notification from shell
- [ ] Visit http://localhost:8000/signals/
- [ ] Check pending signals section exists

---

**Ready to Go?** Visit http://localhost:8000/intelligence/ and start exploring! 🎉
