import argparse
import csv
import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.hilife.com.tw/storeInquiry_street.aspx"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class StoreRecord:
    store_id: str
    store_name: str
    city: str
    district: str
    address: str
    phone: Optional[str]
    services: List[str]


def create_session() -> requests.Session:
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer": BASE_URL,
    })
    return session


def parse_webforms_state(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    state_fields = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        tag = soup.find("input", {"name": name})
        if tag and tag.has_attr("value"):
            state_fields[name] = tag["value"]
    # ASP.NET often needs the hidden field __EVENTTARGET and __EVENTARGUMENT present (even if empty)
    state_fields.setdefault("__EVENTTARGET", "")
    state_fields.setdefault("__EVENTARGUMENT", "")
    return state_fields


def find_dropdown_names(html: str) -> Tuple[str, str, Optional[str]]:
    """
    Attempt to detect the names/ids of the city and area dropdowns and optional submit button.
    Returns: (city_name, area_name, submit_name_or_None)
    """
    soup = BeautifulSoup(html, "html.parser")

    def detect(name_keywords: Iterable[str]) -> Optional[str]:
        for sel in ["select", "input", "button"]:
            for el in soup.select(sel):
                candidate = el.get("name") or el.get("id") or ""
                lower = candidate.lower()
                if any(key in lower for key in name_keywords):
                    return el.get("name") or el.get("id")
        return None

    city_name = detect(["city", "ddlcity"]) or "CITY"
    area_name = detect(["area", "ddldistrict", "district"]) or "AREA"

    # Try to find a submit/search control; if not present, area dropdown change usually triggers results
    submit_name = None
    for el in soup.select("input[type=submit], button[type=submit], input[type=button]"):
        text = (el.get("value") or el.text or "").strip()
        name_or_id = el.get("name") or el.get("id")
        if not name_or_id:
            continue
        # Match typical Chinese labels for search/confirm
        if any(k in text for k in ["查詢", "搜尋", "Search", "確定"]):
            submit_name = name_or_id
            break

    return city_name, area_name, submit_name


def parse_city_options(html: str, city_name: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", {"name": city_name}) or soup.find("select", {"id": city_name})
    options: List[Tuple[str, str]] = []
    if not select:
        return options
    for opt in select.find_all("option"):
        value = (opt.get("value") or "").strip()
        label = (opt.text or "").strip()
        if not value:
            continue
        options.append((value, label))
    return options


def parse_area_options(html: str, area_name: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", {"name": area_name}) or soup.find("select", {"id": area_name})
    options: List[Tuple[str, str]] = []
    if not select:
        return options
    for opt in select.find_all("option"):
        value = (opt.get("value") or "").strip()
        label = (opt.text or "").strip()
        if not value:
            continue
        options.append((value, label))
    return options


def postback(session: requests.Session, current_html: str, target_control: str, payload_overrides: Dict[str, str]) -> str:
    state = parse_webforms_state(current_html)
    form_data: Dict[str, str] = {**state}

    # Simulate __doPostBack if target_control is provided
    if target_control:
        form_data["__EVENTTARGET"] = target_control
        form_data.setdefault("__EVENTARGUMENT", "")

    # Merge user-specified fields (dropdown selections etc.)
    form_data.update(payload_overrides)

    resp = session.post(BASE_URL, data=form_data, timeout=20)
    resp.raise_for_status()
    return resp.text


def fetch_initial(session: requests.Session) -> str:
    resp = session.get(BASE_URL, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_store_rows(html: str, city_label: str, area_label: str) -> List[StoreRecord]:
    soup = BeautifulSoup(html, "html.parser")

    # The site renders a table-like list; each row appears to contain: id | name | address+services | phone
    # We'll search rows in common containers and parse columns robustly.
    records: List[StoreRecord] = []

    # Try semantic: find all rows with four columns
    candidates = []
    for table in soup.find_all(["table", "tbody"]):
        for tr in table.find_all("tr"):
            tds = tr.find_all(["td", "th"], recursive=False)
            if len(tds) == 4:
                candidates.append(tds)

    # Fallback: sometimes rows are separated by hr or divs; include those if needed later

    for cols in candidates:
        store_id = cols[0].get_text(strip=True)
        store_name = cols[1].get_text(strip=True)

        # Address column contains an anchor to Google Maps and service icons (img with title)
        address_anchor = cols[2].find("a")
        address = address_anchor.get_text(strip=True) if address_anchor else cols[2].get_text(" ", strip=True)

        phone_text = cols[3].get_text(strip=True) or None

        services: List[str] = []
        for img in cols[2].find_all("img"):
            title = img.get("title") or img.get("alt")
            if title:
                services.append(title.strip())

        # Skip header separator row like | ---- | ------ |
        if all(s.replace("-", "").strip() == "" for s in [store_id, store_name]) and address.startswith("http"):
            continue
        if store_id == "----":
            continue

        # Basic sanity
        if not store_id.isdigit() or not store_name:
            continue

        records.append(
            StoreRecord(
                store_id=store_id,
                store_name=store_name,
                city=city_label,
                district=area_label,
                address=address,
                phone=phone_text,
                services=services,
            )
        )

    return records


def scrape(all_cities: bool = False, delay_sec: float = 0.8, city_filter: Optional[str] = None, area_filter: Optional[str] = None) -> List[StoreRecord]:
    session = create_session()
    html = fetch_initial(session)
    city_name, area_name, submit_name = find_dropdown_names(html)

    cities = parse_city_options(html, city_name)
    if not cities:
        raise RuntimeError("Could not locate city dropdown options.")

    results: List[StoreRecord] = []

    for city_value, city_label in cities:
        if city_filter and city_filter not in (city_value, city_label):
            continue

        # Change city via postback so areas populate
        html = postback(
            session,
            html,
            target_control=city_name,
            payload_overrides={city_name: city_value},
        )

        areas = parse_area_options(html, area_name)
        if not areas:
            # Some pages may auto-populate after another postback; try once more with empty event target
            html = postback(
                session,
                html,
                target_control="",
                payload_overrides={city_name: city_value},
            )
            areas = parse_area_options(html, area_name)

        for area_value, area_label in areas:
            if area_filter and area_filter not in (area_value, area_label):
                continue

            # Select area; either area change triggers results or we click a search button
            html = postback(
                session,
                html,
                target_control=area_name,
                payload_overrides={city_name: city_value, area_name: area_value},
            )

            # If a submit button is required to render results, try submitting once
            if submit_name:
                html = postback(
                    session,
                    html,
                    target_control=submit_name,
                    payload_overrides={city_name: city_value, area_name: area_value},
                )

            page_records = parse_store_rows(html, city_label=city_label, area_label=area_label)
            results.extend(page_records)

            time.sleep(delay_sec)

        if not all_cities:
            # If not full run, stop after first city (or the filtered one)
            break

    return results


def write_json(path: str, records: List[StoreRecord]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)


def write_csv(path: str, records: List[StoreRecord]) -> None:
    fieldnames = ["store_id", "store_name", "city", "district", "address", "phone", "services"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = asdict(r)
            row["services"] = ", ".join(r.services)
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Hi-Life store information (WebForms).")
    parser.add_argument("--all", action="store_true", help="Scrape all cities and districts (full run)")
    parser.add_argument("--city", help="Filter to a specific city value or label", default=None)
    parser.add_argument("--area", help="Filter to a specific district value or label", default=None)
    parser.add_argument("--delay", type=float, default=0.8, help="Delay between requests (seconds)")
    parser.add_argument("--json", default="hilife_stores.json", help="Path to write JSON output")
    parser.add_argument("--csv", default="hilife_stores.csv", help="Path to write CSV output")
    args = parser.parse_args()

    records = scrape(all_cities=args.all, delay_sec=args.delay, city_filter=args.city, area_filter=args.area)
    write_json(args.json, records)
    write_csv(args.csv, records)
    print(f"Wrote {len(records)} records to {args.json} and {args.csv}")


if __name__ == "__main__":
    main()


