import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

SOURCE_URL = "https://www.salemva.gov/Bids.aspx"

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
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
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")

def text_from_html(html):
    parser = TextParser()
    parser.feed(html)
    return " ".join(parser.parts)

def extract_bid_ids(html):
    ids = re.findall(
        r'[?&]bidID=(\d+)',
        html,
        flags=re.IGNORECASE
    )
    return sorted(set(ids), key=int, reverse=True)

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

    return value[:stop].strip(" :-")

def parse_bid(bid_id):
    url = f"https://www.salemva.gov/bids.aspx?bidID={bid_id}"
    html = get_html(url)
    text = text_from_html(html)

    number = grab(
        text,
        "Bid Number:",
        ["Bid Title:", "Category:"]
    )

    title = grab(
        text,
        "Bid Title:",
        ["Category:", "Status:"]
    )

    status = grab(
        text,
        "Status:",
        ["Description:", "Publication Date/Time:"]
    )

    published = grab(
        text,
        "Publication Date/Time:",
        ["Closing Date/Time:"]
    )

    closing = grab(
        text,
        "Closing Date/Time:",
        [
            "Bid Opening Information:",
            "Pre-bid Meeting:",
            "Contact Person:",
            "Related Documents:",
            "Return To Main"
        ]
    )

    description = grab(
        text,
        "Description:",
        ["Publication Date/Time:"]
    )

    if len(description) > 600:
        description = description[:597] + "..."

    if status.lower() != "open":
        return None

    return {
        "kind": "opportunity",
        "place": "Salem",
        "agency": "City of Salem",
        "title": title or "Untitled solicitation",
        "solicitation": number,
        "status": status,
        "published": published,
        "closing": closing,
        "desc": description,
        "source": url,
    }

def main():
    print("Checking City of Salem solicitations...")

    index_html = get_html(SOURCE_URL)
    bid_ids = extract_bid_ids(index_html)

    print("Found", len(bid_ids), "bid links")

    opportunities = []

    for bid_id in bid_ids:
        try:
            item = parse_bid(bid_id)
            if item:
                opportunities.append(item)
                print(
                    "OPEN:",
                    item["solicitation"],
                    item["title"]
                )
        except Exception as exc:
            print("Skipped bid", bid_id, ":", exc)

    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_URL,
        "count": len(opportunities),
        "opportunities": opportunities,
    }

    os.makedirs("data", exist_ok=True)

    with open(
        "data/opportunities.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            payload,
            f,
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
