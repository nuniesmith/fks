# Rithmic R|API Integration — Spike / Design Doc

> **Status update (2026-07):** the connector **foundation has since shipped**
> along the lines designed here — read-only doctrine mechanically enforced by
> test (fks #185), `candles_futures` persistence (#182), positions/PnL
> subscription + `GET /positions` (#183). The code lives in the **private
> `fks-state` repo** (`crates/rithmic-connector`; §3.1's home question is
> resolved — it moved there in the #196 prune), deployed via the compose
> `rithmic` profile and runtime-gated on `RITHMIC_ENABLED`. It stays **idle**:
> Phase 0 (paid dev-kit credentials + conformance) remains the long pole, so
> everything below about the access gate is still the operative truth.
>
> **Status (original):** research + design only. **No Rithmic code is proposed
> or written here** — the SDK/protocol is gated behind a paid Rithmic account,
> per-app credentials, and a conformance review. This is the timeboxed
> evaluation that [`WEBUI_PLATFORM_ROADMAP.md`](WEBUI_PLATFORM_ROADMAP.md)
> **P12** requires *before* any futures-feed work is scheduled ("SDK evaluation
> spike — **timeboxed 1 week, decides everything after**").
>
> **Quality bar:** the roadmap and the janus `EXPERIENCE_PIPELINE.md` house
> style — every load-bearing claim is either verified against the tree or
> flagged as an assumption. Because the Rithmic protocol cannot be exercised
> without paid access, this doc is deliberately explicit about what is
> **verified**, what is **researched from public sources**, and what is an
> **assumption to be confirmed during the spike**.
>
> **Doctrine, up front and non-negotiable:** the platform is a *manual trading
> co-pilot* (root `CLAUDE.md`: "no autonomous execution"). Rithmic integration
> is **READ-ONLY by construction** — positions, order history, and book/DOM
> data flowing *in*. The order plant (execution) is explicitly, permanently out
> of scope for this line of work.

---

## 0. TL;DR (the two things P12 asked the spike to decide)

- **Recommended integration shape:** a dedicated, credential-gated
  **`rithmic-connector`** container (its own service, *not* folded into
  `exchange-apiws`, which is crypto-venue-shaped) that speaks Rithmic's
  **R|Protocol API** — the *wire spec* (protobuf over TLS WebSocket), **not**
  the compiled R|API+ C++/.NET SDK — using the community Rust crate
  [`rithmic-rs`](https://crates.io/crates/rithmic-rs) as the client. It
  authenticates from the existing 3-slot broker secret (user/password/system),
  subscribes **read-only** plants (Ticker for DOM, History for bars, PnL for
  positions), and writes through the same janus storage contracts
  (`candles_futures`, `book_events_futures`) so the UI treats it as just another
  registered source. Activation is gated end-to-end on `/api/capabilities`
  reporting `rithmic: true`.

- **The single biggest risk / unknown:** **access and conformance, not code.**
  Nothing — not connectivity, not the DOM volume measurement, not even the
  `rithmic-rs` viability check — can start until a **paid Rithmic account +
  per-app dev credentials + a test-system name** are in hand, and Rithmic's
  **conformance review** gates production URLs. That external dependency, whose
  timeline Rithmic controls, is the true "weeks + unknown" in the P12 estimate.
  A **secondary, now-downgraded** risk: the roadmap assumed "no maintained Rust
  client"; that turns out to be **too pessimistic** (see §5.1) — which *lowers*
  the engineering estimate but does not touch the access gate.

---

## 1. What Rithmic R|API actually is

Researched from Rithmic's public pages and multiple broker/community sources
(cited in §9). **None of this is verified against a live connection** — flagged
inline where it matters.

### 1.1 It is three different products under one banner

Rithmic markets several "programmatic trading interfaces", and conflating them
is the first mistake to avoid — the roadmap's §3.2 language ("R|API+ is a
proprietary C++/.NET SDK gateway protocol — not a public WebSocket") describes
**one** of them and understates the option that matters most to us:

| Product | Form | Languages | Relevance to us |
|---|---|---|---|
| **R\|API+** | Compiled **SDK** (shared libs + headers) | C++ and .NET only | The proprietary gateway the roadmap named. Would force an FFI or a sidecar in a non-Rust runtime. **Not our first choice.** |
| **R\|Protocol API** | **Wire-line spec** — Google protobuf framed over a (TLS) WebSocket | *Any* language that can speak protobuf + WS | **The one we want.** No compiled Rithmic binary; the "SDK" is just `.proto` files + connection docs. A Rust client is therefore *possible* and, per §5.1, *already exists*. |
| **R\|Diamond** | Ultra-low-latency variant | — | HFT-oriented; irrelevant to a read-only co-pilot. |

> **Key correction to the roadmap (honest finding #1):** R|Protocol API is a
> *wire spec, not a compiled SDK*. It is explicitly documented as
> language-agnostic ("allowing applications to be built in any language").
> "Proprietary" is still true in the sense that the `.proto` files and the
> connection/URL details are gated behind account approval — but there is **no
> C++/.NET binary in the critical path** if we take the R|Protocol route. This
> is the single most estimate-moving finding in the spike (§5.1 completes it).

### 1.2 How R|Protocol works (as documented, not as verified)

- **Session-based, over TLS WebSocket.** The client opens a WebSocket to a
  Rithmic gateway URL, then exchanges protobuf messages (login → subscribe →
  stream). *Assumption:* framing is length-prefixed protobuf; confirm during
  the spike.
- **Split across "PLANTS."** Functionality is partitioned into independent
  services the client connects to separately:
  - **TICKER_PLANT** — live market data: trades, quotes, **and order book / DOM**.
  - **HISTORY_PLANT** — historical tick + bar data.
  - **ORDER_PLANT** — order entry, order/execution reports, positions.
  - **PNL_PLANT** — position and P&L tracking (in some client libraries).
  > **Doctrine mapping:** we subscribe **TICKER, HISTORY, and PNL** (all
  > read-only inputs). We **never open the ORDER_PLANT for writes.** Reading
  > *order history / fills* is desirable but may only be available via the order
  > plant's report stream — an open question (§8) to resolve without ever
  > sending an order-entry message.
- **Credentials.** Connecting requires: a Rithmic **user + password**, a
  **`system_name`** string (e.g. the documented `"Rithmic Test"` /
  `"Rithmic Paper Trading"`; production system names differ), and per-app
  approval. Gateway URLs for the environments (test vs. production) are handed
  out *after* onboarding — production URLs specifically only after conformance
  (§1.3).

### 1.3 Access is gated, and gated harder than a crypto exchange key

This is the part that dominates the schedule:

1. **A funded/entitled Rithmic account** through a Rithmic-connected FCM/broker
   (AMP, Ironbeam, EdgeClear, Optimus, etc.) — the user already has this (they
   *manually trade Rithmic futures* — §2).
2. **A developer/API request** to Rithmic for a **dev kit + app credentials**
   (the `.proto` files, connection docs, and a test-system login).
3. **Build + test against the Rithmic Test system.**
4. **Conformance review** — Rithmic validates the app against their technical,
   functional, and *risk* requirements. **Production URLs are only released
   after passing.** Community reports describe being asked to "connect to the
   order plant and leave the app running" as part of certification.
   > *Assumption to verify:* whether a **read-only, market-data-only** app faces
   > a lighter conformance path than a full order-routing app. It plausibly
   > does, but Rithmic decides. Treat as unknown.

> **Honest limits (matches roadmap §5.3):** Rithmic credentials are **not
> verifiable via a cheap signed HTTP read** the way a Kraken/KuCoin key is.
> Validity is proven *implicitly* when the connector authenticates against the
> test system. The "Test" button in `/settings` will remain a no-op for Rithmic
> (verified: the picker marks Rithmic `testable: false` / no ping —
> `fks-web/src/routes/settings/+page.svelte`).

---

## 2. User context (what the integration is *for*)

Verified against the roadmap and the merged fks-web provider picker; the
user-intent line is quoted from the roadmap.

- **The user manually trades Rithmic futures.** The platform does **not** place
  those trades and must not. It **observes**.
- **Read-only pull from Rithmic creds:** positions, order history, and
  **book-level / DOM** data. Nothing writes back to Rithmic.
- **Credential-gated "focus logic."** Roadmap §5.2, verified in code
  (`fks-web/src/routes/settings/+page.svelte:64-65`): *"Rithmic is the futures-
  trading focus: its workflows only activate when a rithmic credential is
  present."* Futures/Rithmic surfaces **light up only when a Rithmic credential
  exists**, and go dark (not broken — dark) otherwise.

### 2.1 The provider picker is real — verified

fks-web **#24** (merged 2026-07-06) ships the Rithmic option. Verified in
`fks-web/src/routes/settings/+page.svelte`:

- `id: 'rithmic', label: 'Rithmic', kind: 'broker'` (line 122) — distinct from
  the crypto `kind: 'exchange'` providers.
- **3-slot mapping, documented in-code** (lines 126-132):
  - **User → `api_key`**
  - **Password → `api_secret`**
  - **System → `api_passphrase`** (the third slot, `required: true`, placeholder
    *"e.g. Rithmic Paper Trading"*).
- `testable: false` — no public reachability ping, correctly (Rithmic has none).

The storage side is also verified as ready-enough: the spawner secret store
already carries `api_passphrase` as an optional third slot
(`crates/spawner/src/models.rs:71`; encrypted with ChaCha20-Poly1305 into
`ruby_db`). So a Rithmic credential is **storable today** — no schema change is
required just to hold it. (The `kind`-aware secret-store cleanup in roadmap §5.1
is a *nicety* that renames the slots honestly — `broker: user+password+system` —
but is **not a blocker** for this spike.)

> **Assumption:** `system_name` fits cleanly in the third slot as an opaque
> string. It is not a secret (it is often a well-known value like
> `"Rithmic Paper Trading"`), but storing it alongside the credential keeps the
> record self-contained. Confirm the connector reads all three from the same
> injected secret at spawn (§3.3).

---

## 3. Architecture: where the feed lives and how its data reaches the charts

### 3.1 Where the connector lives — a standalone bridge, not a janus source, not `exchange-apiws`

Doctrine tension, stated plainly. Root `CLAUDE.md` says **"janus is the single
data path — don't add a second data path elsewhere."** Taken literally, a
Rithmic source belongs *inside* janus's Data module as another `[[data.sources]]`
entry. But three facts push the *client* out into its own process while keeping
the *storage path* unified:

1. **Wrong-shape neighbor.** `exchange-apiws` is crypto-REST/WS-venue-shaped
   (Kraken/KuCoin/Binance/Crypto.com auth + order models). Rithmic's
   plant/protobuf/conformance model shares none of that surface. Folding it in
   would pollute a clean crate. **Verdict: not `exchange-apiws`.** (Roadmap §3.2
   agrees.)
2. **Blast-radius + gating.** The connector is **only deployed / only running
   when Rithmic creds exist** (§4.2 gating). A crashing/reconnecting third-party
   protocol client should not be able to take down janus's core crypto ingest.
   A separate container is the natural isolation boundary.
3. **Conformance realism.** A dedicated app is exactly what Rithmic conformance
   expects to certify ("leave *the app* running"). A distinct binary with a
   distinct app credential is cleaner to certify than a subsystem of a larger
   brain.

**Resolution — the "honest exception" the roadmap already carved out (§3.1):**
a dedicated **`rithmic-connector`** container that is a *client sidecar*, not a
*second data path*. It does **not** own its own storage semantics — it writes
through **the same janus storage contracts** and **registers itself in the same
source-status API** (§3.1 of the roadmap: `GET /api/data/sources`). Doctrine is
honored where it counts: **one storage path, one source registry, one health
surface.** The connector is just another registered source that happens to run
in its own process because its protocol is alien and its lifecycle is gated.

> Home repo: either a new `nuniesmith/rithmic-connector` repo or a
> `crates/rithmic-connector/` in `fks` (like `crates/spawner`). Lean toward
> **in-`fks`** for the spike (fewer moving parts, shares the compose/secrets
> plumbing), extract later if it grows. Decide in the spike PR.

```
   Rithmic gateway (TLS WS, gated)              janus (unchanged core)
   ┌───────────────────────────┐                ┌────────────────────────┐
   │ TICKER_PLANT  (DOM/trades) │                │  Data module           │
   │ HISTORY_PLANT (bars)       │                │  crypto klines-ws ...   │
   │ PNL_PLANT     (positions)  │                │                        │
   │ ORDER_PLANT   (NEVER open  │                │  SourceRegistry ◄───────┼── registers
   │               for writes)  │                │  /api/data/sources     │   itself
   └─────────────┬─────────────┘                └───────────┬────────────┘
                 │  rithmic-rs (Rust, R|Protocol)            │
        ┌────────▼──────────────────────────────┐           │
        │  rithmic-connector  (gated container)  │           │
        │  • auth from 3-slot broker secret      │           │
        │  • read-only plant subscriptions       │           │
        │  • aggregate trades → futures klines   │           │
        │  • normalize depth → book events       │           │
        │  • positions/orders snapshot           │           │
        └───┬───────────────┬───────────────┬────┘           │
            │ ILP           │ ILP           │ HTTP/JSON       │
            ▼               ▼               ▼                 ▼
   QuestDB candles_    QuestDB book_    positions/orders   source-status
   futures             events_futures   (Postgres or       (unified UI
   (venue rithmic:)    (venue rithmic:) status endpoint)    "Data" panel)
            │               │               │
            ▼               ▼               ▼
      /charts (futures) DOM/footprint    Rithmic positions &
      via fks-web       panel (later)    order-history panel
      adapter
```

### 3.2 Reaching QuestDB / the charts — a *separate instrument namespace*

Futures are **not** the crypto candle namespace, and conflating them would
silently corrupt series (roadmap §3.1 already flags "KuCoin BTC-USDT and Binance
BTCUSDT stop being implicitly the same series"). Concrete rules:

- **Market data → new tables, not `candles_crypto`.** Verified: the janus candle
  sink hardcodes `candles_crypto` (roadmap §9:
  `grep 'const TABLE' janus/services/data/src/candle_sink.rs`). The multi-asset
  work (roadmap **P11**, a prerequisite for P12) parameterizes that into
  `candles_<asset_class>`. Rithmic futures klines land in **`candles_futures`**;
  depth lands in **`book_events_futures`** (QuestDB ILP, high-volume — §3.4).
- **Symbol namespace: `venue:SYMBOL`.** Adopt `rithmic:MESU6`,
  `rithmic:ESU6` etc. at the API/UI boundary (roadmap §3.1 recommends
  `venue:SYMBOL` platform-wide). Futures symbols carry an **expiry/contract
  month** (`MESU6` = Micro E-mini S&P, Sep 2026) — a dimension crypto symbols
  lack. The connector must handle **front-month rolls** (open question §8).
- **Charts get futures for free-ish.** Once `candles_futures` exists and the
  fks-web chart symbol picker + adapter QuestDB queries understand the
  `venue:SYMBOL` scheme (the two touch points named in roadmap §3.1), a futures
  chart is the *same* lightweight-charts render as a crypto chart. Indicators
  (the janus `indicators-ta` compute path, roadmap §6) apply unchanged — they
  operate on candles regardless of asset class.

### 3.3 Positions & order history — a status surface, not a candle series

Positions and fills are **relational snapshots**, not time series. Two viable homes:

- **Postgres** (`janus_db` or a small connector-owned schema): `positions`
  (`ts, account, symbol, net_qty, avg_price, open_pnl`) and `order_history`
  (`ts, account, symbol, side, qty, price, status, order_id`). The
  `NetWorthHistoryPanel` precedent (roadmap §4.2) shows the pattern.
- **A live `/status`-style endpoint** on the connector (like the crypto bots'
  `/status`) that the fks-web adapter proxies — simplest for "what's my current
  position right now."

**Recommendation:** live `/status` for *current* positions (cheap, always
fresh); Postgres append for *order history* (needs durability + range queries).
Resolve during the read-only-panel phase, aligned with wherever the crypto
`StateStore` PR lands trade-ledger schema (roadmap §4.1, §8.4) so the futures
ledger and the crypto ledger are shaped alike.

### 3.4 Credential-gated capability flag — reuse the roadmap's mechanism verbatim

No new mechanism. Roadmap §5.2 defines it and P7 ships it:

- The fks-web adapter exposes **`GET /api/capabilities`** →
  `{ rithmic: true, … }`, derived from `/secrets/status` (does a
  `kind: 'broker'` / Rithmic credential exist?) **plus** source status (is the
  connector actually up and streaming?).
- One store, `$lib/stores/capabilities.ts`, consumes it. Gated surfaces — the
  Rithmic/futures workspace group in the TabBar (the dormant `workspaces.ts`
  rithmic entry finally has a use), Rithmic panels in the panel registry
  (roadmap §2), the futures focus logic — **render only when `rithmic === true`.**
- The **connector uses the same signal on the backend**: it **idles / is not
  deployed** until a Rithmic credential exists. No creds ⇒ no container ⇒ no
  wasted Rithmic session.

> Two-level truth worth exposing in the capability: **`rithmic: creds-present`**
> vs. **`rithmicLive: connector-streaming`**. Creds present but connector not
> yet built/authenticated should light the *nav* (so the user sees the futures
> group) while individual data panels show an honest "connecting / not yet
> streaming" state — the roadmap's "degrades gracefully until it lands"
> (§7 sequencing note).

---

## 4. Phased plan

Mirrors roadmap P11→P12 and the platform's "each phase independently shippable
and reversible" doctrine. **Every phase after Phase 0 is blocked on the access
gate (§1.3); the calendar is Rithmic's, not ours.**

### Phase 0 — Access + prerequisites (do this FIRST; it is the long pole)

Not engineering — procurement/paperwork, but nothing else can start:

- Request the Rithmic **dev kit + app credentials + test-system login** through
  the user's FCM.
- Confirm scope with Rithmic: **read-only / market-data app** — is the
  conformance path lighter? (§1.3 open question.)
- Land roadmap **P11** (multi-asset storage contracts: `candles_futures`,
  venue-tagged symbols) and **P7** (capabilities gating) — both are Rithmic-free
  and useful on their own, and both are prerequisites here.
- **Exit criterion:** test-system credentials in hand + `candles_futures`
  exists. Until then, P12 stays *unscheduled* (roadmap: "do not schedule
  downstream work on it until the spike reports").

### Phase 1 — The spike proper (~1 week of *engineering*, once Phase 0 clears)

Timeboxed; **validate connectivity + exactly one data type behind a feature
flag.** Concretely:

- Stand up `rithmic-connector` (empty container, gated OFF by default).
- Pull in [`rithmic-rs`](https://crates.io/crates/rithmic-rs); authenticate to
  the **Test system** with the 3-slot secret; open **one** plant.
- **Prove one data type end-to-end:** subscribe **TICKER_PLANT trades for one
  symbol** (e.g. `MES`), aggregate to 1-minute bars, write `candles_futures`
  with `venue=rithmic`, see it render on a futures chart. *One symbol, one
  interval, behind `RITHMIC_CONNECTOR=1`.*
- **Measure the DOM volume** (§3.4 / roadmap open-Q #5) — subscribe depth for a
  couple of CME symbols and record message rate + QuestDB ILP absorption. This
  measurement *shapes* the `book_events_futures` schema and the
  conflation/top-N decision. **This is the spike's most valuable output.**
- **Report:** does `rithmic-rs` actually work against Test? What's the DOM
  firehose look like? What did conformance ask for? **This report re-estimates
  everything after it** (roadmap P12 intent).

### Phase 2 — Read-only positions / history panel

- Connector subscribes **PNL_PLANT** (current positions) and reads
  order/fill **reports** (read-only; §8 caveat about whether that requires the
  order plant's report stream *without* order-entry).
- Expose current positions via `/status`; append order history to Postgres (§3.3).
- fks-web: a **`RithmicPositionsPanel`** + **`RithmicOrderHistoryPanel`** in the
  panel registry (roadmap §2), gated on `capabilities.rithmic`.
- This is the highest *user value per unit effort* — it directly answers "show
  me what I'm holding / what I did," which is the manual trader's core ask.

### Phase 3 — DOM / book data

- Promote the spike's depth measurement into a real **`book_events_futures`**
  schema (top-N levels vs. full depth vs. conflated snapshots — decided by the
  Phase-1 numbers).
- **DOM / footprint panel** in fks-web (the roadmap's "DOM/footprint panels
  (later)" leaf, §3.1 diagram).
- Watch host resource budget — depth for even a few symbols "dwarfs kline
  traffic" (roadmap open-Q #5).

### Phase ∞ — Autonomous execution: **NEVER** (doctrine)

The ORDER_PLANT stays closed for writes, permanently. Root `CLAUDE.md`:
*"The system is a **manual trading co-pilot**. All signal flow terminates at a
human decision point."* Rithmic execution would put a live-order path outside
the manual execution gate — categorically disallowed. **Not "later." Not "with
a two-key arm." Not at all** on this integration. This line exists in the doc so
no future reader mistakes the closed order plant for an unfinished feature.

---

## 5. Open questions + explicit risks

### 5.1 Rust R|API client availability — the roadmap's biggest assumption, re-examined (honest finding #2)

The roadmap (§3.2) states there is **"no maintained Rust client to lean on."**
The spike's research says that is **too pessimistic** — and because the roadmap
flagged this exact point as estimate-defining, correcting it is the spike's job:

| Crate | Latest | Last publish | Downloads (recent) | License | Verdict |
|---|---|---|---|---|---|
| [`rithmic-rs`](https://crates.io/crates/rithmic-rs) (pbeets) | **2.0.0** | **2026-04-21** | 9.7k (2.9k recent) | MIT OR Apache-2.0 | **Actively maintained.** Actor-per-plant over tokio channels; supports **Ticker (incl. order book), Order, History, PnL** plants. Reconnection is caller's job (stated limitation). **The candidate.** |
| [`ff_rithmic_api`](https://crates.io/crates/ff_rithmic_api) (BurnOutTrader) | 0.2.4 | 2024-10-24 | 13k (29 recent) | MIT | **Effectively stale** (author's own README points to a newer project). Useful as a *reference* for compiled protos, not as a dependency. |
| [`async_rithmic`](https://github.com/rundef/async_rithmic) | — | active | — (Python) | — | Not Rust, but the **best-documented reference implementation** of R|Protocol (readthedocs) — invaluable for understanding the connection/login/subscribe dance during the spike. |

**Impact on the estimate:** this is a **major finding, but it moves the number
*down*, not up.** The roadmap priced P12 partly on "wrap the official C++/.NET
SDK" (FFI or a non-Rust sidecar — expensive, ugly in a Rust-first stack). The
R|Protocol + `rithmic-rs` route means a **pure-Rust, crates.io-consumed client**
that fits the existing pattern (`CLAUDE.md`: "consume the published crates —
never re-vendor"). **The engineering got cheaper; the access gate did not
move.** That asymmetry is the whole point of the TL;DR.

**Risks that come with leaning on a community crate** (state them, don't paper over):

- **Not official / not vendor-supported.** A single-maintainer crate in a
  regulated-adjacent path. Mitigation: MIT/Apache dual license means we can vendor
  + patch if it stalls; the wire spec is stable, so a fork is survivable.
- **Reconnection is our responsibility** (documented limitation). The connector
  must own a reconnect/resubscribe loop — non-trivial for a session protocol,
  and a real chunk of Phase-1/2 effort.
- **Conformance is against *our app*, not the crate.** Using `rithmic-rs` does
  not shortcut conformance; Rithmic certifies our binary's behavior.
- **Protocol drift.** If Rithmic revs the `.proto`s, we depend on the crate (or
  our fork) keeping up. Low-frequency risk, but real.

### 5.2 The biggest risk overall: access + conformance (external, uncontrollable)

Restating the TL;DR because it dominates: **the schedule is gated on a
third party we do not control.** Dev-kit issuance, test-system access, and
especially **conformance sign-off for production URLs** are on Rithmic's clock.
No amount of engineering readiness shortcuts it. **Everything downstream of
Phase 0 should be treated as "ready to start, blocked on access,"** and P12
should not be calendared until test credentials exist — exactly the roadmap's
instruction.

### 5.3 Open questions to resolve *during* the spike

1. **Read-only order history without the order plant?** Can fills/order history
   be read via a report subscription without ever enabling order *entry*, and
   does that keep us in a lighter conformance tier? (§1.2, §4.2)
2. **Lighter conformance for a market-data-only app?** Ask Rithmic directly. If
   yes, Phase 1→2 accelerates materially. (§1.3)
3. **DOM volume vs. this host.** Does QuestDB ILP on the current box absorb full
   depth for N CME symbols, or must the connector conflate / top-N? This is a
   **measurement**, the spike's headline deliverable. (§3.4, roadmap open-Q #5)
4. **`book_events_futures` schema** falls out of #3 (full depth vs. top-N vs.
   conflated snapshots).
5. **Contract rolls.** How to represent front-month vs. continuous series in the
   `rithmic:SYMBOL` namespace (chart continuity across expiries). (§3.2)
6. **Connector home** — ~~new `rithmic-connector` repo vs. `crates/` in
   `fks`~~ **resolved**: it started in-`fks` and moved to the private
   `fks-state` repo (`crates/rithmic-connector`) in the #196 prune, alongside
   the rest of the funded-side code. (§3.1)
7. **Positions/orders storage** — live `/status` vs. Postgres, aligned with the
   crypto `StateStore` trade-ledger schema. (§3.3, roadmap §4.1)
8. **Framing / TLS specifics of R|Protocol** — the one genuinely unverifiable
   set of assumptions until we hold the dev kit. (§1.2)

### 5.4 Assumptions ledger (things this doc asserts that only paid access can confirm)

- R|Protocol framing is length-prefixed protobuf over a TLS WebSocket. *(§1.2)*
- `system_name` is an opaque, non-secret string that fits the third secret slot. *(§2.1)*
- Ticker plant exposes DOM at a granularity useful for a footprint panel. *(§1.2, §3.4)*
- A read-only app can subscribe positions/fills without opening order entry. *(§4.2, §5.3)*
- `rithmic-rs` works against the current Rithmic Test system as its README implies. *(§5.1)*

Each is a **spike exit check**, not a settled fact.

---

## 6. Recommendation (what to actually do)

1. **Kick off Phase 0 access now** — it is the long pole and it is free to start.
2. **Land P11 + P7** (storage contracts + capabilities gating) in parallel —
   both are Rithmic-free, independently valuable, and prerequisites.
3. **When test creds arrive, run the 1-week spike** (Phase 1): `rithmic-connector`
   + `rithmic-rs` + one data type behind `RITHMIC_CONNECTOR=1`, and **measure the
   DOM firehose.** The spike report re-estimates Phases 2-3.
4. **Never open the order plant for writes.** Doctrine.

**Integration shape (one line):** a credential-gated, read-only
`rithmic-connector` sidecar speaking **R|Protocol** (not the R|API+ SDK) via
`rithmic-rs`, writing `candles_futures` / `book_events_futures` and registering
in janus's source-status API so the UI treats Rithmic as just another source.

**Biggest risk / unknown (one line):** **access + conformance** — a paid
account, per-app credentials, and Rithmic's certification gate the whole
timeline, and none of it is under our control; the encouraging news (a
maintained Rust client exists) lowers the *engineering* cost but not that gate.

---

## 7. What this doc does NOT do

- It writes **no Rithmic code** and adds **no dependency** — the SDK/protocol is
  gated; the `rithmic-rs` recommendation is a *candidate to validate in the
  spike*, not a merged choice.
- It does **not** schedule P12 — that remains blocked on Phase 0 access, per the
  roadmap.
- It does **not** touch execution — the order plant stays closed by doctrine.

---

## 8. Re-verify the ground truth

```bash
# Rithmic provider merged in the picker, kind=broker, 3-slot mapping, not testable:
grep -n "rithmic\|api_passphrase\|System\|testable" \
  ~/github/fks-web/src/routes/settings/+page.svelte

# The secret store already holds an optional third slot (api_passphrase)
# (spawner code lives in the fks-spawner repo since the #196 prune):
sed -n '60,85p' ~/github/fks-spawner/crates/spawner/src/models.rs

# Candle sink is hardcoded crypto today (P11 parameterizes it → candles_futures):
grep -n 'const TABLE' ~/github/janus/services/data/src/candle_sink.rs

# Roadmap P12 intent (spike decides everything after; do not schedule downstream):
grep -n "P12\|SDK evaluation\|weeks + unknown" \
  ~/github/fks/docs/architecture/WEBUI_PLATFORM_ROADMAP.md

# Doctrine — no autonomous execution:
grep -n "no autonomous execution\|manual trading co-pilot" ~/github/fks/CLAUDE.md

# Rust client maturity (the estimate-moving finding):
#   rithmic-rs — v2.0.0 (2026-04), MIT/Apache, maintained; ff_rithmic_api — stale
curl -s https://crates.io/api/v1/crates/rithmic-rs   | jq '.crate.max_version, .crate.updated_at'
curl -s https://crates.io/api/v1/crates/ff_rithmic_api | jq '.crate.max_version, .crate.updated_at'
```

## 9. Sources (public research; none exercised against a live connection)

- Rithmic — Programmatic Trading Interfaces: <https://www.rithmic.com/apis>
- Rithmic — API request / onboarding: <https://www.rithmic.com/api-request>
- Rithmic — FAQ: <https://www.rithmic.com/faq>
- `async_rithmic` docs (best public R|Protocol reference — connection, market data):
  <https://async-rithmic.readthedocs.io/en/latest/connection.html>,
  <https://async-rithmic.readthedocs.io/en/latest/realtime_data.html>
- `pyrithmic` (Python protobuf-API reference): <https://github.com/jacksonwoody/pyrithmic>
- `rithmic-rs` (Rust, candidate client): <https://github.com/pbeets/rithmic-rs> ·
  <https://crates.io/crates/rithmic-rs>
- `ff_rithmic_api` (Rust, stale reference): <https://github.com/BurnOutTrader/ff_rithmic_api>
- Conformance test explainer: <https://www.quantlabsnet.com/post/what-is-a-rithmic-api-conformance-test>
- Broker/entitlement context (AMP, Ironbeam, EdgeClear): <https://www.ampfutures.com/trading-platform/rithmic-r-api>,
  <https://www.ironbeam.com/rithmic-api-futures-trading/>, <https://edgeclear.com/rithmic/>

---

*Companion to [`WEBUI_PLATFORM_ROADMAP.md`](WEBUI_PLATFORM_ROADMAP.md) (P11/P12)
and [`PLATFORM_ARCHITECTURE.md`](PLATFORM_ARCHITECTURE.md). Research + design
only — no code, no scheduling commitment, no execution.*
