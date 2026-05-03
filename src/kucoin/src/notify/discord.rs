//! Discord Webhook Notifications

use crate::error::{BotError, Result};
use crate::types::{BotFill, BotOrder, BotPosition};
use chrono::{DateTime, Utc};
use exchange_apiws::Side as OrderSide;
use reqwest::Client;
use serde::{Deserialize, Serialize};

use tracing::{debug, error, info, warn};

#[allow(clippy::struct_excessive_bools)]
pub struct DiscordNotifier {
    webhook_url: String,
    client: Client,
    enabled: bool,
    notify_on_signal: bool,
    notify_on_fill: bool,
    notify_on_error: bool,
    stop_loss_pct: f64,
    take_profit_pct: f64,
    bot_name: String,
}

impl DiscordNotifier {
    #[allow(clippy::fn_params_excessive_bools)]
    pub fn new(
        webhook_url: String,
        enabled: bool,
        notify_on_signal: bool,
        notify_on_fill: bool,
        notify_on_error: bool,
    ) -> Self {
        Self {
            webhook_url,
            client: Client::new(),
            enabled,
            notify_on_signal,
            notify_on_fill,
            notify_on_error,
            stop_loss_pct: 2.0,
            take_profit_pct: 5.0,
            bot_name: "KC FUTURES TRADER".to_string(),
        }
    }

    #[allow(clippy::fn_params_excessive_bools)]
    pub fn with_risk_params(
        webhook_url: String,
        enabled: bool,
        notify_on_signal: bool,
        notify_on_fill: bool,
        notify_on_error: bool,
        stop_loss_pct: f64,
        take_profit_pct: f64,
    ) -> Self {
        Self {
            webhook_url,
            client: Client::new(),
            enabled,
            notify_on_signal,
            notify_on_fill,
            notify_on_error,
            stop_loss_pct,
            take_profit_pct,
            bot_name: "KC FUTURES TRADER".to_string(),
        }
    }

    pub fn from_env() -> Self {
        let webhook_url = std::env::var("DISCORD_WEBHOOK_GENERAL").unwrap_or_default();
        let enabled = std::env::var("DISCORD_ENABLE_NOTIFICATIONS")
            .unwrap_or_else(|_| "false".to_string())
            .parse()
            .unwrap_or(false);
        let notify_on_signal = std::env::var("DISCORD_NOTIFY_ON_SIGNAL")
            .unwrap_or_else(|_| "true".to_string())
            .parse()
            .unwrap_or(true);
        let notify_on_fill = std::env::var("DISCORD_NOTIFY_ON_FILL")
            .unwrap_or_else(|_| "true".to_string())
            .parse()
            .unwrap_or(true);
        let notify_on_error = std::env::var("DISCORD_NOTIFY_ON_ERROR")
            .unwrap_or_else(|_| "true".to_string())
            .parse()
            .unwrap_or(true);
        let stop_loss_pct = std::env::var("DISCORD_DEFAULT_STOP_LOSS_PCT")
            .unwrap_or_else(|_| "2.0".to_string())
            .parse()
            .unwrap_or(2.0);
        let take_profit_pct = std::env::var("DISCORD_DEFAULT_TAKE_PROFIT_PCT")
            .unwrap_or_else(|_| "5.0".to_string())
            .parse()
            .unwrap_or(5.0);
        let bot_name =
            std::env::var("DISCORD_BOT_NAME").unwrap_or_else(|_| "KC FUTURES TRADER".to_string());

        Self {
            webhook_url,
            client: Client::new(),
            enabled,
            notify_on_signal,
            notify_on_fill,
            notify_on_error,
            stop_loss_pct,
            take_profit_pct,
            bot_name,
        }
    }

    pub const fn is_enabled(&self) -> bool {
        self.enabled && !self.webhook_url.is_empty()
    }

    /// Returns `true` when fill notifications are enabled.
    pub const fn notify_on_fill(&self) -> bool {
        self.notify_on_fill
    }
    #[allow(clippy::too_many_arguments)]
    pub async fn notify_signal_received(
        &self,
        signal_id: &str,
        symbol: &str,
        side: OrderSide,
        quantity: f64,
        price: Option<f64>,
        confidence: f64,
        strategy_id: &str,
    ) -> Result<()> {
        if !self.is_enabled() || !self.notify_on_signal {
            return Ok(());
        }

        debug!("Sending signal notification to Discord: {signal_id}");

        if let Some(entry_price) = price {
            return self
                .notify_signal_with_levels(
                    signal_id,
                    symbol,
                    side,
                    quantity,
                    entry_price,
                    confidence,
                    strategy_id,
                    self.stop_loss_pct,
                    self.take_profit_pct,
                )
                .await;
        }

        let side_emoji = match side {
            OrderSide::Buy => "🟢",
            OrderSide::Sell => "🔴",
        };

        let embed = DiscordEmbed {
            title: format!("{side_emoji} Trading Signal Received"),
            description: Some(format!("New trading signal from strategy `{strategy_id}`")),
            color: match side {
                OrderSide::Buy => 3_066_993,
                OrderSide::Sell => 15_158_332,
            },
            fields: vec![
                EmbedField {
                    name: "Symbol".into(),
                    value: symbol.into(),
                    inline: true,
                },
                EmbedField {
                    name: "Side".into(),
                    value: format!("{side:?}").to_uppercase(),
                    inline: true,
                },
                EmbedField {
                    name: "Quantity".into(),
                    value: format!("{quantity:.8}"),
                    inline: true,
                },
                EmbedField {
                    name: "Price".into(),
                    value: "Market".into(),
                    inline: true,
                },
                EmbedField {
                    name: "Confidence".into(),
                    value: format!("{:.1}%", confidence * 100.0),
                    inline: true,
                },
                EmbedField {
                    name: "Signal ID".into(),
                    value: signal_id.into(),
                    inline: false,
                },
            ],
            timestamp: Some(Utc::now()),
            footer: Some(EmbedFooter {
                text: self.bot_name.clone(),
            }),
        };

        self.send_webhook(vec![embed]).await
    }

    #[allow(clippy::too_many_arguments, clippy::too_many_lines)]
    pub async fn notify_signal_with_levels(
        &self,
        signal_id: &str,
        symbol: &str,
        side: OrderSide,
        quantity: f64,
        entry_price: f64,
        confidence: f64,
        strategy_id: &str,
        stop_loss_pct: f64,
        take_profit_pct: f64,
    ) -> Result<()> {
        if !self.is_enabled() || !self.notify_on_signal {
            return Ok(());
        }

        debug!("Sending enhanced signal notification to Discord: {signal_id}");

        let total_value = entry_price * quantity;

        let (stop_loss_price, take_profit_price) = match side {
            OrderSide::Buy => {
                let sl = entry_price * (1.0 - stop_loss_pct / 100.0);
                let tp = entry_price * (1.0 + take_profit_pct / 100.0);
                (sl, tp)
            }
            OrderSide::Sell => {
                let sl = entry_price * (1.0 + stop_loss_pct / 100.0);
                let tp = entry_price * (1.0 - take_profit_pct / 100.0);
                (sl, tp)
            }
        };

        let risk_amount = total_value * (stop_loss_pct / 100.0);
        let reward_amount = total_value * (take_profit_pct / 100.0);
        let risk_reward_ratio = take_profit_pct / stop_loss_pct;

        let side_emoji = match side {
            OrderSide::Buy => "🟢",
            OrderSide::Sell => "🔴",
        };
        let side_name = match side {
            OrderSide::Buy => "BUY (LONG)",
            OrderSide::Sell => "SELL (SHORT)",
        };

        let sl_direction = match side {
            OrderSide::Buy => format!("-{stop_loss_pct:.1}%"),
            OrderSide::Sell => format!("+{stop_loss_pct:.1}%"),
        };
        let tp_direction = match side {
            OrderSide::Buy => format!("+{take_profit_pct:.1}%"),
            OrderSide::Sell => format!("-{take_profit_pct:.1}%"),
        };
        let execution_steps = match side {
            OrderSide::Buy => {
                "1️⃣ Enter LONG at entry price\n2️⃣ Set Stop Loss immediately\n3️⃣ Set Take Profit immediately\n4️⃣ Log trade in journal"
            }
            OrderSide::Sell => {
                "1️⃣ Enter SHORT at entry price\n2️⃣ Set Stop Loss immediately\n3️⃣ Set Take Profit immediately\n4️⃣ Log trade in journal"
            }
        };

        let embed = DiscordEmbed {
            title: format!("{side_emoji} {side_name} Signal"),
            description: Some(format!(
                "**{}**\nStrategy: `{}`\nConfidence: **{:.1}%**",
                symbol,
                strategy_id,
                confidence * 100.0
            )),
            color: match side {
                OrderSide::Buy => 65_280,
                OrderSide::Sell => 16_711_680,
            },
            fields: vec![
                EmbedField {
                    name: "📍 Entry Price".into(),
                    value: format!("**${entry_price:.2}**"),
                    inline: true,
                },
                EmbedField {
                    name: "📦 Position Size".into(),
                    value: format!("**${total_value:.2}**"),
                    inline: true,
                },
                EmbedField {
                    name: "📊 Quantity".into(),
                    value: format!("{quantity:.8}"),
                    inline: true,
                },
                EmbedField {
                    name: "🛑 Stop Loss".into(),
                    value: format!("**${stop_loss_price:.2}**\n({sl_direction})"),
                    inline: true,
                },
                EmbedField {
                    name: "🎯 Take Profit".into(),
                    value: format!("**${take_profit_price:.2}**\n({tp_direction})"),
                    inline: true,
                },
                EmbedField {
                    name: "⚖️ Risk/Reward".into(),
                    value: format!("**1:{risk_reward_ratio:.1}**"),
                    inline: true,
                },
                EmbedField {
                    name: "💰 Potential Profit".into(),
                    value: format!("+${reward_amount:.2}"),
                    inline: true,
                },
                EmbedField {
                    name: "⚠️ Potential Loss".into(),
                    value: format!("-${risk_amount:.2}"),
                    inline: true,
                },
                EmbedField {
                    name: "🔑 Signal ID".into(),
                    value: signal_id.into(),
                    inline: true,
                },
                EmbedField {
                    name: "⏰ Execution Steps".into(),
                    value: execution_steps.into(),
                    inline: false,
                },
            ],
            timestamp: Some(Utc::now()),
            footer: Some(EmbedFooter {
                text: format!("{} • Manual Execution", self.bot_name),
            }),
        };

        self.send_webhook(vec![embed]).await
    }

    /// Notify that an order was filled.
    pub async fn notify_order_filled(
        &self,
        order: &BotOrder,
        fill: &BotFill,
        position: Option<&BotPosition>,
    ) -> Result<()> {
        if !self.is_enabled() || !self.notify_on_fill {
            return Ok(());
        }

        debug!("Sending order fill notification to Discord: {}", order.id);

        let side_lower = order.side.to_lowercase();
        let side_emoji = if side_lower == "buy" { "✅" } else { "💰" };

        let mut fields = vec![
            EmbedField {
                name: "Symbol".into(),
                value: order.symbol.clone(),
                inline: true,
            },
            EmbedField {
                name: "Side".into(),
                value: order.side.to_uppercase(),
                inline: true,
            },
            EmbedField {
                name: "Filled Quantity".into(),
                value: format!("{:.8}", fill.quantity),
                inline: true,
            },
            EmbedField {
                name: "Fill Price".into(),
                value: format!("${:.2}", fill.price),
                inline: true,
            },
            EmbedField {
                name: "Total Value".into(),
                value: format!("${:.2}", fill.quantity * fill.price),
                inline: true,
            },
            EmbedField {
                name: "Fee".into(),
                value: format!("${:.4} {}", fill.fee, fill.fee_currency),
                inline: true,
            },
        ];

        if let Some(pos) = position {
            let pnl_emoji = if pos.unrealized_pnl >= 0.0 {
                "📈"
            } else {
                "📉"
            };
            fields.push(EmbedField {
                name: format!("{pnl_emoji} Position P&L"),
                value: format!(
                    "Unrealized: ${} | Realized: ${}",
                    pos.unrealized_pnl, pos.realized_pnl
                ),
                inline: false,
            });
        }

        fields.push(EmbedField {
            name: "Order ID".into(),
            value: order.id.clone(),
            inline: false,
        });

        let color = if side_lower == "buy" {
            3_066_993
        } else {
            15_158_332
        };

        let embed = DiscordEmbed {
            title: format!("{side_emoji} Order Filled"),
            description: Some("Order successfully executed".into()),
            color,
            fields,
            timestamp: Some(Utc::now()),
            footer: Some(EmbedFooter {
                text: "KC FUTURES TRADER".into(),
            }),
        };

        self.send_webhook(vec![embed]).await
    }

    /// Notify about a position update.
    pub async fn notify_position_update(&self, position: &BotPosition, reason: &str) -> Result<()> {
        if !self.is_enabled() {
            return Ok(());
        }

        debug!(
            "Sending position update notification to Discord: {}",
            position.symbol
        );

        let pnl_emoji = if position.unrealized_pnl >= 0.0 {
            "📈"
        } else {
            "📉"
        };

        let embed = DiscordEmbed {
            title: format!("{pnl_emoji} Position Update"),
            description: Some(reason.into()),
            color: if position.unrealized_pnl >= 0.0 {
                3_066_993
            } else {
                15_158_332
            },
            fields: vec![
                EmbedField {
                    name: "Symbol".into(),
                    value: position.symbol.clone(),
                    inline: true,
                },
                EmbedField {
                    name: "Side".into(),
                    value: position.side.to_uppercase(),
                    inline: true,
                },
                EmbedField {
                    name: "Quantity".into(),
                    value: format!("{:.8}", position.quantity),
                    inline: true,
                },
                EmbedField {
                    name: "Entry Price".into(),
                    value: format!("${}", position.average_entry_price),
                    inline: true,
                },
                EmbedField {
                    name: "Current Price".into(),
                    value: format!("${}", position.current_price),
                    inline: true,
                },
                EmbedField {
                    name: "Unrealized P&L".into(),
                    value: format!("${}", position.unrealized_pnl),
                    inline: true,
                },
            ],
            timestamp: Some(Utc::now()),
            footer: Some(EmbedFooter {
                text: "KC FUTURES TRADER".into(),
            }),
        };

        self.send_webhook(vec![embed]).await
    }

    pub async fn notify_error(
        &self,
        error_type: &str,
        error_message: &str,
        context: &str,
    ) -> Result<()> {
        if !self.is_enabled() || !self.notify_on_error {
            return Ok(());
        }

        warn!("Sending error notification to Discord: {error_type}");

        let embed = DiscordEmbed {
            title: "❌ Execution Error".into(),
            description: Some(format!("**{error_type}**")),
            color: 15_158_332,
            fields: vec![
                EmbedField {
                    name: "Error".into(),
                    value: error_message.into(),
                    inline: false,
                },
                EmbedField {
                    name: "Context".into(),
                    value: context.into(),
                    inline: false,
                },
            ],
            timestamp: Some(Utc::now()),
            footer: Some(EmbedFooter {
                text: "KC FUTURES TRADER - Alert".into(),
            }),
        };

        self.send_webhook(vec![embed]).await
    }

    pub async fn notify_daily_summary(
        &self,
        total_trades: usize,
        winning_trades: usize,
        losing_trades: usize,
        total_pnl: f64,
        win_rate: f64,
    ) -> Result<()> {
        if !self.is_enabled() {
            return Ok(());
        }

        debug!("Sending daily summary to Discord");

        let pnl_emoji = if total_pnl >= 0.0 { "💰" } else { "⚠️" };

        let embed = DiscordEmbed {
            title: format!("{pnl_emoji} Daily Trading Summary"),
            description: Some("End of day performance report".into()),
            color: if total_pnl >= 0.0 {
                3_066_993
            } else {
                15_158_332
            },
            fields: vec![
                EmbedField {
                    name: "Total Trades".into(),
                    value: total_trades.to_string(),
                    inline: true,
                },
                EmbedField {
                    name: "Winning Trades".into(),
                    value: winning_trades.to_string(),
                    inline: true,
                },
                EmbedField {
                    name: "Losing Trades".into(),
                    value: losing_trades.to_string(),
                    inline: true,
                },
                EmbedField {
                    name: "Win Rate".into(),
                    value: format!("{:.1}%", win_rate * 100.0),
                    inline: true,
                },
                EmbedField {
                    name: "Total P&L".into(),
                    value: format!("${total_pnl:.2}"),
                    inline: true,
                },
            ],
            timestamp: Some(Utc::now()),
            footer: Some(EmbedFooter {
                text: self.bot_name.clone(),
            }),
        };

        self.send_webhook(vec![embed]).await
    }

    pub async fn notify_bot_started(&self, version: &str, dry_run: bool) -> Result<()> {
        if !self.is_enabled() {
            return Ok(());
        }
        info!("Sending bot started notification to Discord");

        let mode = if dry_run {
            "**🧪 DRY RUN MODE**"
        } else {
            "**🔴 LIVE TRADING**"
        };

        let embed = DiscordEmbed {
            title: "🤖 Trading Bot Started".into(),
            description: Some(format!("Version: {version}\nMode: {mode}")),
            color: 65_280,
            fields: vec![
                EmbedField {
                    name: "Default Stop Loss".into(),
                    value: format!("{:.1}%", self.stop_loss_pct),
                    inline: true,
                },
                EmbedField {
                    name: "Default Take Profit".into(),
                    value: format!("{:.1}%", self.take_profit_pct),
                    inline: true,
                },
                EmbedField {
                    name: "Started At".into(),
                    value: Utc::now().format("%Y-%m-%d %H:%M:%S UTC").to_string(),
                    inline: true,
                },
            ],
            timestamp: Some(Utc::now()),
            footer: Some(EmbedFooter {
                text: self.bot_name.clone(),
            }),
        };

        self.send_webhook(vec![embed]).await
    }

    pub async fn notify_bot_stopped(&self, reason: &str) -> Result<()> {
        if !self.is_enabled() {
            return Ok(());
        }
        info!("Sending bot stopped notification to Discord");

        let embed = DiscordEmbed {
            title: "🛑 Trading Bot Stopped".into(),
            description: Some(format!("Reason: {reason}")),
            color: 16_711_680,
            fields: vec![EmbedField {
                name: "Stopped At".into(),
                value: Utc::now().format("%Y-%m-%d %H:%M:%S UTC").to_string(),
                inline: false,
            }],
            timestamp: Some(Utc::now()),
            footer: Some(EmbedFooter {
                text: self.bot_name.clone(),
            }),
        };

        self.send_webhook(vec![embed]).await
    }

    pub async fn notify_warning(&self, warning_msg: &str, context: &str) -> Result<()> {
        if !self.is_enabled() {
            return Ok(());
        }
        warn!("Sending warning notification to Discord: {warning_msg}");

        let embed = DiscordEmbed {
            title: "⚠️ Warning".into(),
            description: Some(format!("**Context:** {context}\n\n{warning_msg}")),
            color: 16_750_848,
            fields: vec![],
            timestamp: Some(Utc::now()),
            footer: Some(EmbedFooter {
                text: self.bot_name.clone(),
            }),
        };

        self.send_webhook(vec![embed]).await
    }

    pub async fn notify_balance_update(&self, balance: f64, change_pct: Option<f64>) -> Result<()> {
        if !self.is_enabled() {
            return Ok(());
        }
        debug!("Sending balance update notification to Discord");

        let color = match change_pct {
            Some(pct) if pct > 0.0 => 65_280,
            Some(pct) if pct < 0.0 => 16_711_680,
            Some(_) => 8_421_504,
            None => 3_447_003,
        };

        let description = if let Some(pct) = change_pct {
            format!("Current Balance: **${balance:.2}**\nChange: **{pct:+.2}%**")
        } else {
            format!("Current Balance: **${balance:.2}**")
        };

        let embed = DiscordEmbed {
            title: "💰 Account Balance Update".into(),
            description: Some(description),
            color,
            fields: vec![],
            timestamp: Some(Utc::now()),
            footer: Some(EmbedFooter {
                text: self.bot_name.clone(),
            }),
        };

        self.send_webhook(vec![embed]).await
    }

    async fn send_webhook(&self, embeds: Vec<DiscordEmbed>) -> Result<()> {
        if !self.is_enabled() {
            return Ok(());
        }

        let payload = DiscordWebhook { embeds };

        match self
            .client
            .post(&self.webhook_url)
            .json(&payload)
            .send()
            .await
        {
            Ok(response) => {
                if response.status().is_success() {
                    debug!("Discord notification sent successfully");
                    Ok(())
                } else {
                    let status = response.status();
                    let error_text = response.text().await.unwrap_or_default();
                    error!("Discord webhook failed with status {status}: {error_text}");
                    Err(BotError::Order(format!("Discord webhook failed: {status}")))
                }
            }
            Err(e) => {
                error!("Failed to send Discord notification: {e}");
                Err(BotError::Order(format!(
                    "Failed to send Discord notification: {e}"
                )))
            }
        }
    }

    pub const fn set_stop_loss_pct(&mut self, pct: f64) {
        self.stop_loss_pct = pct;
    }
    pub const fn set_take_profit_pct(&mut self, pct: f64) {
        self.take_profit_pct = pct;
    }
    pub fn set_bot_name(&mut self, name: String) {
        self.bot_name = name;
    }
    pub const fn stop_loss_pct(&self) -> f64 {
        self.stop_loss_pct
    }
    pub const fn take_profit_pct(&self) -> f64 {
        self.take_profit_pct
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct DiscordWebhook {
    embeds: Vec<DiscordEmbed>,
}

#[derive(Debug, Serialize, Deserialize)]
struct DiscordEmbed {
    title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    description: Option<String>,
    color: u32,
    fields: Vec<EmbedField>,
    #[serde(skip_serializing_if = "Option::is_none")]
    timestamp: Option<DateTime<Utc>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    footer: Option<EmbedFooter>,
}

#[derive(Debug, Serialize, Deserialize)]
struct EmbedField {
    name: String,
    value: String,
    inline: bool,
}

#[derive(Debug, Serialize, Deserialize)]
struct EmbedFooter {
    text: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_notifier_creation() {
        let notifier = DiscordNotifier::new(
            "https://discord.com/api/webhooks/test".into(),
            true,
            true,
            true,
            true,
        );
        assert!(notifier.is_enabled());
        assert!((notifier.stop_loss_pct() - 2.0).abs() < f64::EPSILON);
        assert!((notifier.take_profit_pct() - 5.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_notifier_with_risk_params() {
        let notifier = DiscordNotifier::with_risk_params(
            "https://discord.com/api/webhooks/test".into(),
            true,
            true,
            true,
            true,
            3.0,
            6.0,
        );
        assert!(notifier.is_enabled());
        assert!((notifier.stop_loss_pct() - 3.0).abs() < f64::EPSILON);
        assert!((notifier.take_profit_pct() - 6.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_notifier_disabled() {
        let notifier = DiscordNotifier::new(String::new(), false, true, true, true);
        assert!(!notifier.is_enabled());
    }

    #[test]
    fn test_notifier_no_webhook() {
        let notifier = DiscordNotifier::new(String::new(), true, true, true, true);
        assert!(!notifier.is_enabled());
    }

    #[test]
    fn test_set_risk_params() {
        let mut notifier = DiscordNotifier::new(
            "https://discord.com/api/webhooks/test".into(),
            true,
            true,
            true,
            true,
        );
        notifier.set_stop_loss_pct(1.5);
        notifier.set_take_profit_pct(4.5);
        assert!((notifier.stop_loss_pct() - 1.5).abs() < f64::EPSILON);
        assert!((notifier.take_profit_pct() - 4.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_set_bot_name() {
        let mut notifier = DiscordNotifier::new(
            "https://discord.com/api/webhooks/test".into(),
            true,
            true,
            true,
            true,
        );
        notifier.set_bot_name("My Custom Bot".into());
    }
}
