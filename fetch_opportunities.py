
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser


SOURCES = [
    {
        "place": "Salem",
        "agency": "City of Salem",
        "base": "https://www.salemva.gov",
        "index": "https://www.salemva.gov/Bids.aspx",
    },
    {
        "place": "Christiansburg",
        "agency": "Town of Christiansburg",
        "base": "https://www.christiansburg.org",
        "index": "https://www.christiansburg.org/bids.aspx",
    },
]


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script", "style"):
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style"):
            if self.skip_depth:
                self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            return

        text = data.strip()

        if text:
            self.parts.append(text)


def get_html(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "VA-Opportunity-Radar/1.0",
            "Accept": "text/html",
        },
    )

    with urllib.request.urlopen(
        req,
        timeout=60
    ) as response:
        return response.read().decode(
            "utf-8",
            errors="replace"
        )


def text_from_html(html):
    parser = TextParser()
    parser.feed(html)

    return " ".join(parser.parts)


def clean_text(value):
    value = unescape(str(value or ""))

    value = re.sub(
        r"<!--.*?-->",
        " ",
        value,
        flags=re.DOTALL
    )

    value = re.sub(
        r"\barrEmail\d*\b.*",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip(" :-")


def extract_bid_ids(html):
    ids = re.findall(
        r'[?&]bidID=(\d+)',
        html,
        flags=re.IGNORECASE
    )

    return sorted(
        set(ids),
        key=int,
        reverse=True
    )


def grab(text, start, ends):
    pos = text.find(start)

    if pos == -1:
        return ""

    value = text[pos + len(start):]

    stop = len(value)

    for end in ends:
        p = value.find(end)

        if p != -1:
            stop = min(stop, p)

    return clean_text(value[:stop])


def parse_bid(source, bid_id):
    url = (
        source["base"]
        + "/bids.aspx?bidID="
        + str(bid_id)
    )

    html = get_html(url)
    text = text_from_html(html)

    number = grab(
        text,
        "Bid Number:",
        [
            "Bid Title:",
            "Category:",
        ]
    )

    title = grab(
        text,
        "Bid Title:",
        [
            "Category:",
            "Status:",
        ]
    )

    category = grab(
        text,
        "Category:",
        [
            "Status:",
            "Description:",
        ]
    )

    status = grab(
        text,
        "Status:",
        [
            "Description:",
            "Publication Date/Time:",
        ]
    )

    description = grab(
        text,
        "Description:",
        [
            "Publication Date/Time:",
        ]
    )

    published = grab(
        text,
        "Publication Date/Time:",
        [
            "Closing Date/Time:",
        ]
    )

    closing = grab(
        text,
        "Closing Date/Time:",
        [
            "Bid Opening Information:",
            "Pre-bid Meeting:",
            "Contact Person:",
            "Related Documents:",
            "Return To Main",
        ]
    )

    if status.lower() != "open":
        return None

    if not title:
        return None

    if len(description) > 500:
        description = (
            description[:497].rstrip()
            + "..."
        )

    return {
        "kind": "opportunity",
        "place": source["place"],
        "agency": source["agency"],
        "title": title,
        "solicitation": number,
        "category": category,
        "status": status,
        "published": published,
        "closing": closing,
        "desc": description,
        "source": url,
    }


def collect_source(source):
    print(
        "Checking",
        source["agency"],
        "open solicitations..."
    )

    html = get_html(source["index"])
    bid_ids = extract_bid_ids(html)

    print(
        "Found",
        len(bid_ids),
        "bid links for",
        source["agency"]
    )

    opportunities = []

    for bid_id in bid_ids:
        try:
            item = parse_bid(
                source,
                bid_id
            )

            if item:
                opportunities.append(item)

                print(
                    "OPEN:",
                    source["place"],
                    item["solicitation"],
                    "-",
                    item["title"]
                )

        except Exception as exc:
            print(
                "Skipped",
                source["place"],
                "bid",
                bid_id,
                ":",
                exc
            )

    return opportunities


def main():
    opportunities = []
    source_results = []

    for source in SOURCES:
        try:
            items = collect_source(source)

            opportunities.extend(items)

            source_results.append({
                "agency": source["agency"],
                "place": source["place"],
                "source": source["index"],
                "count": len(items),
                "status": "ok",
            })

        except Exception as exc:
            print(
                "Source failed:",
                source["agency"],
                ":",
                exc
            )

            source_results.append({
                "agency": source["agency"],
                "place": source["place"],
                "source": source["index"],
                "count": 0,
                "status": "error",
                "error": str(exc),
            })

    opportunities.sort(
        key=lambda item: (
            item["place"].lower(),
            item["title"].lower(),
            item["solicitation"]
        )
    )

    payload = {
        "updated": datetime.now(
            timezone.utc
        ).isoformat(),
        "count": len(opportunities),
        "sources": source_results,
        "opportunities": opportunities,
    }

    os.makedirs(
        "data",
        exist_ok=True
    )

    with open(
        "data/opportunities.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        "Wrote",
        len(opportunities),
        "open opportunity records"
    )


if __name__ == "__main__":
    main()
