# CNS (Centralized Notification System) Documentation

The Centralized Notification System (CNS) provides unified notification and alerting capabilities for the FKS platform.

## Overview

CNS is a microservice that handles all outbound notifications from the platform, supporting multiple channels and providing:
- Multi-channel notification delivery (Slack, email, webhooks)
- Priority-based routing and throttling
- Template-based message formatting
- Delivery tracking and retry logic
- Rate limiting to prevent notification spam

## Documentation

### [Architecture](CNS_ARCHITECTURE.md)
Complete architectural overview of the CNS service.

**Topics:**
- System design and components
- Integration patterns
- Message flow
- Channel abstractions
- Scalability considerations

### [Deployment Guide](CNS_DEPLOYMENT.md)
Step-by-step deployment instructions.

**Covers:**
- Prerequisites and dependencies
- Configuration requirements
- Docker deployment
- Kubernetes deployment
- Environment variables
- Secrets management

### [Quick Start](CNS_QUICKSTART.md)
Get up and running with CNS quickly.

**Includes:**
- Minimal configuration
- Running locally
- Sending test notifications
- Verifying delivery
- Basic troubleshooting

### [Integration Checklist](CNS_INTEGRATION_CHECKLIST.md)
Checklist for integrating CNS into your service.

**Steps:**
- Client library setup
- Configuration
- Authentication
- Testing
- Production readiness

### [Summary](CNS_SUMMARY.md)
High-level summary of CNS capabilities and status.

### [Integration Progress](CNS_INTEGRATION_PROGRESS.md)
Current integration status across FKS services.

## Key Features

### Multi-Channel Support
- **Slack**: Rich message formatting, threading, reactions
- **Email**: HTML and plain text, attachments
- **Webhooks**: Custom HTTP endpoints, configurable payloads
- **SMS**: (Planned) Text message notifications

### Priority Levels
- **Critical**: Immediate delivery, no throttling
- **High**: Expedited delivery, minimal throttling
- **Normal**: Standard delivery, standard throttling
- **Low**: Bulk delivery, aggressive throttling

### Message Templates
Pre-defined templates for common scenarios:
- Alert notifications
- System status updates
- Trade confirmations
- Error reports
- Daily summaries

### Rate Limiting
Prevents notification fatigue:
- Per-channel rate limits
- Per-priority rate limits
- Adaptive throttling
- Burst allowances

### Delivery Guarantees
- At-least-once delivery semantics
- Automatic retries with exponential backoff
- Dead letter queue for failed messages
- Delivery status tracking

## Architecture

```
┌─────────────┐
│   Service   │
│  (Client)   │
└──────┬──────┘
       │
       │ gRPC/REST
       ▼
┌─────────────┐
│     CNS     │
│   Router    │
└──────┬──────┘
       │
       ├─────────┬─────────┬─────────┐
       │         │         │         │
       ▼         ▼         ▼         ▼
   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
   │Slack │ │Email │ │Webhook│ │ SMS  │
   │Channel│ │Channel│ │Channel│ │Channel
   └──────┘ └──────┘ └──────┘ └──────┘
```

## Configuration

### Environment Variables

```bash
# Slack Configuration
CNS_SLACK_WEBHOOK_URL=https://hooks.slack.com/...
CNS_SLACK_CHANNEL_DEFAULT=#alerts
CNS_SLACK_RATE_LIMIT=10  # messages per minute

# Email Configuration
CNS_EMAIL_SMTP_HOST=smtp.gmail.com
CNS_EMAIL_SMTP_PORT=587
CNS_EMAIL_FROM=noreply@fks.example.com
CNS_EMAIL_RATE_LIMIT=5  # emails per minute

# Webhook Configuration
CNS_WEBHOOK_TIMEOUT=30s
CNS_WEBHOOK_RETRIES=3

# General Settings
CNS_LOG_LEVEL=info
CNS_METRICS_PORT=9091
```

### Slack Setup

1. Create a Slack app at https://api.slack.com/apps
2. Enable Incoming Webhooks
3. Add webhook to workspace
4. Copy webhook URL to `CNS_SLACK_WEBHOOK_URL`

### Email Setup

1. Configure SMTP server credentials
2. Set sender address
3. (Optional) Configure templates
4. Test with a sample message

## Usage Examples

### Sending a Simple Notification

```rust
use cns_client::CnsClient;

let client = CnsClient::new("http://cns:50051")?;

client.send_notification(
    "System Alert",
    "High CPU usage detected",
    Priority::High,
    vec![Channel::Slack, Channel::Email]
).await?;
```

### Using Templates

```rust
use cns_client::{CnsClient, Template};

let client = CnsClient::new("http://cns:50051")?;

let context = json!({
    "service": "data-service",
    "error": "Connection timeout",
    "timestamp": Utc::now()
});

client.send_from_template(
    Template::ErrorAlert,
    context,
    Priority::Critical,
    vec![Channel::Slack]
).await?;
```

### Checking Delivery Status

```rust
use cns_client::CnsClient;

let client = CnsClient::new("http://cns:50051")?;

let message_id = client.send_notification(...).await?;

// Later, check status
let status = client.get_delivery_status(&message_id).await?;
println!("Status: {:?}", status);
```

## Metrics

CNS exposes metrics on `/metrics`:

- `cns_messages_sent_total{channel, priority}` - Total messages sent
- `cns_messages_failed_total{channel, reason}` - Failed message count
- `cns_delivery_duration_seconds{channel}` - Delivery time histogram
- `cns_rate_limit_hits_total{channel}` - Rate limit hit count
- `cns_queue_depth{priority}` - Current queue depth

## Health Checks

- **Endpoint**: `/health`
- **Status Codes**: 200 (healthy), 503 (unhealthy)
- **Checks**:
  - Queue connectivity
  - Channel availability
  - Recent delivery success rate

## Integration with FKS Services

### Data Service
- Exchange connectivity alerts
- Data quality warnings
- Performance degradation alerts

### Janus
- Trading decision notifications
- Risk threshold alerts
- Strategy performance summaries

### Execution Service
- Order execution confirmations
- Fill notifications
- Error alerts

### Monitoring (Prometheus)
- Alert notifications via Alertmanager
- Threshold breach notifications
- System health summaries

## Development

### Running Locally

```bash
# Start CNS service
docker-compose up -d cns

# Check logs
docker-compose logs -f cns

# Send test notification
cargo run --bin cns-test-client
```

### Running Tests

```bash
# Unit tests
cargo test -p cns

# Integration tests
cargo test -p cns --test integration_tests

# End-to-end tests (requires running stack)
./scripts/test-cns-e2e.sh
```

### Adding a New Channel

1. Implement `Channel` trait in `src/channels/`
2. Add channel configuration to `Config`
3. Register channel in router
4. Add metrics
5. Write tests
6. Update documentation

## Troubleshooting

### Messages Not Delivering

1. Check CNS logs for errors
2. Verify channel configuration (webhooks, SMTP, etc.)
3. Check network connectivity
4. Review rate limiting settings
5. Inspect dead letter queue

### Slack Notifications Not Appearing

1. Verify webhook URL is correct
2. Check Slack app permissions
3. Confirm channel exists
4. Review Slack rate limits
5. Check CNS logs for Slack API errors

### High Latency

1. Check queue depth metrics
2. Review rate limiting configuration
3. Verify external service performance (Slack, SMTP)
4. Consider increasing worker count
5. Check network latency

### Rate Limiting Too Aggressive

1. Review rate limit configuration
2. Adjust limits in environment variables
3. Consider priority-based exemptions
4. Implement message batching
5. Use digest notifications for low-priority events

## Production Considerations

### Scaling
- CNS can run multiple instances with shared queue
- Consider dedicated instances per channel for isolation
- Monitor queue depth and adjust workers

### Reliability
- Configure retries appropriately
- Monitor dead letter queue
- Set up alerts for high failure rates
- Regular testing of all channels

### Security
- Rotate webhook URLs periodically
- Use secrets management (Vault) for credentials
- Validate message content
- Rate limit by source

## Related Documentation

- [Main Documentation Index](../../README.md)
- [Service Documentation](../README.md)
- [Operations Runbooks](../../runbooks/README.md)
- [Monitoring Setup](../../operations/monitoring/)

## Contributing

When updating CNS documentation:
1. Keep examples up to date with API changes
2. Test all code examples
3. Update integration checklists
4. Add troubleshooting entries for common issues
5. Update metrics documentation

## Status

**Current Version**: 1.0  
**Status**: Production Ready  
**Integrations**: Data Service, Janus, Execution Service, Monitoring  
**Supported Channels**: Slack, Email, Webhooks  
**Planned Channels**: SMS, PagerDuty, Discord