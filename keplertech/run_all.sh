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
check 3 "2d734efb2 fix reported as a behavior change" iob_axi2iob 2d734efb2 k_induction 8

exit $FAIL
