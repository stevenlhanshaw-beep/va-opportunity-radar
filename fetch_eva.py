import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

RESOURCE_ID = "76f6831d-fac7-4c1f-8313-cc7ff238ddca"
API = "https://data.virginia.gov/api/3/action/datastore_search"
RESOURCE_PAGE = (
    "https://data.virginia.gov/dataset/"
    "eva-procurement-data-2026-virginia/resource/"
    + RESOURCE_ID
)

TARGETS = [
    "roanoke",
    "salem",
    "blacksburg",
    "christiansburg",
    "radford",
    "pulaski",
    "wytheville",
    "austinville",
]

SEARCH_FIELDS = [
    "Shipping City",
    "Entity Description",
    "Vendor Address City",
]


def api_get(params):
    url = API + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "VA-Opportunity-Radar/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def money(value):
    try:
        return float(
            str(value or "0")
            .replace("$", "")
            .replace(",", "")
            .strip()
            or 0
        )
    except (TypeError, ValueError):
        return 0.0


def fetch_target_records():
    records = []
    seen_ids = set()

    for target in TARGETS:
        print("Querying:", target)

        obj = api_get(
            {
                "resource_id": RESOURCE_ID,
                "q": target,
                "limit": 5000,
            }
        )

        if not obj.get("success"):
            raise RuntimeError("Virginia Data API returned an error")

        result = obj.get("result", {})

        print(
            "  matches reported:",
            result.get("total", 0),
        )

        for row in result.get("records", []):
            haystack = " ".join(
                str(row.get(field) or "").lower()
                for field in SEARCH_FIELDS
            )

            if target not in haystack:
                continue

            row_id = row.get("_id")

            if row_id in seen_ids:
                continue

            seen_ids.add(row_id)
            records.append(row)

    return records


def build_signals(records):
    orders = defaultdict(
        lambda: {
            "total": 0.0,
            "items": [],
            "row": None,
        }
    )

    for row in records:
        order = str(row.get("Order #") or "").strip()

        if not order:
            continue

        item = orders[order]

        if item["row"] is None:
            item["row"] = row

        item["total"] += money(row.get("Line Total"))

        description = str(
            row.get("Item Description")
            or row.get("NIGP Description")
            or ""
        ).strip()

        if (
            description
            and description not in item["items"]
            and len(item["items"]) < 3
        ):
            item["items"].append(description)

    signals = []

    for order, item in orders.items():
        row = item["row"]

        city = str(
            row.get("Shipping City")
            or row.get("Vendor Address City")
            or "Virginia"
        ).strip().title()

        entity = str(
            row.get("Entity Description")
            or "Virginia buyer"
        ).strip()

        description = "; ".join(item["items"])[:300]

        if not description:
            description = str(
                row.get("NIGP Description")
                or "Procurement purchase order"
            ).strip()

        ordered_date = str(
            row.get("Ordered Date")
            or "date unavailable"
        ).strip()

        vendor = str(
            row.get("Vendor Name")
            or ""
        ).strip()

        total = round(item["total"], 2)

        signals.append(
            {
                "kind": "spend",
                "place": city,
                "title": entity,
                "desc": description,
                "meta": f"eVA order {order} • {ordered_date}",
                "score": (
                    "$" + format(total, ",.0f")
                    if total
                    else "Spend"
                ),
                "amount": total,
                "order": order,
                "vendor": vendor,
                "source": RESOURCE_PAGE,
            }
        )

    signals.sort(
        key=lambda signal: signal["amount"],
        reverse=True,
    )

    return signals


def main():
    records = fetch_target_records()

    print("Relevant API records:", len(records))

    signals = build_signals(records)

    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": RESOURCE_PAGE,
        "record_count": len(records),
        "count": len(signals),
        "signals": signals[:250],
    }

    os.makedirs("data", exist_ok=True)

    with open(
        "data/signals.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        "Wrote",
        len(payload["signals"]),
        "spend signals",
    )


if __name__ == "__main__":
    main()
