"""
drosophila_connectome / demo.py
-------------------------------
Sanity-check the query layer against known ground-truth numbers from the
MaleCNS v1.0 paper / precomputed facts. Run WITHOUT an MCP client:

    python -m mcp_connectome.demo
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core

PASS = 0
FAIL = 0


def check(label, got, expect):
    global PASS, FAIL
    ok = (got == expect)
    if ok:
        PASS += 1
        print("[PASS] %s = %s" % (label, got))
    else:
        FAIL += 1
        print("[FAIL] %s: got %s, expected %s" % (label, got, expect))


def show(title, text):
    print("\n==== %s ====" % title)
    print(text)


def main():
    core.ensure_cache(verbose=True)

    # 1) Overview totals
    ov = core.connectome_overview()
    show("connectome_overview", _fmt_overview(ov))
    check("total_synapses", ov["total_synapses"], 124177617)

    # 2) APL -> DPM: paper/facts say 711 synapses (strongest target of APL)
    apl_body = 10540  # APL body id from facts
    dpm = 12569       # DPM body id from facts
    dpm_syn = core.pair_synapses(apl_body, dpm)
    show("pair_synapses(APL->DPM)", "APL(10540) -> DPM(12569) = %d 突触" % dpm_syn)
    check("APL->DPM synapses", dpm_syn, 711)

    # 3) neuron_info for APL
    info = core.neuron_info(apl_body)
    show("neuron_info(APL)", _fmt_info(info))
    check("APL fan_out", info["fan_out"], 102263)
    check("APL fan_in", info["fan_in"], 119935)

    # 4) neuron_outputs top target of APL should be DPM at 711
    outs = core.neuron_outputs(apl_body, top=3)
    show("neuron_outputs(APL) top3", "\n".join("  %s -> %d" % (core._label(b), s) for b, s in outs))
    check("APL top target is DPM", outs[0][0], dpm)

    # 5) superclass_projection for mushroom_body
    sp = core.superclass_projection("mushroom_body")
    show("superclass_projection(mushroom_body)", _fmt_sp(sp))

    # 6) hub_targets CT1
    ht = core.hub_targets("CT1")
    show("hub_targets(CT1)", _fmt_hub(ht))
    check("CT1 exists", ht is not None, True)

    # 7) pathway APL -> DPM should be 1 hop
    pw = core.pathway(apl_body, dpm)
    show("pathway(APL->DPM)", str(pw))
    check("pathway APL->DPM hops", pw["hops"], 1)

    # 8) search_neurons
    res = core.search_neurons("APL", field="type", limit=5)
    show("search_neurons(APL)", "\n".join("  body %d %s" % (b, r.get("type")) for b, r in res))

    print("\n==== RESULT: %d passed, %d failed ====" % (PASS, FAIL))
    return 1 if FAIL else 0


# ---- tiny formatters mirroring server.py ----
def _fmt_overview(o):
    return ("数据集 %s\n注释神经元 %d\n总突触 %d\n平均发出 %.1f / 接收 %.1f" % (
        o["dataset"], o["annotated_neurons"], o["total_synapses"],
        o["mean_fanout"], o["mean_fanin"]))


def _fmt_info(r):
    if not r:
        return "未找到"
    return "\n".join("%s: %s" % (k, r[k]) for k in
                     ["type", "superclass", "neurotransmitter", "fan_out", "fan_in"])


def _fmt_sp(sp):
    lines = ["superclass %s" % sp["superclass"]]
    if sp["io"]:
        lines.append("  神经元 %d, 发出 %d, 接收 %d" % (
            sp["io"]["n_neurons"], sp["io"]["out_synapses"], sp["io"]["in_synapses"]))
    return "\n".join(lines)


def _fmt_hub(h):
    if not h:
        return "未找到"
    return "%s (body %d): %d 突触; top target %s" % (
        h["hub_type"], h["hub_body"], h["hub_total_synapses"], h["top_targets"][0])


if __name__ == "__main__":
    sys.exit(main())
