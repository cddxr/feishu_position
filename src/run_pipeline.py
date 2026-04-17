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
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


MAX_PAGES = 5
WAIT_TIME = 10
RESULTS_PER_PAGE = 48
SEARCH_RETRIES = 3
KEYWORD_REOPEN_RETRIES = 2


ASIN_KEYWORDS_MAP: Dict[str, Dict] = {
    "B0F8HXNY5N": {
        "name": "default",
        "zipcodes": ["90001", "75001"],
        "keywords": [
            {"keyword": "ryze mushroom hot cocoa"},
            {"keyword": "moonbrew"},
            {"keyword": "moon brew"},
            {"keyword": "sleep aid"},
        ],
    },
    "B0G64PSMX4": {
        "name": "default",
        "zipcodes": ["90001", "75001"],
        "keywords": [
            {"keyword": "javy protein coffee powder"},
            {"keyword": "protein coffee"},
            {"keyword": "chike high protein coffee"},
            {"keyword": "javvy"},
            {"keyword": "chike"},
        ],
    },
    "B0FN3RJ53V": {
        "name": "y",
        "zipcodes": ["90001", "75001"],
        "keywords": [
            {"keyword": "magnesium cream"},
            {"keyword": "magnesium lotion"},
            {"keyword": "magnesium cream for sleep"},
            {"keyword": "magnesium lotion for sleep"},
            {"keyword": "magnesium lotion for kids"},
            {"keyword": "magnesium oil"},
            {"keyword": "magnesium butter"},
            {"keyword": "arnica cream"},
            {"keyword": "restless legs syndrome relief"},
            {"keyword": "Total Relief Magnesium Cream"},
        ],
    },
    "B0F1Y8YV9R": {
        "name": "y",
        "zipcodes": ["90001", "75001"],
        "keywords": [
            {"keyword": "mullein drops for lungs"},
            {"keyword": "mullein"},
            {"keyword": "mullein leaf extract for lungs"},
            {"keyword": "lung detox for smokers"},
        ],
    },
    "B0DJVWJHHJ": {
        "name": "hwy",
        "zipcodes": ["90001", "75001"],
        "keywords": [
            {"keyword": "cat dental care"},
            {"keyword": "cat teeth cleaning"},
            {"keyword": "dog dental wipes"},
            {"keyword": "dog teeth cleaning wipes"},
        ],
    },
    "B0DDCJFFBM": {
        "name": "tx",
        "zipcodes": ["90001", "75001"],
        "keywords": [
            {"keyword": "ryze mushroom coffee"},
            {"keyword": "mushroom coffee"},
        ],
    },
    "B0DFBMVX7T": {
        "name": "tx",
        "zipcodes": ["90001", "75001"],
        "keywords": [
            {"keyword": "mushroom coffee for weight loss"},
            {"keyword": "ryze mushroom coffee for weight loss"},
        ],
    },
    "BODWSDC52L": {
        "name": "tx",
        "zipcodes": ["90001", "75001"],
        "keywords": [
            {"keyword": "face moisturizer"},
            {"keyword": "retinol serum for face"},
            {"keyword": "retinol cream"},
            {"keyword": "anti aging face cream"},
            {"keyword": "wrinkle cream for women"},
        ],
    },
    "B0DN6T1QGD": {
        "name": "lyj",
        "zipcodes": ["90015"],
        "keywords": [
            {"keyword": "lmnt electrolytes"},
            {"keyword": "lmnt"},
            {"keyword": "relyte electrolyte mix"},
            {"keyword": "electrolytes"},
            {"keyword": "electrolytes powder packets"},
        ],
    },
    "B0DGPZ81BC": {
        "name": "lyj",
        "zipcodes": ["90015"],
        "keywords": [
            {"keyword": "hydration packets"},
            {"keyword": "liquid iv"},
            {"keyword": "liquid iv sugar free"},
            {"keyword": "waterboy"},
            {"keyword": "waterboy hydration packets"},
            {"keyword": "electrolytes powder packets"},
        ],
    },
    "B0FKN8PWNJ": {
        "name": "lyj",
        "zipcodes": ["90015"],
        "keywords": [
            {"keyword": "liquid iv"},
            {"keyword": "liquid iv sugar free"},
            {"keyword": "electrolytes powder packets"},
            {"keyword": "hydration packets"},
            {"keyword": "sugar free liquid iv"},
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
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver


def change_zipcode(driver: webdriver.Chrome, wait: WebDriverWait, zipcode: str) -> None:
    def safe_click(locator, use_js_fallback: bool = True):
        el = wait.until(EC.element_to_be_clickable(locator))
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.5)
            el.click()
        except Exception:
            if not use_js_fallback:
                raise
            el = wait.until(EC.presence_of_element_located(locator))
            driver.execute_script("arguments[0].click();", el)
        return el

    try:
        # 先回首页，避免在搜索页/其他页弹窗异常
        if "amazon.com" not in driver.current_url:
            driver.get("https://www.amazon.com")
            time.sleep(2)

        # 1. 点击地址按钮
        safe_click((By.ID, "nav-global-location-popover-link"))
        time.sleep(1.5)

        # 2. 等待邮编输入框真正出现
        zip_input = wait.until(
            EC.visibility_of_element_located((By.ID, "GLUXZipUpdateInput"))
        )

        # 3. 清空并输入邮编
        try:
            zip_input.clear()
            time.sleep(0.3)
        except Exception:
            pass

        driver.execute_script("arguments[0].value = '';", zip_input)
        zip_input.send_keys(zipcode)
        time.sleep(0.5)

        # 4. 点 Apply / 更新
        apply_clicked = False
        apply_locators = [
            (By.XPATH, '//input[@aria-labelledby="GLUXZipUpdate-announce"]'),
            (By.XPATH, '//input[contains(@id,"GLUXZipUpdate") and (@type="submit" or @type="button")]'),
            (By.XPATH, '//span[@id="GLUXZipUpdate"]//input'),
        ]

        for locator in apply_locators:
            try:
                safe_click(locator)
                apply_clicked = True
                break
            except Exception:
                continue

        if not apply_clicked:
            raise Exception("Apply button not clickable")

        time.sleep(2.5)

        # 5. 某些场景会多一个 Continue / Confirm
        optional_confirm_locators = [
            (By.NAME, "glowDoneButton"),
            (By.XPATH, '//input[@name="glowDoneButton"]'),
            (By.XPATH, '//span[@id="GLUXConfirmClose"]//input'),
            (By.XPATH, '//input[contains(@aria-labelledby,"GLUXConfirmClose")]'),
        ]

        for locator in optional_confirm_locators:
            try:
                els = driver.find_elements(*locator)
                if els:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", els[0])
                        time.sleep(0.3)
                        els[0].click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", els[0])
                    time.sleep(1.5)
                    break
            except Exception:
                pass

        # 6. 等页面稳定一下
        time.sleep(2)

        # 7. 简单校验一下地址区域是否已更新
        nav_text = ""
        try:
            nav_addr = driver.find_element(By.ID, "glow-ingress-line2")
            nav_text = (nav_addr.text or "").strip()
        except Exception:
            pass

        if zipcode not in nav_text:
            page_text = (driver.page_source or "")[:300000]
            if zipcode not in page_text:
                raise Exception(f"zipcode not applied: {zipcode}, nav_text={nav_text}")

        print(f"Zipcode switched to {zipcode} successfully")

    except Exception as exc:
        print(f"Zipcode switch failed for {zipcode}: {exc}")
        raise


def find_asin_rank(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    keyword: str,
    asin: str,
    max_pages: int = MAX_PAGES,
    results_per_page: int = RESULTS_PER_PAGE,
) -> Dict[str, Optional[int]]:
    query_url = f"https://www.amazon.com/s?k={quote_plus(keyword)}"
    loaded = False
    for _ in range(SEARCH_RETRIES):
        try:
            driver.get(query_url)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-main-slot")))
            loaded = True
            break
        except (TimeoutException, WebDriverException):
            time.sleep(2)

    if not loaded:
        return {
            "page": None,
            "rank": None,
            "position": None,
            "type": "执行失败",
        }

    page = 1
    while page <= max_pages:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-main-slot")))
        except TimeoutException:
            break

        items = driver.find_elements(By.XPATH, '//div[@data-component-type="s-search-result"]')
        rank_page = 0

        for item in items:
            item_asin = item.get_attribute("data-asin")
            if not item_asin:
                continue

            is_sponsored = item.find_elements(
                By.XPATH,
                './/span[contains(translate(text(),"SPONSORED","sponsored"),"sponsored")]',
            )
            item_type = "ad" if is_sponsored else "organic"

            current_rank_page: Optional[int] = None
            current_rank_total: Optional[int] = None
            if item_type == "organic":
                rank_page += 1
                current_rank_page = rank_page
                current_rank_total = (page - 1) * results_per_page + rank_page

            if item_asin == asin:
                return {
                    "page": page,
                    "rank": current_rank_page,
                    "position": current_rank_total,
                    "type": item_type,
                }

        next_btn = driver.find_elements(By.CSS_SELECTOR, "a.s-pagination-next")
        if not next_btn:
            break

        next_class = next_btn[0].get_attribute("class") or ""
        if "s-pagination-disabled" in next_class:
            break

        next_btn[0].click()
        page += 1
        time.sleep(2)

    return {
        "page": None,
        "rank": None,
        "position": None,
        "type": "N/A",
    }


def collect_records(timezone_name: str) -> List[Dict]:
    rows: List[Dict] = []
    driver = build_driver(headless=True)
    wait = WebDriverWait(driver, WAIT_TIME)

    def reopen_session(current_zipcode: str) -> None:
        nonlocal driver, wait
        try:
            driver.quit()
        except Exception:
            pass
        driver = build_driver(headless=True)
        wait = WebDriverWait(driver, WAIT_TIME)
        driver.get("https://www.amazon.com")
        time.sleep(2)
        change_zipcode(driver, wait, current_zipcode)

    try:
        driver.get("https://www.amazon.com")
        time.sleep(2)

        for asin, meta in ASIN_KEYWORDS_MAP.items():
            account_name = meta.get("name", "default")
            zipcodes = meta.get("zipcodes", [])
            keywords = [x["keyword"] for x in meta.get("keywords", []) if x.get("keyword")]

            for zipcode in zipcodes:
                change_zipcode(driver, wait, zipcode)
                for keyword in keywords:
                    rank_result = {
                        "page": None,
                        "rank": None,
                        "position": None,
                        "type": "执行失败",
                    }

                    for attempt in range(KEYWORD_REOPEN_RETRIES + 1):
                        try:
                            rank_result = find_asin_rank(driver, wait, keyword, asin)
                        except Exception as exc:
                            print(
                                f"find_asin_rank exception asin={asin} keyword={keyword} "
                                f"attempt={attempt + 1}: {exc}"
                            )
                            rank_result = {
                                "page": None,
                                "rank": None,
                                "position": None,
                                "type": "执行失败",
                            }

                        if rank_result.get("type") != "执行失败":
                            break

                        if attempt < KEYWORD_REOPEN_RETRIES:
                            print(
                                f"Retry with reopen asin={asin} keyword={keyword} "
                                f"zipcode={zipcode} attempt={attempt + 2}"
                            )
                            reopen_session(zipcode)

                    now = datetime.now(pytz.timezone(timezone_name))
                    rows.append(
                        {
                            "asin": asin,
                            "account_name": account_name,
                            "zipcode": zipcode,
                            "keyword": keyword,
                            "page": rank_result["page"],
                            "rank": rank_result["rank"],
                            "position": rank_result["position"],
                            "type": rank_result["type"],
                            "captured_at": now.isoformat(),
                            "captured_date": now.strftime("%Y-%m-%d"),
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
    table = os.getenv("SUPABASE_TABLE", "amazon_keyword_rank").strip()
    on_conflict = os.getenv(
        "SUPABASE_ON_CONFLICT",
        "captured_date,account_name,asin,keyword,zipcode",
    ).strip()

    endpoint = f"{supabase_url}/rest/v1/{table}?on_conflict={quote_plus(on_conflict)}"

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }

    resp = requests.post(endpoint, headers=headers, data=json.dumps(rows), timeout=30)
    if not resp.ok:
        print(f"Supabase upsert failed: status={resp.status_code}, body={resp.text[:500]}")
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
