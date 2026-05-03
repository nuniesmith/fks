//! Contract sizing from a fixed dollar trade size.
//!
//! The number of contracts is derived from the dollar amount of *margin*
//! (`trade_size_usd`) the user wants to commit per trade, multiplied by
//! leverage to get the target notional, then divided by the per-contract
//! value in USD at the current price.
//!
//! ```text
//! notional   = trade_size_usd × leverage
//! contracts  = floor(notional / (price × contract_value))
//! contracts  = min(contracts, max_contracts)
//! ```

use crate::BotSettings;
use crate::settings::contract_value;

/// Calculate how many contracts to open for a given signal.
///
/// Returns `0` if any input is non-positive or the resulting size rounds down
/// to zero (position too small at current price/leverage).
pub fn contracts_for_signal(price: f64, settings: &BotSettings) -> u32 {
    if price <= 0.0 || settings.trade_size_usd <= 0.0 || settings.leverage == 0 {
        return 0;
    }

    let cv = contract_value(&settings.symbol);
    if cv <= 0.0 {
        return 0;
    }

    // Notional the user wants to control (margin × leverage).
    let notional = settings.trade_size_usd * f64::from(settings.leverage);

    // Each contract controls (price × cv) USDT of notional.
    let raw = (notional / (price * cv)).floor() as u32;

    // Hard cap — never exceed max_contracts regardless of math.
    raw.min(settings.max_contracts)
}

#[cfg(test)]
mod tests {
    use proptest::prelude::*;

    use crate::bot::sizing::contracts_for_signal;
    use crate::settings::BotSettings;

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// Minimal settings builder — only the fields sizing cares about.
    fn settings(
        symbol: &str,
        trade_size_usd: f64,
        leverage: u32,
        max_contracts: u32,
    ) -> BotSettings {
        BotSettings {
            symbol: symbol.into(),
            trade_size_usd,
            leverage,
            max_contracts,
            ..BotSettings::base()
        }
    }

    // ── Unit tests ────────────────────────────────────────────────────────────

    #[test]
    fn zero_price_returns_zero() {
        let s = settings("XBTUSDTM", 500.0, 5, 50);
        assert_eq!(contracts_for_signal(0.0, &s), 0);
    }

    #[test]
    fn negative_price_returns_zero() {
        let s = settings("XBTUSDTM", 500.0, 5, 50);
        assert_eq!(contracts_for_signal(-1.0, &s), 0);
    }

    #[test]
    fn zero_trade_size_returns_zero() {
        let s = settings("XBTUSDTM", 0.0, 5, 50);
        assert_eq!(contracts_for_signal(50_000.0, &s), 0);
    }

    #[test]
    fn negative_trade_size_returns_zero() {
        let s = settings("XBTUSDTM", -100.0, 5, 50);
        assert_eq!(contracts_for_signal(50_000.0, &s), 0);
    }

    #[test]
    fn zero_leverage_returns_zero() {
        let s = settings("XBTUSDTM", 500.0, 0, 50);
        assert_eq!(contracts_for_signal(50_000.0, &s), 0);
    }

    #[test]
    fn max_contracts_cap_is_respected() {
        // $500k margin × 100× leverage at $1 price with 0.001 cv
        // raw = 500_000 * 100 / (1.0 * 0.001) = 50_000_000 — far above any cap.
        let s = settings("XBTUSDTM", 500_000.0, 100, 10);
        assert_eq!(contracts_for_signal(1.0, &s), 10);
    }

    /// Concrete known-good calculation for BTC (cv = 0.001).
    ///
    /// notional = 500 × 5 = 2500 USDT
    /// per_contract = 50_000 × 0.001 = 50 USDT
    /// contracts = floor(2500 / 50) = 50
    #[test]
    fn btc_known_value() {
        let s = settings("XBTUSDTM", 500.0, 5, 100);
        assert_eq!(contracts_for_signal(50_000.0, &s), 50);
    }

    /// Concrete known-good calculation for ETH (cv = 0.01).
    ///
    /// notional = 500 × 5 = 2500 USDT
    /// per_contract = 3_000 × 0.01 = 30 USDT
    /// contracts = floor(2500 / 30) = 83
    #[test]
    fn eth_known_value() {
        let s = settings("ETHUSDTM", 500.0, 5, 1000);
        assert_eq!(contracts_for_signal(3_000.0, &s), 83);
    }

    /// Concrete known-good calculation for SOL (cv = 1.0).
    ///
    /// notional = 100 × 10 = 1000 USDT
    /// per_contract = 150.0 × 1.0 = 150 USDT
    /// contracts = floor(1000 / 150) = 6
    #[test]
    fn sol_known_value() {
        let s = settings("SOLUSDTM", 100.0, 10, 1000);
        assert_eq!(contracts_for_signal(150.0, &s), 6);
    }

    /// Price so high that notional / per_contract rounds to zero.
    #[test]
    fn rounds_to_zero_when_price_too_high() {
        // notional = 1 × 1 = 1 USDT
        // per_contract = 1_000_000 × 0.001 = 1000 USDT
        // floor(1 / 1000) = 0
        let s = settings("XBTUSDTM", 1.0, 1, 50);
        assert_eq!(contracts_for_signal(1_000_000.0, &s), 0);
    }

    // ── Property tests ────────────────────────────────────────────────────────

    proptest! {
        /// Output never exceeds max_contracts for any valid input.
        #[test]
        fn prop_never_exceeds_max_contracts(
            price         in 0.01f64..1_000_000.0f64,
            trade_size    in 0.01f64..1_000_000.0f64,
            leverage      in 1u32..=200u32,
            max_contracts in 1u32..=10_000u32,
        ) {
            let s = settings("XBTUSDTM", trade_size, leverage, max_contracts);
            let result = contracts_for_signal(price, &s);
            prop_assert!(result <= max_contracts,
                "got {result} > max_contracts {max_contracts}");
        }

        /// Any non-positive price must return 0.
        #[test]
        fn prop_non_positive_price_is_zero(
            price      in prop::num::f64::NEGATIVE | prop::num::f64::ZERO,
            trade_size in 0.01f64..1_000_000.0f64,
            leverage   in 1u32..=200u32,
        ) {
            let s = settings("XBTUSDTM", trade_size, leverage, 1000);
            prop_assert_eq!(contracts_for_signal(price, &s), 0);
        }

        /// Higher trade_size_usd never yields fewer contracts (monotone).
        #[test]
        fn prop_more_margin_never_fewer_contracts(
            price      in 1.0f64..500_000.0f64,
            small_size in 1.0f64..5_000.0f64,
            extra      in 0.01f64..5_000.0f64,
            leverage   in 1u32..=50u32,
        ) {
            let large_size = small_size + extra;
            let s_small = settings("XBTUSDTM", small_size, leverage, 100_000);
            let s_large = settings("XBTUSDTM", large_size, leverage, 100_000);
            let small_result = contracts_for_signal(price, &s_small);
            let large_result = contracts_for_signal(price, &s_large);
            prop_assert!(large_result >= small_result,
                "trade_size {small_size} → {small_result} contracts, \
                 trade_size {large_size} → {large_result} contracts (went down)");
        }

        /// Higher price never yields more contracts (monotone, same notional).
        #[test]
        fn prop_higher_price_never_more_contracts(
            low_price  in 1.0f64..500_000.0f64,
            extra      in 0.01f64..500_000.0f64,
            trade_size in 1.0f64..10_000.0f64,
            leverage   in 1u32..=50u32,
        ) {
            let high_price = low_price + extra;
            let s = settings("XBTUSDTM", trade_size, leverage, 100_000);
            let low_result  = contracts_for_signal(low_price,  &s);
            let high_result = contracts_for_signal(high_price, &s);
            prop_assert!(high_result <= low_result,
                "price {low_price} → {low_result} contracts, \
                 price {high_price} → {high_result} contracts (went up)");
        }

        /// Higher leverage never yields fewer contracts (monotone).
        #[test]
        fn prop_more_leverage_never_fewer_contracts(
            price       in 1.0f64..500_000.0f64,
            trade_size  in 1.0f64..10_000.0f64,
            low_lev     in 1u32..=50u32,
            extra_lev   in 1u32..=50u32,
        ) {
            let high_lev = low_lev + extra_lev;
            let s_low  = settings("XBTUSDTM", trade_size, low_lev,  100_000);
            let s_high = settings("XBTUSDTM", trade_size, high_lev, 100_000);
            let low_result  = contracts_for_signal(price, &s_low);
            let high_result = contracts_for_signal(price, &s_high);
            prop_assert!(high_result >= low_result,
                "leverage {low_lev} → {low_result} contracts, \
                 leverage {high_lev} → {high_result} contracts (went down)");
        }

        /// Result is always consistent with the floor formula when cap is not hit.
        #[test]
        fn prop_matches_floor_formula(
            price      in 1.0f64..500_000.0f64,
            trade_size in 1.0f64..10_000.0f64,
            leverage   in 1u32..=50u32,
        ) {
            // Use a very high cap so it never interferes.
            let s = settings("XBTUSDTM", trade_size, leverage, u32::MAX);
            let result = contracts_for_signal(price, &s);

            let cv = 0.001_f64; // XBTUSDTM
            let notional = trade_size * f64::from(leverage);
            let expected = (notional / (price * cv)).floor() as u32;

            prop_assert_eq!(result, expected,
                "formula expected {} but got {} (price={}, size={}, lev={})",
                expected, result, price, trade_size, leverage);
        }
    }
}
