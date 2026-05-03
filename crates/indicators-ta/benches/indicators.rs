/// Criterion benchmarks for the indicators hot path.
///
/// Three groups:
///
/// 1. `engine_update` — full `Indicators::update()` replay at different dataset
///    sizes.  At every 10th bar past `training_period` (100) the engine runs
///    KMeans (O(N × K × 100 iters)).  At every 10th bar past bar 41 it also
///    re-runs `hurst_scalar` (O(N log N)).  These benchmarks make both costs
///    visible and provide a baseline for future optimisations.
///
/// 2. `engine_hot_bar` — a single `update()` call at bar 150, where both
///    KMeans and Hurst fire simultaneously.  `iter_batched` excludes the
///    warm-up cost from the measurement so the number reflects only the hot-
///    path work.
///
/// 3. `signal_pipeline` — full `SignalIndicator::calculate()` end-to-end for
///    different candle-slice sizes.  This is the realistic production cost.
use std::hint::black_box;

use criterion::{BatchSize, BenchmarkId, Criterion, criterion_group, criterion_main};

use indicators::{
    IndicatorConfig, IndicatorConfig as Cfg, Indicators, SignalIndicator, compute_signal,
    indicator::Indicator,
    signal::{
        confluence::ConfluenceEngine, cvd::CVDTracker, liquidity::LiquidityProfile,
        structure::MarketStructure, vol_regime::VolatilityPercentile,
    },
    types::Candle,
};

// ── Candle generation ─────────────────────────────────────────────────────────

/// Build `n` rising candles with realistic OHLCV variation.
fn rising_candles(n: usize) -> Vec<Candle> {
    (0..n)
        .map(|i| {
            // Small oscillation on top of the trend keeps KMeans meaningful.
            let wave = (i as f64 * 0.3).sin() * 0.5;
            let c = 100.0 + i as f64 * 0.25 + wave;
            Candle {
                time: i64::try_from(i).unwrap() * 60_000,
                open: c - 0.15,
                high: c + 0.35,
                low: c - 0.35,
                close: c,
                volume: 800.0 + ((i * 37) % 400) as f64,
            }
        })
        .collect()
}

// ── Group 1: engine_update replay ────────────────────────────────────────────

fn bench_engine_update(c: &mut Criterion) {
    let mut group = c.benchmark_group("engine_update");

    for &n_bars in &[100usize, 200, 500] {
        let candles = rising_candles(n_bars);
        group.bench_with_input(BenchmarkId::from_parameter(n_bars), &candles, |b, cs| {
            b.iter(|| {
                let mut ind = Indicators::new(Cfg::default());
                for candle in cs {
                    black_box(ind.update(black_box(candle)));
                }
            });
        });
    }

    group.finish();
}

// ── Group 2: single hot-bar update ───────────────────────────────────────────
//
// Bar 150 triggers KMeans (bars 100, 110, 120, 130, 140, 150) and Hurst
// (bars 41, 51, …, 141, 151 — so bar 150 also triggers Hurst at bar 150).
// `iter_batched` moves the warm-up into the setup phase so only the single
// `update()` call is timed.

fn bench_engine_hot_bar(c: &mut Criterion) {
    // Bar index for the measurement — chosen to coincide with a KMeans + Hurst
    // double-trigger: bar 150 satisfies (150 - 100) % 10 == 0 for KMeans and
    // (150 - 140) >= 10 for Hurst.
    let warmup_n: usize = 150;
    let warmup_candles = rising_candles(warmup_n);

    // The candle that will actually be measured.
    let measure_candle = rising_candles(warmup_n + 1).into_iter().last().unwrap();

    c.bench_function("engine_hot_bar_150_kmeans_plus_hurst", |b| {
        b.iter_batched(
            || {
                // Setup (excluded from timing): replay warmup_n bars.
                let mut ind = Indicators::new(Cfg::default());
                for c in &warmup_candles {
                    ind.update(c);
                }
                ind
            },
            |mut ind| {
                // Measured: one update on a post-training bar where both
                // KMeans and Hurst recompute.
                black_box(ind.update(black_box(&measure_candle)))
            },
            BatchSize::SmallInput,
        );
    });
}

/// Isolate a bar that does NOT trigger KMeans or Hurst (bar 155 — 5 bars after
/// the last trigger at 150) so we can see the baseline cost of a "normal" bar.
fn bench_engine_normal_bar(c: &mut Criterion) {
    let warmup_n: usize = 155;
    let warmup_candles = rising_candles(warmup_n);
    let measure_candle = rising_candles(warmup_n + 1).into_iter().last().unwrap();

    c.bench_function("engine_normal_bar_155_no_recompute", |b| {
        b.iter_batched(
            || {
                let mut ind = Indicators::new(Cfg::default());
                for c in &warmup_candles {
                    ind.update(c);
                }
                ind
            },
            |mut ind| black_box(ind.update(black_box(&measure_candle))),
            BatchSize::SmallInput,
        );
    });
}

// ── Group 3: full signal pipeline ────────────────────────────────────────────

fn bench_signal_pipeline(c: &mut Criterion) {
    let mut group = c.benchmark_group("signal_pipeline");

    for &n_bars in &[150usize, 300] {
        let candles = rising_candles(n_bars);
        let si = SignalIndicator::with_defaults();

        group.bench_with_input(BenchmarkId::from_parameter(n_bars), &candles, |b, cs| {
            b.iter(|| black_box(si.calculate(black_box(cs)).unwrap()));
        });
    }

    group.finish();
}

// ── Group 4: per-bar streaming pipeline (realistic loop) ─────────────────────
//
// Mirrors production usage: all sub-components updated one candle at a time,
// followed by `compute_signal`.  This reveals the true per-bar latency in a
// live trading loop.

fn bench_streaming_per_bar(c: &mut Criterion) {
    let candles = rising_candles(300);
    let cfg = IndicatorConfig::default();

    c.bench_function("streaming_per_bar_300_bars", |b| {
        b.iter(|| {
            let mut ind = Indicators::new(cfg.clone());
            let mut liq = LiquidityProfile::new(50, 20);
            let mut conf = ConfluenceEngine::new(8, 21, 50, 14, 14);
            let mut ms = MarketStructure::new(5, 0.5);
            let mut cvd = CVDTracker::new(10, 20);
            let mut vol = VolatilityPercentile::new(100);

            for c in &candles {
                ind.update(c);
                liq.update(c);
                conf.update(c);
                ms.update(c);
                cvd.update(c);
                vol.update(ind.atr);

                black_box(compute_signal(
                    c.close,
                    &ind,
                    &liq,
                    &conf,
                    &ms,
                    &cfg,
                    Some(&cvd),
                    Some(&vol),
                ));
            }
        });
    });
}

// ── Criterion wiring ──────────────────────────────────────────────────────────

criterion_group!(
    engine_benches,
    bench_engine_update,
    bench_engine_hot_bar,
    bench_engine_normal_bar,
);
criterion_group!(
    pipeline_benches,
    bench_signal_pipeline,
    bench_streaming_per_bar
);
criterion_main!(engine_benches, pipeline_benches);
