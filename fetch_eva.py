import csv, io, json, os, urllib.request
from collections import defaultdict
from datetime import datetime, timezone

RESOURCE_ID = "76f6831d-fac7-4c1f-8313-cc7ff238ddca"
RESOURCE_PAGE = "https://data.virginia.gov/dataset/eva-procurement-data-2026-virginia/resource/" + RESOURCE_ID
API = "https://data.virginia.gov/api/3/action/package_show?id=eva-procurement-data-2026-virginia"
TARGETS = {"roanoke","salem","blacksburg","christiansburg","radford","pulaski","wytheville","austinville"}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent":"VA-Opportunity-Radar/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def resource_url():
    try:
        obj = json.loads(get(API))
        for r in obj.get("result", {}).get("resources", []):
            if r.get("id") == RESOURCE_ID and r.get("url"):
                return r["url"]
    except Exception as e:
        print("CKAN metadata lookup failed:", e)
    return RESOURCE_PAGE + "/download"

def money(v):
    try:
        return float(str(v).replace("$", "").replace(",", "").strip() or 0)
    except Exception:
        return 0.0

def main():
    raw = get(resource_url())
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    orders = defaultdict(lambda: {"total":0.0, "items":[], "row":None})

    for row in reader:
        hay = " ".join([
            (row.get("Shipping City") or "").lower(),
            (row.get("Entity Description") or "").lower(),
            (row.get("Vendor Address City") or "").lower(),
        ])
        if not any(t in hay for t in TARGETS):
            continue
        order = (row.get("Order #") or "").strip()
        if not order:
            continue
        o = orders[order]
        o["row"] = o["row"] or row
        o["total"] += money(row.get("Line Total"))
        desc = (row.get("Item Description") or row.get("NIGP Description") or "").strip()
        if desc and desc not in o["items"] and len(o["items"]) < 3:
            o["items"].append(desc)

    signals = []
    for order, o in orders.items():
        r = o["row"]
        city = (r.get("Shipping City") or r.get("Vendor Address City") or "Virginia").title()
        signals.append({
            "kind":"spend",
            "place":city,
            "title":(r.get("Entity Description") or "Virginia buyer").strip(),
            "desc":"; ".join(o["items"])[:300] or (r.get("NIGP Description") or "Procurement purchase order"),
            "meta":"eVA order " + order + " • " + (r.get("Ordered Date") or "date unavailable"),
            "score":("$" + format(o["total"], ",.0f")) if o["total"] else "Spend",
            "amount":round(o["total"], 2),
            "order":order,
            "vendor":(r.get("Vendor Name") or "").strip(),
            "source":RESOURCE_PAGE,
        })

    signals.sort(key=lambda x: x["amount"], reverse=True)
    payload = {
        "updated":datetime.now(timezone.utc).isoformat(),
        "source":RESOURCE_PAGE,
        "count":len(signals),
        "signals":signals[:250],
    }
    os.makedirs("data", exist_ok=True)
    with open("data/signals.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("Wrote", len(payload["signals"]), "signals")

if __name__ == "__main__":
    main()
