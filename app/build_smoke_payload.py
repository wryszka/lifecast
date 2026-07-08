"""Build the /api/content payload shape offline for route_smoke.mjs — no
workspace, no auth. Mirrors app.py's content() with a stub link resolver.
Usage: python3 app/build_smoke_payload.py [/tmp/content_test.json]
"""
import json
import sys

sys.path.insert(0, "app")
import content  # noqa: E402


def link(key: str) -> str:
    return "https://smoke.invalid/" + key.replace(":", "/")


flows = []
for f in content.FLOWS:
    swaps = [{"old": sw["old"], "new": sw["new"],
              "links": [{"label": l, "url": link(k)} for l, k in sw["links"]],
              **({"peek": {"label": sw["peek"][0], "hash": sw["peek"][1]}} if "peek" in sw else {})}
             for sw in f["tab2"]["swaps"]]
    h = f["tab2"]["handoff"]
    flows.append({
        "id": f["id"], "eyebrow": f["eyebrow"], "title": f["title"], "use_for": f["use_for"],
        "skeleton": f["skeleton"], "tab1": f["tab1"],
        "tab2": {"lead": f["tab2"]["lead"], "swaps": swaps, "scope": f["tab2"]["scope"],
                 "handoff": {"ours": h["ours"], "theirs": h["theirs"], "text": h["text"],
                             "next_label": h["next_label"], "next_url": link(h["next_link"])}},
        "tab3": {"lead": f["tab3"]["lead"], "run_help": f["tab3"]["run_help"],
                 "agent": {**f["tab3"]["agent"], "genie_url": link("genie_runhealth")}},
        "beat": f["beat"],
    })

personas = [{**p, "cards": [{
    "id": c["id"], "question": c["question"], "proves": c["proves"],
    "where": [{"label": l, "url": link(k)} for l, k in c["where"]],
    "build": c["build"],
    "links": [{"label": l, "url": link(k)} for l, k in c["links"]],
    "today": c["today"], "tomorrow": c["tomorrow"],
} for c in content.CARDS[p["id"]]]} for p in content.PERSONAS]

payload = {
    "tiles": [{**{k: v for k, v in t.items() if k != "link"},
               **({"url": link(t["link"])} if "link" in t else {})} for t in content.TILES],
    "flows": flows, "personas": personas,
    "terms": [{"term": t, "text": x} for t, x in content.TERMS],
    "poc": content.POC_PLAN,
    "blocks": {k: {**b, "assets": [{"label": l, "url": link(kk),
                                    "kind": kk.partition(":")[0]} for l, kk in b["assets"]]}
               for k, b in content.BLOCKS.items()},
    "gov_showcase": content.GOV_SHOWCASE, "gov_agent": content.GOV_AGENT,
    "roadmap": content.ROADMAP, "ai": content.AI_PAGE, "learn": content.LEARN,
    "demo_guide": "https://smoke.invalid/demo-guide",
    "host": "https://smoke.invalid", "catalog": "smoke_catalog",
}
out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/content_test.json"
json.dump(payload, open(out, "w"))
print(f"offline payload -> {out} ({len(json.dumps(payload))//1024} KB)")
