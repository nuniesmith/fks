#!/usr/bin/env python3
"""janus-bridge — Milestone 1: daily logged Janus<->crypto regime assessment.

Read-only/advisory by design:
  - polls Janus's RegimeBridgeService (GetCurrentRegime) every 5 minutes,
  - reads the crypto-regime bot's daily regime flags from its state.json
    (mounted read-only),
  - at the close of each 00:05 -> 00:05 UTC window appends one JSONL
    assessment line per pair plus a window summary.

Never touches the bot. Never posts anywhere. Log only.

Predeclared assessment rule (approved 2026-10-12):
  - window: 00:05 UTC -> next 00:05 UTC (aligned to the bot's regime read)
  - Janus daily call per pair: Bullish iff Bullish-side time-share >= 60%,
    Bearish iff Bearish-side >= 60%, else "no clear call" (excluded from
    agreement, never forced)
  - agreement = Janus call matches the bot's regime_bull flag for the day
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

JANUS_GRPC = os.environ.get("JANUS_BRIDGE_GRPC", "fks_janus:50052")
BOT_STATE_PATH = os.environ.get("JANUS_BRIDGE_BOT_STATE", "/bot-state/state.json")
DATA_DIR = os.environ.get("JANUS_BRIDGE_DATA_DIR", "/data")
SAMPLE_SECS = int(os.environ.get("JANUS_BRIDGE_SAMPLE_SECS", "300"))
WINDOW_MINUTE = int(os.environ.get("JANUS_BRIDGE_WINDOW_MINUTE", "5"))
CALL_THRESHOLD = float(os.environ.get("JANUS_BRIDGE_CALL_THRESHOLD", "0.60"))
STATUS_FILE = "/tmp/janus-bridge.status"

SERVICE_NAME = "fks.janus.v1.bridge.RegimeBridgeService"
GET_CURRENT = f"{SERVICE_NAME}/GetCurrentRegime"
ASSESSMENT_PATH = os.path.join(DATA_DIR, "assessment.jsonl")
FINALIZED_PATH = os.path.join(DATA_DIR, "finalized.txt")

# Hypothalamus variants -> directional side (from regime_bridge.proto)
BULLISH_SIDE = {
    "HYPOTHALAMUS_REGIME_STRONG_BULLISH",
    "HYPOTHALAMUS_REGIME_BULLISH",
}
BEARISH_SIDE = {
    "HYPOTHALAMUS_REGIME_STRONG_BEARISH",
    "HYPOTHALAMUS_REGIME_BEARISH",
}


def log(msg):
    print(f"[janus-bridge] {datetime.now(UTC).isoformat()} {msg}", flush=True)


def window_id(ts):
    """Window id = YYYY-MM-DD of the latest 00:05 UTC at or before ts."""
    dt = datetime.fromtimestamp(ts, UTC)
    if dt.hour == 0 and dt.minute < WINDOW_MINUTE:
        dt = dt - timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


def window_bounds(day_id):
    start = datetime.strptime(day_id, "%Y-%m-%d").replace(tzinfo=UTC) + timedelta(
        minutes=WINDOW_MINUTE
    )
    return start, start + timedelta(days=1)


def bot_pair_to_janus(pair):
    p = pair.upper()
    if not p.endswith("USD"):
        return None
    base = p[:-3]
    if base == "XBT":
        base = "BTC"
    return f"{base}/USDT"


def poll_janus():
    """One GetCurrentRegime call; returns {symbol: {hypo, amyg, scale, conf}}."""
    out = subprocess.run(
        [
            "grpcurl",
            "-plaintext",
            "-connect-timeout",
            "10",
            "-import-path",
            "/proto",
            "-proto",
            "fks/janus/v1/regime_bridge.proto",
            "-d",
            "{}",
            JANUS_GRPC,
            GET_CURRENT,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if out.returncode != 0:
        raise RuntimeError(f"grpcurl failed: {out.stderr.strip()[:300]}")
    states = {}
    for s in json.loads(out.stdout).get("states", []):
        states[s["symbol"]] = {
            "hypo": s.get("hypothalamusRegime", "HYPOTHALAMUS_REGIME_UNKNOWN"),
            "amyg": s.get("amygdalaRegime", "AMYGDALA_REGIME_UNKNOWN"),
            "scale": s.get("positionScale", 1.0),
            "conf": s.get("confidence", 0.0),
        }
    return states


def read_bot_state():
    """The bot's own daily flags (read-only). Returns dict or None."""
    try:
        with open(BOT_STATE_PATH) as f:
            s = json.load(f)
        return {
            "bull": dict(s.get("regime_bull", {})),
            "reading": {
                k: {
                    "close": v.get("close"),
                    "sma": v.get("sma"),
                    "bull": v.get("bull"),
                }
                for k, v in s.get("regime_reading", {}).items()
            },
            "last_regime_day": s.get("last_regime_day", ""),
        }
    except Exception as e:  # state missing/unparseable -> sample still counts
        log(f"WARN: cannot read bot state: {e}")
        return None


def samples_path(day_id):
    return os.path.join(DATA_DIR, f"samples-{day_id}.jsonl")


def finalized():
    try:
        with open(FINALIZED_PATH) as f:
            return {l.strip() for l in f if l.strip()}
    except FileNotFoundError:
        return set()


def mark_finalized(day_id):
    with open(FINALIZED_PATH, "a") as f:
        f.write(day_id + "\n")


def finalize(day_id):
    """Aggregate one closed window and append assessment + summary lines."""
    path = samples_path(day_id)
    samples = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    wstart, wend = window_bounds(day_id)

    # Bot flags active during this window: last sample whose last_regime_day
    # matches the window day (falls back to the last sample's bot reading).
    bot = None
    for smp in reversed(samples):
        b = smp.get("bot")
        if b and b.get("last_regime_day") == day_id:
            bot = b
            break
    if bot is None:
        for smp in reversed(samples):
            if smp.get("bot"):
                bot = smp["bot"]
                break

    n = len(samples)
    partial = n < 250  # spec: log partial days with sample count, no backfill
    lines = []
    calls = {}
    agree = disagree = unclear = 0

    pairs = sorted({s for smp in samples for s in smp["states"]})
    for symbol in pairs:
        seq = [smp["states"][symbol] for smp in samples if symbol in smp["states"]]
        m = len(seq)
        bull_ts = sum(1 for s in seq if s["hypo"] in BULLISH_SIDE) / m
        bear_ts = sum(1 for s in seq if s["hypo"] in BEARISH_SIDE) / m
        neut_ts = 1.0 - bull_ts - bear_ts
        amyg_ts = {}
        for s in seq:
            a = s["amyg"].replace("AMYGDALA_REGIME_", "").lower()
            amyg_ts[a] = amyg_ts.get(a, 0) + 1
        amyg_ts = {k: v / m for k, v in amyg_ts.items()}
        mean_conf = sum(s["conf"] for s in seq) / m
        cw_bull = sum(s["conf"] for s in seq if s["hypo"] in BULLISH_SIDE) / m
        cw_bear = sum(s["conf"] for s in seq if s["hypo"] in BEARISH_SIDE) / m
        transitions = sum(
            1 for a, b in zip(seq, seq[1:]) if a["hypo"] != b["hypo"]
        )
        if bull_ts >= CALL_THRESHOLD:
            call = "bullish"
        elif bear_ts >= CALL_THRESHOLD:
            call = "bearish"
        else:
            call = "no clear call"
        calls[symbol] = call

        bot_pair = next(
            (p for p in (bot or {}).get("bull", {}) if bot_pair_to_janus(p) == symbol),
            None,
        )
        bot_bull = (bot or {}).get("bull", {}).get(bot_pair) if bot_pair else None
        reading = (bot or {}).get("reading", {}).get(bot_pair, {}) if bot_pair else {}
        if call == "no clear call" or bot_bull is None:
            agreement = None
            unclear += 1
        else:
            agreement = (call == "bullish") == bool(bot_bull)
            agree, disagree = agree + agreement, disagree + (not agreement)

        lines.append(
            {
                "type": "assessment",
                "day": day_id,
                "window_start": wstart.isoformat(),
                "window_end": wend.isoformat(),
                "pair": symbol,
                "bot_pair": bot_pair,
                "bot": {
                    "bull": bot_bull,
                    "close": reading.get("close"),
                    "sma200": reading.get("sma"),
                    "distance": (
                        reading["close"] / reading["sma"] - 1.0
                        if reading.get("close") and reading.get("sma")
                        else None
                    ),
                    "last_regime_day": (bot or {}).get("last_regime_day"),
                },
                "janus": {
                    "samples": m,
                    "hypo_timeshare": {
                        "bullish": round(bull_ts, 4),
                        "bearish": round(bear_ts, 4),
                        "neutral": round(neut_ts, 4),
                        "dominant": max(
                            (("bullish", bull_ts), ("bearish", bear_ts),
                             ("neutral", neut_ts)),
                            key=lambda kv: kv[1],
                        )[0],
                    },
                    "amyg_timeshare": {
                        k: round(v, 4) for k, v in sorted(amyg_ts.items())
                    },
                    "mean_confidence": round(mean_conf, 4),
                    "conf_weighted_bullish": round(cw_bull, 4),
                    "conf_weighted_bearish": round(cw_bear, 4),
                    "transitions": transitions,
                    "daily_call": call,
                },
                "agreement": agreement,
                "partial": partial,
                "threshold": CALL_THRESHOLD,
            }
        )

    # Rolling 7-day agreement from the log plus the window just finalized
    # (the spec's evidence metric).
    clear7 = agree7 = 0
    window_start_7d = (
        datetime.strptime(day_id, "%Y-%m-%d").date() - timedelta(days=6)
    ).isoformat()
    try:
        with open(ASSESSMENT_PATH) as f:
            prior = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        prior = []
    for r in prior + lines:
        if r.get("type") == "assessment" and r["day"] >= window_start_7d:
            if r["agreement"] is not None:
                clear7 += 1
                agree7 += r["agreement"]

    summary = {
        "type": "summary",
        "day": day_id,
        "window_start": wstart.isoformat(),
        "window_end": wend.isoformat(),
        "samples": n,
        "partial": partial,
        "calls": calls,
        "agreeing_pairs": agree,
        "disagreeing_pairs": disagree,
        "no_clear_call_pairs": unclear,
        "agreement_rate_7d": round(agree7 / clear7, 4) if clear7 else None,
        "agreement_denominator_7d": clear7,
    }
    lines.append(summary)

    with open(ASSESSMENT_PATH, "a") as f:
        for rec in lines:
            f.write(json.dumps(rec) + "\n")
    mark_finalized(day_id)
    log(
        f"FINALIZED {day_id}: samples={n} partial={partial} "
        f"agree={agree} disagree={disagree} unclear={unclear} "
        f"7d_rate={summary['agreement_rate_7d']} calls={calls}"
    )


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    done = finalized()
    log(
        f"starting: janus={JANUS_GRPC} sample={SAMPLE_SECS}s "
        f"threshold={CALL_THRESHOLD} window_minute={WINDOW_MINUTE}"
    )
    while True:
        now = time.time()
        day = window_id(now)
        try:
            states = poll_janus()
        except Exception as e:
            log(f"WARN: poll failed: {e}")
            states = None
        if states is not None:
            rec = {
                "ts": now,
                "ts_iso": datetime.fromtimestamp(now, UTC).isoformat(),
                "day": day,
                "bot": read_bot_state(),
                "states": states,
            }
            with open(samples_path(day), "a") as f:
                f.write(json.dumps(rec) + "\n")
            # Finalize any closed, unfinalized windows.
            for fname in os.listdir(DATA_DIR):
                if fname.startswith("samples-") and fname.endswith(".jsonl"):
                    d = fname[len("samples-") : -len(".jsonl")]
                    if d != day and d not in done:
                        try:
                            finalize(d)
                        except Exception as e:
                            log(f"WARN: finalize {d} failed: {e}")
                        done = finalized()
        try:
            with open(STATUS_FILE, "w") as f:
                json.dump({"last_poll": time.time()}, f)
        except OSError:
            pass
        time.sleep(SAMPLE_SECS)


if __name__ == "__main__":
    main()
