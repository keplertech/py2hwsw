# SPDX-FileCopyrightText: 2026 keplertech.io
#
# SPDX-License-Identifier: Apache-2.0

"""Replay a kepler-formal SEC counterexample in simulation.

  replay_cex.py tb <kepler-formal.log> <top.v> <top> <reset_cycles> <reset_ports> <out_tb.v>
      Writes a self-checking-free testbench that applies the reset bootstrap,
      then the counterexample inputs cycle by cycle, and prints every output
      of <top> once per cycle.

  replay_cex.py compare <sim_design1.txt> <sim_design2.txt>
      Compares the two simulation transcripts and prints the outputs that
      differ, per cycle. Exit code 0 if they differ (counterexample confirmed),
      1 if they do not.

Inputs that the counterexample does not list are driven to 0. Outputs are
sampled after the cycle's inputs are applied and before the rising clock edge,
which is where SEC compares outputs within a frame.
"""

import re
import sys


def parse_trace(log):
    cycles = {}
    for line in open(log):
        m = re.match(r"\s*cycle (\d+): (.*)", line)
        if not m:
            continue
        vals = {}
        for item in m.group(2).split(", "):
            name, v = item.rsplit("=", 1)
            bm = re.match(r"([\w$]+)\[(\d+)\]$", name)
            if bm:
                vals.setdefault(bm.group(1), {})[int(bm.group(2))] = int(v)
            else:
                vals.setdefault(name, {})[0] = int(v)
        cycles[int(m.group(1))] = vals
    if not cycles:
        sys.exit(f"no counterexample cycles found in {log}")
    return cycles


def parse_top(path, top):
    """Return (params, ports) of module <top> from a Verilog file."""
    text = open(path).read()
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    m = re.search(r"\bmodule\s+" + top + r"\b(.*?)\);", text, flags=re.S)
    if not m:
        sys.exit(f"module {top} not found in {path}")
    header = m.group(1)
    params = {}
    for pm in re.finditer(r"parameter\s+(?:\w+\s+)?(\w+)\s*=\s*([^,\)]+)", header):
        params[pm.group(1)] = pm.group(2).strip()
    ports = []
    for pm in re.finditer(
        r"\b(input|output)\s+(?:wire|reg|logic)?\s*(\[[^\]]+\])?\s*(\w+)", header
    ):
        ports.append((pm.group(1), pm.group(2), pm.group(3)))
    return params, ports


def width_of(rng, params):
    if not rng:
        return 1
    msb, lsb = rng.strip("[]").split(":")
    env = {}
    for _ in range(4):  # resolve parameters that refer to other parameters
        for k, v in params.items():
            try:
                env[k] = int(eval(v.replace("/", "//"), {}, env))
            except Exception:
                pass
    try:
        return abs(int(eval(msb.replace("/", "//"), {}, env)) - int(eval(lsb, {}, env))) + 1
    except Exception:
        return 64  # unresolved width: simulator truncates or pads


def make_tb(log, top_v, top, reset_cycles, reset_ports, out):
    cycles = parse_trace(log)
    params, ports = parse_top(top_v, top)
    clk = next((n for d, _, n in ports if d == "input" and re.match(r"clk", n)), None)
    if clk is None:
        sys.exit("no clock input (clk*) found on the top module")
    ins = [(width_of(r, params), n) for d, r, n in ports if d == "input" and n != clk]
    outs = [(width_of(r, params), n) for d, r, n in ports if d == "output"]
    resets = dict(p.split("=") for p in reset_ports.split())

    L = ["`timescale 1ns/1ps", "module replay_tb;", f"  reg {clk} = 0;"]
    L += [f"  reg [{w - 1}:0] {n} = 0;" for w, n in ins]
    L += [f"  wire [{w - 1}:0] {n};" for w, n in outs]
    conns = [f"    .{clk}({clk})"] + [f"    .{n}({n})" for _, n in ins + outs]
    L += [f"  {top} dut (", ",\n".join(conns), "  );"]
    fmt = " ".join(f"{n}=%0h" for _, n in outs)
    args = ", ".join(n for _, n in outs)
    L.append("  initial begin")
    for port, active in resets.items():
        L.append(f"    {port} = {active};")
    L.append(f"    repeat ({reset_cycles}) begin #5 {clk} = 1; #5 {clk} = 0; end")
    for c in sorted(cycles):
        for w, n in ins:
            bits = cycles[c].get(n, {})
            L.append(f"    {n} = {w}'h{sum(b << i for i, b in bits.items()):x};")
        L.append("    #1;")
        L.append(f'    $display("cycle {c}: {fmt}", {args});')
        L.append(f"    #4 {clk} = 1; #5 {clk} = 0;")
    L += ["    $finish;", "  end", "endmodule"]
    open(out, "w").write("\n".join(L) + "\n")


def read_sim(path):
    res = {}
    for line in open(path):
        m = re.match(r"cycle (\d+): (.*)", line.strip())
        if m:
            res[int(m.group(1))] = dict(kv.split("=") for kv in m.group(2).split())
    return res


def compare(sim1, sim2):
    a, b = read_sim(sim1), read_sim(sim2)
    found = False
    for c in sorted(set(a) | set(b)):
        diffs = [
            (n, a[c].get(n), b.get(c, {}).get(n))
            for n in a.get(c, {})
            if a[c].get(n) != b.get(c, {}).get(n)
        ]
        if diffs:
            found = True
            print(f"   cycle {c}: " + ", ".join(f"{n} design1={x} design2={y}" for n, x, y in diffs))
    if not found:
        print(f"   no output difference in {len(a)} simulated cycles")
    return 0 if found else 1


if __name__ == "__main__":
    if sys.argv[1] == "tb":
        make_tb(*sys.argv[2:6], sys.argv[6], sys.argv[7])
    elif sys.argv[1] == "compare":
        sys.exit(compare(sys.argv[2], sys.argv[3]))
    else:
        sys.exit(__doc__)
