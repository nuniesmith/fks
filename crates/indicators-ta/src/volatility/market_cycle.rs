//! Market Cycle Indicator.
//!
//! Python source: `indicators/other/market_cycle.py :: class MarketCycleIndicator`
//!
//! Detects market cycle phases from price momentum:
//! - `Markup`       — momentum > 0
//! - `Markdown`     — momentum < 0
//! - `Plateau`      — momentum == 0
//! - `Accumulation` — previous phase was Markdown, current changed
//! - `Distribution` — previous phase was Markup, current changed
//!
//! Output column: `"MarketCycle"` — encoded as `f64`:
//! - 1.0 = Markup, -1.0 = Markdown, 0.0 = Plateau,
//!   0.5 = Accumulation, -0.5 = Distribution.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

/// Numeric encoding for cycle phases (avoids `String` in `IndicatorOutput`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CyclePhase {
    Markup = 1,
    Markdown = -1,
    Plateau = 0,
    Accumulation = 2, // using 2/-2 to distinguish from Markup/Markdown
    Distribution = -2,
}

impl CyclePhase {
    pub fn as_f64(self) -> f64 {
        self as i32 as f64
    }
}

#[derive(Debug, Clone)]
pub struct MarketCycleParams {
    /// Momentum diff period.  Python default: 1.
    pub momentum_period: usize,
}
impl Default for MarketCycleParams {
    fn default() -> Self {
        Self { momentum_period: 1 }
    }
}

#[derive(Debug, Clone)]
pub struct MarketCycle {
    pub params: MarketCycleParams,
}

impl MarketCycle {
    pub fn new(params: MarketCycleParams) -> Self {
        Self { params }
    }
}

impl Default for MarketCycle {
    fn default() -> Self {
        Self::new(MarketCycleParams::default())
    }
}

impl Indicator for MarketCycle {
    fn name(&self) -> &'static str {
        "MarketCycle"
    }
    fn required_len(&self) -> usize {
        self.params.momentum_period + 1
    }
    fn required_columns(&self) -> &[&'static str] {
        &["close"]
    }

    /// Detects market cycle phase for each bar using price momentum and
    /// transition rules that mirror Python's pandas vectorised assignments.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let close: Vec<f64> = candles.iter().map(|c| c.close).collect();
        let mp = self.params.momentum_period;
        let n = close.len();

        // Step 1: assign base phases from momentum.
        let mut phases = vec![CyclePhase::Plateau; n];
        for i in mp..n {
            let momentum = close[i] - close[i - mp];
            phases[i] = if momentum > 0.0 {
                CyclePhase::Markup
            } else if momentum < 0.0 {
                CyclePhase::Markdown
            } else {
                CyclePhase::Plateau
            };
        }

        // Step 2: apply transition rules, matching Python's pandas semantics.
        //
        // Python does:
        //   cycle.loc[(cycle.shift(1) == "Markdown") & (cycle != "Markdown")] = "Accumulation"
        //   cycle.loc[(cycle.shift(1) == "Markup")   & (cycle != "Markup")]   = "Distribution"
        //
        // `cycle.shift(1)` in the second rule sees Accumulation values already
        // written by the first rule.  We replicate this by reading from `result`
        // (the output being built) rather than from the original `phases` slice.
        let mut result = phases.clone();
        for i in 1..n {
            match (result[i - 1], phases[i]) {
                (CyclePhase::Markdown, p) if p != CyclePhase::Markdown => {
                    result[i] = CyclePhase::Accumulation;
                }
                (CyclePhase::Markup, p) if p != CyclePhase::Markup => {
                    result[i] = CyclePhase::Distribution;
                }
                _ => {}
            }
        }

        let values: Vec<f64> = result.iter().map(|p| p.as_f64()).collect();

        Ok(IndicatorOutput::from_pairs([(
            "MarketCycle".to_string(),
            values,
        )]))
    }
}

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(MarketCycle::new(MarketCycleParams {
        momentum_period: param_usize(params, "momentum_period", 1)?,
    })))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn candles(closes: &[f64]) -> Vec<Candle> {
        closes
            .iter()
            .enumerate()
            .map(|(i, &c)| Candle {
                time: i64::try_from(i).expect("time index fits i64"),
                open: c,
                high: c,
                low: c,
                close: c,
                volume: 1.0,
            })
            .collect()
    }

    #[test]
    fn market_cycle_output_column() {
        let out = MarketCycle::default()
            .calculate(&candles(&[1.0, 2.0, 3.0]))
            .unwrap();
        assert!(out.get("MarketCycle").is_some());
    }

    #[test]
    fn rising_prices_give_markup() {
        let closes = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let out = MarketCycle::default().calculate(&candles(&closes)).unwrap();
        let vals = out.get("MarketCycle").unwrap();
        // Index 1+ should reflect Markup (1.0) except where transition rules fire.
        assert_eq!(vals[1], CyclePhase::Markup.as_f64());
    }

    #[test]
    fn falling_after_rising_gives_distribution() {
        // Rise then fall → distribution transition.
        let closes = vec![1.0, 2.0, 3.0, 2.0];
        let out = MarketCycle::default().calculate(&candles(&closes)).unwrap();
        let vals = out.get("MarketCycle").unwrap();
        assert_eq!(vals[3], CyclePhase::Distribution.as_f64());
    }

    #[test]
    fn factory_creates_market_cycle() {
        assert_eq!(factory(&HashMap::new()).unwrap().name(), "MarketCycle");
    }
}
