#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2026 keplertech.io
#
# SPDX-License-Identifier: Apache-2.0

# Replays the counterexample of a previous sec_commit.sh run in Icarus Verilog,
# on both generated versions, and prints the outputs that differ per cycle.
#
# Usage: keplertech/replay_cex.sh <core> <commit>
# Uses the same RESET_PORTS and RESET_CYCLES as sec_commit.sh (set them to the
# same values). Requires iverilog and vvp on PATH.
# Exit code: 0 if the simulation confirms an output difference, 1 otherwise.

set -euo pipefail

CORE=$1
COMMIT=$2
PYTHON=${PYTHON:-python3}
RESET_PORTS=${RESET_PORTS:-arst_i=1}
RESET_CYCLES=${RESET_CYCLES:-4}

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(git -C "$HERE" rev-parse --show-toplevel)
SHORT=$(git -C "$REPO" rev-parse --short "$COMMIT")
WORK=$REPO/keplertech/work/${CORE}_${SHORT}
LOG=$WORK/kepler-formal.log
SIM=$WORK/replay
mkdir -p "$SIM"

grep -q "Counterexample reaches" "$LOG" || {
    echo "   no counterexample in ${LOG#$REPO/}; run sec_commit.sh first"
    exit 1
}

"$PYTHON" "$HERE/replay_cex.py" tb "$LOG" \
    "$WORK/gen_design1/build/hardware/src/$CORE.v" "$CORE" \
    "$RESET_CYCLES" "$RESET_PORTS" "$SIM/replay_tb.v"

for side in design1 design2; do
    src=$WORK/gen_$side/build/hardware/src
    iverilog -g2012 -o "$SIM/$side.vvp" -I "$src" "$SIM/replay_tb.v" "$src"/*.v \
        2>"$SIM/iverilog_$side.log"
    vvp -n "$SIM/$side.vvp" >"$SIM/sim_$side.txt"
done

echo "== replay in Icarus Verilog: $CORE $SHORT^ (design 1) vs $SHORT (design 2)"
"$PYTHON" "$HERE/replay_cex.py" compare "$SIM/sim_design1.txt" "$SIM/sim_design2.txt"
