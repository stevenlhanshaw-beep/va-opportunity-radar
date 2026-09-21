import json
import os
import time
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
    "Roanoke",
    "Salem",
    "Blacksburg",
    "Christiansburg",
    "Radford",
    "Pulaski",
    "Wytheville",
    "Austinville",
]

CITY_FIELDS = [
    "Shipping_City",
    "Vendor_Address_City",
]


def api_get(params, retries=3):
    url = API + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "VA-Opportunity-Radar/1.0",
            "Accept": "application/json",
        },
    )

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(
                req, timeout=60
            ) as response:
                return json.loads(
                    response.read().decode("utf-8")
                )
        except Exception as exc:
            if attempt == retries - 1:
                raise

            print("Retrying after:", exc)
            time.sleep(3 * (attempt + 1))


def get_value(row, *names):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return ""


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


def fetch_records():
    records = []
    seen = set()

    for city in TARGETS:
        for field in CITY_FIELDS:
            print("Querying:", field, "=", city)

            filters = json.dumps({field: city})

            obj = api_get(
                {
                    "resource_id": RESOURCE_ID,
                    "filters": filters,
                    "limit": 1000,
                }
            )

            if not obj.get("success"):
                print("API query unsuccessful")
                continue

            result = obj.get("result", {})
            rows = result.get("records", [])

            print(
                "  returned:",
                len(rows),
                "of",
                result.get("total", len(rows)),
            )

            for row in rows:
                row_id = row.get("_id")

                if row_id in seen:
                    continue

                seen.add(row_id)
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
        order = str(
            get_value(
                row,
                "Order_#",
                "Order #",
                "Order_Number",
            )
        ).strip()

        if not order:
            continue

        item = orders[order]

        if item["row"] is None:
            item["row"] = row

        item["total"] += money(
            get_value(
                row,
                "Line_Total",
                "Line Total",
            )
        )

        description = str(
            get_value(
                row,
                "Item_Description",
                "Item Description",
                "NIGP_Description",
                "NIGP Description",
            )
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
            get_value(
                row,
                "Shipping_City",
                "Shipping City",
                "Vendor_Address_City",
                "Vendor Address City",
            )
            or "Virginia"
        ).strip().title()

        entity = str(
            get_value(
                row,
                "Entity_Description",
                "Entity Description",
            )
            or "Virginia buyer"
        ).strip()

        description = "; ".join(item["items"])[:300]

        if not description:
            description = str(
                get_value(
                    row,
                    "NIGP_Description",
                    "NIGP Description",
                )
                or "Procurement purchase order"
            ).strip()

        ordered_date = str(
            get_value(
                row,
                "Ordered_Date",
                "Ordered Date",
            )
            or "date unavailable"
        ).strip()

        vendor = str(
            get_value(
                row,
                "Vendor_Name",
                "Vendor Name",
            )
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
        key=lambda x: x["amount"],
        reverse=True,
    )

    return signals


def main():
    records = fetch_records()

    print("Relevant records:", len(records))

    signals = build_signals(records)

    payload = {
        "updated": datetime.now(
            timezone.utc
        ).isoformat(),
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
