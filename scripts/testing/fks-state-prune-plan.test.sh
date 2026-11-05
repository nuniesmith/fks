#!/usr/bin/env bash
# Tests for fks-state.sh's release retention (_prune_plan): which snapshot
# releases a run deletes. A wrong answer deletes real backups, so every rule
# is pinned here.  Run: scripts/testing/fks-state-prune-plan.test.sh
set -euo pipefail
S="$(cd "$(dirname "$0")/.." && pwd)/fks-state.sh"
plan() { "$S" _prune-plan "$1"; }
fail=0
check() { # name expected actual
  if [[ "$2" == "$3" ]]; then echo "ok   $1"; else echo "FAIL $1"; echo "  expected: [$2]"; echo "  actual:   [$3]"; fail=1; fi
}
day() { date -u -d "$1" +snapshot-%Y%m%dT130000Z; }

# 1. Fewer than keep: nothing goes.
tags="$(for d in 2026-11-01 2026-11-02 2026-11-03; do day $d; done)"
check "under the limit deletes nothing" "" "$(printf '%s\n' "$tags" | plan 30)"

# 2. 40 consecutive days, keep 30: the 10 oldest go, because their month
#    (October) already has a newer kept snapshot.
tags="$(for i in $(seq 0 39); do day "2026-10-01 +$i days"; done)"
want="$(for i in $(seq 9 -1 0); do day "2026-10-01 +$i days"; done)"
check "keeps newest 30, drops older same-month" "$want" "$(printf '%s\n' "$tags" | plan 30)"

# 3. Monthly keepers survive outside the window: newest of each month, forever.
tags="$(for d in 2026-07-03 2026-07-29 2026-08-02 2026-08-31 2026-09-20 2026-10-27 2026-11-03 2026-11-04; do day $d; done)"
want="$(for d in 2026-08-02 2026-07-03; do day $d; done)"
check "newest per month kept (07-29, 08-31, 09-20, 10-27)" "$want" "$(printf '%s\n' "$tags" | plan 2)"

# 4. Input order does not matter.
check "order independent" "$want" "$(printf '%s\n' "$tags" | sort -R | plan 2)"

# 5. Anything that is not a snapshot tag is never deleted.
tags="$(printf '%s\n' v1.0 snapshot-latest snapshot-2026110 "$(day 2026-11-01)" "$(day 2026-11-02)" "$(day 2026-11-03)")"
# keep 1: 11-03 kept; 11-02 and 11-01 share its month, so both go; the
# three odd tags stay.
check "non-snapshot tags never deleted" "$(printf '%s\n' "$(day 2026-11-02)" "$(day 2026-11-01)")" "$(printf '%s\n' "$tags" | plan 1)"

# 6. keep 0 still keeps one per month.
tags="$(for d in 2026-11-01 2026-11-02 2026-10-05; do day $d; done)"
check "keep 0 keeps month keepers only" "$(day 2026-11-01)" "$(printf '%s\n' "$tags" | plan 0)"

# 7. Two snapshots on a month's last day: the later one is the month keeper.
tags="$(printf '%s\n' snapshot-20261031T202048Z snapshot-20261031T202131Z snapshot-20261103T130144Z)"
check "same-day duplicates: later one keeps the month" "snapshot-20261031T202048Z" "$(printf '%s\n' "$tags" | plan 1)"

# 8. Empty input.
check "empty input" "" "$(printf '' | plan 30)"

exit $fail
