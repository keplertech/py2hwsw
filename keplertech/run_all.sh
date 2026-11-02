#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2026 keplertech.io
#
# SPDX-License-Identifier: Apache-2.0

# Reproduces the two kepler-formal RTL SEC results described in keplertech/README.md
# and checks that each verdict is the expected one.
#
# Usage: keplertech/run_all.sh
# Environment: KEPLER_FORMAL, PYTHON (see keplertech/sec_commit.sh)

set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
FAIL=0

check() {
    # $1 = expected exit code, $2 = label, remaining = sec_commit.sh arguments
    local expected=$1 label=$2
    shift 2
    local start=$SECONDS
    "$HERE/sec_commit.sh" "$@"
    local status=$?
    local elapsed=$((SECONDS - start))
    if [ "$status" -eq "$expected" ]; then
        echo "   PASS: $label (${elapsed}s including generation)"
    else
        echo "   FAIL: $label, expected exit $expected, got $status"
        FAIL=1
    fi
    echo
}

# 1. Warning cleanup, intended to keep behavior: expect a proof.
check 0 "e0434c789 cleanup proved equivalent" iob_axi2iob e0434c789 pdr

# 2. rvalid/rdata register fix, a real behavior change: expect a counterexample.
#    cke_i=0 as a reset port holds the clock enable at 0 during reset and at 1
#    afterwards, so the counterexample uses normal operation only.
export RESET_PORTS="arst_i=1 cke_i=0"
check 3 "2d734efb2 fix reported as a behavior change" iob_axi2iob 2d734efb2 k_induction 8

# 3. Replay that counterexample in Icarus Verilog, when it is installed.
if command -v iverilog >/dev/null 2>&1 && command -v vvp >/dev/null 2>&1; then
    if "$HERE/replay_cex.sh" iob_axi2iob 2d734efb2; then
        echo "   PASS: counterexample confirmed in simulation"
    else
        echo "   FAIL: simulation does not show the difference"
        FAIL=1
    fi
else
    echo "== replay skipped: iverilog not installed"
fi

exit $FAIL
