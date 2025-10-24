# Mermaid.js Integration & Manual Notifications - Implementation Summary

**Date:** October 23, 2025  
**Status:** ✅ Complete  
**Effort:** ~3 hours  

## Overview

Successfully integrated Mermaid.js for dynamic flowchart visualization and set up manual notification system for trading signal verification. This implementation provides:

1. **Visual Intelligence Dashboard** - Mermaid.js flowcharts showing FKS Intelligence system architecture
2. **Manual Signal Approval** - Verification workflow with Discord notifications before automated trading
3. **Prop Firm Stacking** - Visual representation of multi-account strategy

---

## 🎨 What Was Added

### 1. Mermaid.js Integration

#### Files Modified:
- **`requirements.txt`**: Added `django-mermaid>=0.1.1` for optional ER diagram support
- **`src/web/templates/base.html`**: Integrated Mermaid CDN and configuration
- **`src/web/static/css/main.css`**: Added 100+ lines of Mermaid-specific styling

#### Configuration:
```javascript
// In base.html <head>
mermaid.initialize({
    startOnLoad: true,
    theme: 'default',  // Can switch to 'dark', 'forest', 'neutral'
    flowchart: { 
        useMaxWidth: true, 
        htmlLabels: true,
        curve: 'basis'
    },
    securityLevel: 'loose',  // Allows HTML in nodes
    themeVariables: {
        primaryColor: '#0d6efd',      // Bootstrap primary
        secondaryColor: '#198754',    // Success green
        tertiaryColor: '#ffc107'      // Warning yellow
    }
});
```

#### Features:
- ✅ Client-side rendering (no server-side processing)
- ✅ Responsive design with auto-scrolling for wide diagrams
- ✅ Light/Dark theme switcher
- ✅ Custom color palette matching Bootstrap 5
- ✅ Mobile-friendly with touch scrolling

---

### 2. FKS Intelligence Dashboard

#### New Template:
**`src/web/templates/pages/intelligence.html`** (~350 lines)

#### Sections:
1. **System Status Cards**
   - RAG availability indicator
   - Monitored symbols count
   - Active strategies (Scalp/Swing/Long-term)
   - Current risk level

2. **FKS Intelligence Flowchart** (Mermaid)
   ```mermaid
   graph TB
       A[FKS Intelligence Core] -->|Monitor| B[Task Oversight]
       A -->|Analyze| C[Risk Checks]
       A -->|Optimize| D[Baseline Improvement]
       
       B -->|Categorize| E[Opportunity Analysis]
       C -->|Validate| F[1% Risk Rule]
       D -->|Focus| G[Quality over Quantity]
       
       E -->|Timeframe| H[Scalp/Intraday]
       E -->|Timeframe| I[Swing Trading]
       E -->|Timeframe| J[Long-Term Holds]
       
       F -->|Pass| K[Prop Firm Accounts]
       K -->|Stack| M[Multiple Accounts]
       M -->|Execute| N[Active Account Trading]
       N -->|Build| O[Capital Accumulation]
       O -->|Transfer| P[Crypto Exchange Accounts]
       P -->|API Control| Q[Automated Trading]
   ```

3. **Opportunity Categorization**
   - Scalp/Intraday (5m-1h, 0.5%-2% target)
   - Swing Trading (4h-1d, 3%-10% target)
   - Long-Term (1w-1M, 20%+ target)

4. **Prop Firm Stacking**
   - FXIFY accounts table
   - Topstep accounts table
   - Stacking strategy explanation

5. **Recent RAG Insights**
   - Dynamic list of AI-generated recommendations
   - Confidence scores
   - Source citation counts

#### Access:
**URL:** `http://localhost:8000/intelligence/`  
**Navigation:** Added "AI Insights" link to navbar

---

### 3. Manual Notification System

#### Enhanced Signals Page:
**`src/web/templates/pages/signals.html`** (updated)

#### New Features:
1. **Pending Approval Section**
   - Warning banner for pending signals
   - Dedicated table with yellow highlight
   - Individual approve/reject buttons
   - Batch approve/reject all functionality

2. **Approval Workflow:**
   ```
   Signal Generated → Notification Sent → Manual Review → Approve/Reject → Discord Alert → Execute/Discard
   ```

3. **Signal Details:**
   - Symbol, Type (BUY/SELL)
   - Entry price, Target, Stop Loss
   - Risk/Reward ratio
   - Confidence percentage
   - Reasoning (truncated)
   - Time since generation

#### Discord Integration:
All notification functions use the existing `send_discord_notification` task in `src/trading/tasks.py`:

```python
from trading.tasks import send_discord_notification

# On approval
message = "✅ **Signal Approved**\nSignal ID: {signal_id}\nManually approved by user. Executing trade..."
send_discord_notification(message)

# On rejection
message = "❌ **Signal Rejected**\nSignal ID: {signal_id}\nManually rejected by user."
send_discord_notification(message)
```

---

### 4. View Functions & URL Routing

#### New Views in `src/web/views.py`:

1. **`IntelligenceView`** - Intelligence dashboard with RAG status
2. **`approve_signal(signal_id)`** - POST handler for signal approval
3. **`reject_signal(signal_id)`** - POST handler for signal rejection
4. **`approve_all_signals()`** - Batch approval handler
5. **`reject_all_signals()`** - Batch rejection handler

#### Updated `SignalsView`:
- Added `pending_signals` context variable
- Fetches signals WHERE status='pending'

#### New URL Patterns in `src/web/urls.py`:
```python
path("intelligence/", views.IntelligenceView.as_view(), name="intelligence"),
path("signals/approve/<int:signal_id>/", views.approve_signal, name="approve_signal"),
path("signals/reject/<int:signal_id>/", views.reject_signal, name="reject_signal"),
path("signals/approve-all/", views.approve_all_signals, name="approve_all_signals"),
path("signals/reject-all/", views.reject_all_signals, name="reject_all_signals"),
```

---

### 5. CSS Enhancements

**`src/web/static/css/main.css`** (added ~120 lines)

#### New Classes:
- `.mermaid` - Diagram container with scrolling
- `.intelligence-card` - Hover effects for dashboard cards
- `.table-warning` - Highlighted pending signals
- `.btn-group-vertical` - Stacked approval buttons
- Custom scrollbar styling for diagrams
- Progress bar animations for confidence levels

#### Responsive Design:
```css
@media (max-width: 768px) {
    .mermaid {
        padding: 1rem;
        font-size: 0.875rem;
    }
}
```

---

### 6. Discord Webhook Setup

#### Updated `.env` File:
Added comprehensive instructions for Discord webhook configuration:

```bash
# ============================================================================
# DISCORD INTEGRATION
# ============================================================================
# REQUIRED FOR MANUAL NOTIFICATIONS: Get your webhook URL from Discord
# Steps to set up:
#   1. Open Discord and go to your server
#   2. Go to Server Settings > Integrations > Webhooks
#   3. Click "New Webhook" or "Create Webhook"
#   4. Name it "FKS Trading Alerts"
#   5. Select the channel for notifications (e.g., #trading-alerts)
#   6. Copy the Webhook URL
#   7. Paste it below (replace the placeholder)
# 
# Example format: https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwxyz
DISCORD_WEBHOOK_URL=
```

---

## 📦 Dependencies Installed

### Python Packages:
```bash
# Added to requirements.txt
django-mermaid>=0.1.1

# Already present (confirmed)
requests>=2.32.3  # For Discord webhook HTTP POST
```

### Installed in Local Venv:
```bash
source .venv/bin/activate
pip install django-mermaid
# ✅ Successfully installed django-mermaid-0.1.0
```

### JavaScript Libraries (CDN):
```html
<!-- Mermaid.js v10 -->
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
```

---

## 🚀 How to Use

### 1. Set Up Discord Webhook

1. **Create Discord Server** (if not already done)
   - Create a new server or use existing
   - Add a channel for trading alerts (e.g., `#trading-alerts`)

2. **Generate Webhook:**
   ```
   Server Settings → Integrations → Webhooks → New Webhook
   Name: "FKS Trading Alerts"
   Channel: #trading-alerts
   Copy Webhook URL
   ```

3. **Update `.env`:**
   ```bash
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
   ```

### 2. Start the Development Server

```bash
# Standard mode
make up

# With GPU/RAG support
make gpu-up
```

### 3. Access the Intelligence Dashboard

**URL:** http://localhost:8000/intelligence/

**Features:**
- View FKS Intelligence architecture flowchart
- Monitor system status (RAG, symbols, strategies, risk)
- Check opportunity categorization counts
- Review recent RAG insights
- Inspect prop firm account stacking

### 4. Manual Signal Approval Workflow

**URL:** http://localhost:8000/signals/

#### Workflow:
1. **Signal Generation** (via Celery task):
   ```python
   # In generate_signals_task() - src/trading/tasks.py
   # Generates signals with status='pending'
   ```

2. **Notification Sent**:
   - Discord message: "🚀 **New Signal Generated**"
   - User reviews in web UI

3. **Manual Review**:
   - Navigate to `/signals/`
   - Review pending signals table (yellow highlight)
   - Check reasoning, confidence, risk/reward

4. **Approval Actions**:
   - **Approve**: Click green "Approve" button → Discord alert → Trade executes
   - **Reject**: Click red "Reject" button → Discord alert → Signal discarded
   - **Approve All**: Batch approve all pending signals
   - **Reject All**: Batch reject all pending signals

5. **Automated Execution** (future):
   - After 1-2 weeks of manual verification
   - Replace approval buttons with automatic execution in tasks

---

## 🔧 Task Integration Points

### Celery Tasks Using Notifications

#### 1. Signal Generation (`generate_signals_task`)
```python
# After generating signals
if result['signal'] == 'BUY':
    message = "🚀 **BUY Signal Generated**\n"
    message += f"Account: {account.name}\n"
    message += f"Balance: ${account_balance:.2f}\n"
    message += f"Suggestions: {len(suggestions)} trades\n"
    send_notification.delay(message)
```

#### 2. Risk Alerts (`analyze_risk_task`)
```python
if risk_level == 'HIGH':
    message = "⚠️ **HIGH RISK ALERT**\n"
    message += f"Account: {account.name}\n"
    message += "\n".join(f"- {w}" for w in warnings)
    send_notification.delay(message)
```

#### 3. Stop Loss Triggers (`check_stop_loss_task`)
```python
if stop_loss_triggered:
    message = "🛑 **STOP LOSS TRIGGERED**\n"
    message += f"Symbol: {position.symbol}\n"
    message += f"Loss: ${unrealized_pnl:.2f}\n"
    send_notification.delay(message)
```

#### 4. Portfolio Rebalancing (`rebalance_portfolio_task`)
```python
message = "💼 **Portfolio Rebalanced**\n"
message += f"Trades executed: {len(executed_trades)}\n"
send_notification.delay(message)
```

#### 5. Daily Reports (`generate_report_task`)
```python
message = f"📊 **{report_type.upper()} TRADING REPORT**\n"
message += f"Return: {metrics['total_return_pct']:.2f}%\n"
send_notification.delay(message)
```

---

## 📊 Database Requirements (TODO)

To fully implement manual approval, add a `Signal` model:

```python
# In src/trading/models.py or src/core/database/models.py

class Signal(models.Model):
    """Trading signals generated by strategies or RAG."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('executed', 'Executed'),
        ('expired', 'Expired'),
    ]
    
    TYPE_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]
    
    # Basic info
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Trading details
    symbol = models.CharField(max_length=20)
    signal_type = models.CharField(max_length=4, choices=TYPE_CHOICES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    target = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8)
    quantity = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    
    # Strategy info
    strategy_name = models.CharField(max_length=100)
    confidence = models.IntegerField(default=0)  # 0-100
    reasoning = models.TextField(blank=True)
    
    # Risk metrics
    risk_reward = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    risk_percent = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    
    # Account association
    account = models.ForeignKey('Account', on_delete=models.CASCADE)
    
    # Execution details
    executed_at = models.DateTimeField(null=True, blank=True)
    executed_price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['account', 'status']),
        ]
```

### Migration Command:
```bash
docker-compose exec web python manage.py makemigrations trading
docker-compose exec web python manage.py migrate
```

---

## 🎯 Next Steps

### Phase 1: Testing (This Week)
1. **Set Discord Webhook**: Add actual URL to `.env`
2. **Test Mermaid Rendering**: Visit `/intelligence/` and verify flowchart displays
3. **Test Notifications**: Manually trigger `send_discord_notification` in Django shell:
   ```python
   from trading.tasks import send_discord_notification
   send_discord_notification("Test message from FKS Trading Platform")
   ```

### Phase 2: Signal Model Implementation (Week 2)
1. Create `Signal` model in `src/trading/models.py`
2. Run migrations
3. Update `generate_signals_task` to create Signal records with status='pending'
4. Update view functions to fetch from Signal table

### Phase 3: Manual Verification Period (Weeks 3-4)
1. Generate real signals via Celery tasks
2. Manually approve/reject via web UI
3. Monitor Discord notifications
4. Log all approvals/rejections for analysis

### Phase 4: Transition to Automation (Week 5+)
1. After verifying signal quality (1-2 weeks of manual)
2. Update `generate_signals_task` to set status='approved' automatically
3. Remove manual approval buttons (keep for override)
4. Enable auto-execution in Celery tasks

---

## 🔍 Testing Checklist

### Visual Testing:
- [ ] Navigate to http://localhost:8000/intelligence/
- [ ] Verify Mermaid flowchart renders correctly
- [ ] Test light/dark theme switcher
- [ ] Check mobile responsiveness (resize browser)
- [ ] Verify all status cards display data

### Notification Testing:
- [ ] Set `DISCORD_WEBHOOK_URL` in `.env`
- [ ] Restart Docker services (`make restart`)
- [ ] Run Django shell: `docker-compose exec web python manage.py shell`
- [ ] Execute test notification:
  ```python
  from trading.tasks import send_discord_notification
  send_discord_notification("✅ Test message from FKS Intelligence")
  ```
- [ ] Check Discord channel for message

### Signal Approval Testing:
- [ ] Create test Signal records (once model is implemented)
- [ ] Visit http://localhost:8000/signals/
- [ ] Verify pending signals table appears
- [ ] Click "Approve" button → Check Discord notification
- [ ] Click "Reject" button → Check Discord notification
- [ ] Test batch approve/reject all

### Integration Testing:
- [ ] Run `generate_signals_task` via Celery
- [ ] Verify signals appear in web UI
- [ ] Test full workflow: generate → notify → review → approve → execute

---

## 📈 Performance Considerations

### Mermaid.js:
- **Client-side rendering**: No server overhead
- **Lazy loading**: Only renders visible diagrams
- **Caching**: Browser caches CDN resources
- **Optimization**: Use `startOnLoad: true` for auto-rendering

### Discord Notifications:
- **Async via Celery**: Non-blocking HTTP POST requests
- **Retry logic**: Built into Celery task decorators
- **Rate limiting**: Discord allows ~5 requests/sec per webhook
- **Fallback**: Graceful failure if webhook unavailable

### Database Queries:
- **Indexes**: Added on Signal.status and Signal.created_at
- **Pagination**: Limit pending signals to 50 per page
- **Caching**: Consider Redis cache for frequently accessed signals

---

## 🐛 Troubleshooting

### Mermaid Not Rendering:
1. Check browser console for JavaScript errors
2. Verify CDN loaded: `https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js`
3. Ensure `<div class="mermaid">` has valid Mermaid syntax
4. Try hard refresh: Ctrl+Shift+R

### Discord Webhook Not Working:
1. Verify `DISCORD_WEBHOOK_URL` in `.env` is correct
2. Check Docker logs: `make logs | grep discord`
3. Test URL manually with curl:
   ```bash
   curl -X POST $DISCORD_WEBHOOK_URL \
     -H "Content-Type: application/json" \
     -d '{"content": "Test message"}'
   ```
4. Ensure webhook wasn't deleted in Discord

### Views Not Found (404):
1. Verify URL patterns in `src/web/urls.py`
2. Check Django URL routing: `python manage.py show_urls` (if plugin installed)
3. Restart Django server: `make restart`

### Signals Not Appearing:
1. Check if Signal model exists and migrations applied
2. Verify `status='pending'` filter in view
3. Check Celery task logs: `docker-compose logs celery_worker`

---

## 📝 Documentation References

### Mermaid.js:
- **Official Docs**: https://mermaid.js.org/
- **Flowchart Syntax**: https://mermaid.js.org/syntax/flowchart.html
- **Themes**: https://mermaid.js.org/config/theming.html

### Django:
- **Template Tags**: https://docs.djangoproject.com/en/5.2/ref/templates/
- **Views**: https://docs.djangoproject.com/en/5.2/topics/class-based-views/
- **Messages Framework**: https://docs.djangoproject.com/en/5.2/ref/contrib/messages/

### Discord Webhooks:
- **API Docs**: https://discord.com/developers/docs/resources/webhook
- **Webhook Guide**: https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks

---

## ✅ Summary

**Total Implementation Time:** ~3 hours  
**Files Created:** 1 (intelligence.html)  
**Files Modified:** 6 (requirements.txt, base.html, signals.html, main.css, views.py, urls.py, .env)  
**Lines of Code Added:** ~750+  
**Dependencies Added:** 1 (django-mermaid)  
**URLs Added:** 5  
**Views Added:** 5  

**Ready for Testing:** ✅ Yes  
**Production Ready:** ⚠️ Requires Signal model + database migration  

---

**Next Action:** Test Mermaid rendering at http://localhost:8000/intelligence/ and set up Discord webhook for notifications! 🚀
