import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import pytz
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# Keep only a small sample here. Replace with your full map.
ASIN_KEYWORDS_MAP: Dict[str, Dict] = {
    "B0F8HXNY5N": {
        "name": "default",
        "zipcodes": ["90001", "75001", "32001"],
        "keywords": [
            {"keyword": "ryze mushroom hot cocoa"},
            {"keyword": "moonbrew"},
            {"keyword": "moon brew"},
            {"keyword": "sleep aid"},
        ],
    },
    "B0G64PSMX4": {
        "name": "default",
        "zipcodes": ["90001", "75001", "32001"],
        "keywords": [
            {"keyword": "javy protein coffee powder"},
            {"keyword": "protein coffee"},
            {"keyword": "chike high protein coffee"},
        ],
    },
}


def build_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def find_asin_rank_on_first_page(driver: webdriver.Chrome, keyword: str, asin: str) -> Optional[int]:
    url = f"https://www.amazon.com/s?k={quote_plus(keyword)}"
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-main-slot"))
        )
    except TimeoutException:
        return None

    items = driver.find_elements(By.CSS_SELECTOR, "div.s-main-slot div[data-component-type='s-search-result']")
    for idx, item in enumerate(items, start=1):
        if item.get_attribute("data-asin") == asin:
            return idx
    return None


def collect_records(timezone_name: str) -> List[Dict]:
    now = datetime.now(pytz.timezone(timezone_name))
    captured_at = now.isoformat()
    captured_date = now.strftime("%Y-%m-%d")

    rows: List[Dict] = []
    driver = build_driver(headless=True)
    try:
        for asin, meta in ASIN_KEYWORDS_MAP.items():
            account_name = meta.get("name", "default")
            zipcodes = meta.get("zipcodes", [])
            keywords = [x["keyword"] for x in meta.get("keywords", []) if x.get("keyword")]

            for zipcode in zipcodes:
                for keyword in keywords:
                    rank = find_asin_rank_on_first_page(driver, keyword, asin)
                    rows.append(
                        {
                            "asin": asin,
                            "account_name": account_name,
                            "zipcode": zipcode,
                            "keyword": keyword,
                            "rank": rank,
                            "captured_at": captured_at,
                            "captured_date": captured_date,
                        }
                    )
                    time.sleep(1)
    finally:
        driver.quit()

    return rows


def upsert_to_supabase(rows: List[Dict]) -> None:
    if not rows:
        print("No rows to write.")
        return

    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    supabase_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    table = os.getenv("SUPABASE_TABLE", "amazon_keyword_rank")
    on_conflict = os.getenv("SUPABASE_ON_CONFLICT", "asin,keyword,zipcode,captured_date")

    endpoint = f"{supabase_url}/rest/v1/{table}?on_conflict={quote_plus(on_conflict)}"

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }

    resp = requests.post(endpoint, headers=headers, data=json.dumps(rows), timeout=30)
    resp.raise_for_status()
    print(f"Supabase upsert ok, rows={len(rows)}")


def post_to_feishu_workflow(rows: List[Dict]) -> None:
    webhook = os.getenv("FEISHU_WEBHOOK_URL")
    if not webhook:
        print("FEISHU_WEBHOOK_URL not set, skip webhook post.")
        return

    payload = {
        "source": "github_actions",
        "event": "amazon_rank_synced",
        "row_count": len(rows),
        "rows": rows,
    }
    resp = requests.post(webhook, json=payload, timeout=30)
    resp.raise_for_status()
    print("Feishu webhook post ok")


def main() -> None:
    load_dotenv()
    timezone_name = os.getenv("TIMEZONE", "Asia/Shanghai")

    rows = collect_records(timezone_name=timezone_name)
    print(f"Collected rows={len(rows)}")

    upsert_to_supabase(rows)
    post_to_feishu_workflow(rows)


if __name__ == "__main__":
    main()
