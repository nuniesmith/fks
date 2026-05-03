//! Runtime-only domain types.
//!
//! Shared exchange types (`Candle`, `Side`, `OrderType`, `contract_value`)
//! come from `exchange_apiws::types` — import them directly.
//!
//! This module provides:
//! - `Position(i32)`  — live position size signed integer wrapper
//! - `BotPosition`    — notification-friendly position snapshot (f64 fields)
//! - `BotFill`        — notification-friendly fill snapshot

use serde::{Deserialize, Serialize};

// ── Position ──────────────────────────────────────────────────────────────────

/// Live position: positive = long N contracts, negative = short, zero = flat.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Position(pub i32);

impl Position {
    pub const fn is_flat(self) -> bool {
        self.0 == 0
    }
    pub const fn is_long(self) -> bool {
        self.0 > 0
    }
    pub const fn is_short(self) -> bool {
        self.0 < 0
    }
    /// Returns the absolute position size as an unsigned integer.
    ///
    /// Uses `unsigned_abs()` instead of `abs() as u32` to avoid the
    /// overflow edge case when `self.0 == i32::MIN` (debug-mode panic).
    pub const fn size(self) -> u32 {
        self.0.unsigned_abs()
    }

    /// The side needed to *close* this position, if any.
    pub const fn close_side(self) -> Option<exchange_apiws::Side> {
        use exchange_apiws::Side;
        match self.0 {
            n if n > 0 => Some(Side::Sell),
            n if n < 0 => Some(Side::Buy),
            _ => None,
        }
    }
}

// ── Notification shim types ───────────────────────────────────────────────────
//
// The Discord notifier needs clean, flat structs with f64 fields.
// Construct these from exchange_apiws REST response types when sending alerts.

/// Snapshot of the current position for notification purposes.
///
/// Build from `exchange_apiws::rest::account::PositionInfo`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BotPosition {
    pub symbol: String,
    /// "buy" (long) or "sell" (short)
    pub side: String,
    /// Absolute number of contracts.
    pub quantity: f64,
    pub average_entry_price: f64,
    pub current_price: f64,
    pub unrealized_pnl: f64,
    pub realized_pnl: f64,
}

impl BotPosition {
    /// Convert from the REST position response.
    pub fn from_info(info: &exchange_apiws::rest::account::PositionInfo, mark_price: f64) -> Self {
        let side = if info.current_qty >= 0 { "buy" } else { "sell" };
        Self {
            symbol: info.symbol.clone(),
            side: side.to_string(),
            quantity: f64::from(info.current_qty.unsigned_abs()),
            average_entry_price: info.avg_entry_price.unwrap_or(0.0),
            current_price: mark_price,
            unrealized_pnl: info.unrealised_pnl.unwrap_or(0.0),
            realized_pnl: info.realised_pnl.unwrap_or(0.0),
        }
    }
}

/// A single trade fill for notification purposes.
///
/// Build from `exchange_apiws::rest::orders::Fill`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BotFill {
    pub symbol: String,
    pub order_id: String,
    /// "buy" or "sell"
    pub side: String,
    pub price: f64,
    pub quantity: f64,
    pub fee: f64,
    pub fee_currency: String,
}

impl BotFill {
    pub fn from_fill(f: &exchange_apiws::rest::orders::Fill) -> Self {
        Self {
            symbol: f.symbol.clone(),
            order_id: f.order_id.clone(),
            side: f.side.clone(),
            price: f.price,
            quantity: f64::from(f.size),
            fee: f.fee,
            fee_currency: f.fee_currency.clone().unwrap_or_default(),
        }
    }
}

/// A placed/filled order for notification purposes.
///
/// Build from `exchange_apiws::rest::orders::OrderDetail`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BotOrder {
    pub id: String,
    pub symbol: String,
    /// "buy" or "sell"
    pub side: String,
    pub price: f64,
    pub size: u32,
}

impl BotOrder {
    pub fn from_detail(o: &exchange_apiws::rest::orders::OrderDetail) -> Self {
        Self {
            id: o.id.clone(),
            symbol: o.symbol.clone(),
            side: o.side.clone(),
            price: o.price.unwrap_or(0.0),
            size: o.size,
        }
    }
}
