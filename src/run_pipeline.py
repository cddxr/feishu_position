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
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager


MAX_PAGES = 8
WAIT_TIME = 15
RESULTS_PER_PAGE = 48
SEARCH_RETRIES = 5
KEYWORD_REOPEN_RETRIES = 2
RETRY_TYPE = "__retry__"

FEISHU_WEBHOOK_DEFAULTS = {
    "lyj_group": "https://o9xilj84js.feishu.cn/base/workflow/webhook/event/TqLDajCZYw8Zyph0nyGcMH1anMH",
    "ytx_group": "https://o9xilj84js.feishu.cn/base/workflow/webhook/event/VXZsa3nrIwrrnIhuCLSc2H7Dnee",
    "default_group": "https://o9xilj84js.feishu.cn/base/workflow/webhook/event/OMqZaCHJ9wOjOGhGFwGcCOccnEd",
}

FEISHU_ACCOUNT_GROUPS = {
    "lyj": "lyj_group",
    "zlq": "lyj_group",
    "lyw": "lyj_group",
    "y": "ytx_group",
    "tx": "ytx_group",
    "hwy": "ytx_group",
    "default": "default_group",
}


ASIN_KEYWORDS_MAP: Dict[str, Dict] = {
    "B0F8HXNY5N": {
        "name": "default",
        "zipcodes": ["90001", "75001", "10001", "90015"],
        "keywords": [
            {"keyword": "ryze mushroom hot cocoa"},
            {"keyword": "moonbrew"},
            {"keyword": "moon brew"},
            {"keyword": "sleep aid"},
        ],
    },
    # "B0G64PSMX4": {
    #     "name": "default",
    #     "zipcodes": ["90001", "75001", "10001", "90015"],
    #     "keywords": [
    #         {"keyword": "javy protein coffee powder"},
    #         {"keyword": "protein coffee"},
    #         {"keyword": "chike high protein coffee"},
    #         {"keyword": "javvy"},
    #         {"keyword": "chike"},
    #     ],
    # },
    "B0DJRD5LCB": {
        "asin": "B0DJRD5LCB",
        "name": "y",
        "zipcodes": ["90001", "90015"],
        "keywords": [
            {"keyword": "vitamin d drops"},
            {"keyword": "liquid vitamin d"},
            {"keyword": "vitamin d3 k2"},
            {"keyword": "d3 k2 vitamin 10000 iu"},
        ],
    },
    "B0DJVWJHHJ": {
        "name": "hwy",
        "zipcodes": ["90001", "90015"],
        "keywords": [
            {"keyword": "cat dental care"},
            {"keyword": "cat teeth cleaning"},
            {"keyword": "dog dental wipes"},
            {"keyword": "dog teeth cleaning wipes"},
        ],
    },
    "B0DDCJFFBM": {
        "name": "tx",
        "zipcodes": ["90001", "75001", "78001", "10001"],
        "keywords": [
            {"keyword": "ryze mushroom coffee"},
            {"keyword": "mushroom coffee"},
        ],
    },
    "B0DFBMVX7T": {
        "name": "tx",
        "zipcodes": ["90001", "75001", "78001", "10001"],
        "keywords": [
            {"keyword": "mushroom coffee for weight loss"},
            {"keyword": "ryze mushroom coffee for weight loss"},
        ],
    },
    "B0DWSDC52L": {
        "name": "tx",
        "zipcodes": ["90001"],
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
    "B0FKN3ZTBJ__zlq": {
        "asin": "B0FKN3ZTBJ",
        "name": "zlq",
        "zipcodes": ["90015"],
        "keywords": [
            {"keyword": "electrolytes"},
            {"keyword": "lmnt electrolytes"},
            {"keyword": "lmnt"},
            {"keyword": "electrolytes powder packets"},
            {"keyword": "lmnt electrolyte powder packets"},
        ],
    },
    "B0FVLNKFJL": {
        "name": "zlq",
        "zipcodes": ["90015"],
        "keywords": [
            {"keyword": "electrolytes"},
            {"keyword": "lmnt electrolytes"},
            {"keyword": "lmnt"},
            {"keyword": "electrolytes powder packets"},
            {"keyword": "lmnt electrolyte powder packets"},
        ],
    },
    "B0DGPZ81BC__lyw": {
        "asin": "B0DGPZ81BC",
        "name": "lyw",
        "zipcodes": ["90015"],
        "keywords": [
            {"keyword": "liquid iv"},
            {"keyword": "liquid iv sugar free"},
            {"keyword": "hydration packets"},
            {"keyword": "electrolytes powder packets"},
            {"keyword": "waterboy"},
            {"keyword": "waterboy hydration packets"},
        ],
    },
    "B0FKN3ZTBJ__lyw": {
        "asin": "B0FKN3ZTBJ",
        "name": "lyw",
        "zipcodes": ["90015"],
        "keywords": [
            {"keyword": "electrolytes"},
            {"keyword": "lmnt electrolytes"},
            {"keyword": "lmnt"},
            {"keyword": "electrolytes powder packets"},
            {"keyword": "lmnt electrolyte powder packets"},
        ],
    },
}


def build_driver(headless: bool = True) -> webdriver.Chrome:
    runner_temp = os.environ.get("RUNNER_TEMP") or os.environ.get("TEMP") or os.getcwd()
    chrome_runtime_dir = os.path.join(runner_temp, "chrome-runtime", str(os.getpid()))
    wdm_cache_dir = os.environ.get("WDM_CACHE_DIR") or os.path.join(runner_temp, "wdm-cache")
    os.makedirs(chrome_runtime_dir, exist_ok=True)
    os.makedirs(wdm_cache_dir, exist_ok=True)

    options = Options()
    options.page_load_strategy = "eager"
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--no-first-run")
    options.add_argument("--lang=en-US,en")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"--user-data-dir={chrome_runtime_dir}")
    options.add_argument(f"--disk-cache-dir={os.path.join(chrome_runtime_dir, 'cache')}")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option(
        "prefs",
        {
            "intl.accept_languages": "en-US,en",
            "profile.default_content_setting_values.notifications": 2,
        },
    )
    service = Service(
        ChromeDriverManager(cache_manager=DriverCacheManager(root_dir=wdm_cache_dir)).install()
    )
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(15)
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd(
        "Network.setExtraHTTPHeaders",
        {
            "headers": {
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
            }
        },
    )
    driver.execute_cdp_cmd("Emulation.setLocaleOverride", {"locale": "en-US"})
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                window.chrome = window.chrome || {runtime: {}};
            """
        },
    )
    return driver


def change_zipcode(driver: webdriver.Chrome, wait: WebDriverWait, zipcode: str) -> None:
    def wait_page_ready(timeout: int = 12):
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

    def safe_click_any(locators, timeout: int = WAIT_TIME):
        last_exc = None
        for locator in locators:
            try:
                el = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located(locator)
                )
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.5)
                WebDriverWait(driver, timeout).until(
                    lambda d: el.is_displayed() and el.is_enabled()
                )
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                return el
            except Exception as exc:
                last_exc = exc
                continue
        raise last_exc if last_exc else Exception("No clickable element found")

    def try_ajax_change() -> bool:
        if "amazon.com" not in (driver.current_url or ""):
            driver.get("https://www.amazon.com/?ref_=nav_logo")
            wait_page_ready()

        script = """
            const zipcode = arguments[0];
            const done = arguments[arguments.length - 1];
            const body = new URLSearchParams({
                locationType: "LOCATION_INPUT",
                zipCode: zipcode,
                storeContext: "generic",
                deviceType: "web",
                pageType: "Gateway",
                actionSource: "glow"
            });
            fetch("/gp/delivery/ajax/address-change.html", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body,
                credentials: "include"
            })
                .then(async response => done({
                    ok: response.ok,
                    status: response.status,
                    text: (await response.text()).slice(0, 300)
                }))
                .catch(error => done({ok: false, error: String(error)}));
        """
        result = driver.execute_async_script(script, zipcode)
        text = (result.get("text") or "").lower()
        return bool(result.get("ok")) and "captcha" not in text and "csrf" not in text

    start = time.time()
    try:
        try:
            if try_ajax_change():
                print(
                    f"Zipcode switched to {zipcode} via ajax in {time.time() - start:.1f}s",
                    flush=True,
                )
                return
        except Exception as exc:
            print(f"Fast zipcode ajax failed for {zipcode}: {exc}", flush=True)

        # 1) 强制回首页，避免停留在搜索页/异常页
        driver.get("https://www.amazon.com/?ref_=nav_logo")
        wait_page_ready()
        time.sleep(1)

        # 2) 先处理可能的 cookie / continue 弹窗（有则点，没有就跳过）
        optional_buttons = [
            (By.ID, "sp-cc-accept"),
            (By.NAME, "accept"),
            (By.XPATH, '//input[contains(@aria-label, "Accept")]'),
            (By.XPATH, '//button[contains(., "Continue shopping")]'),
        ]
        for locator in optional_buttons:
            try:
                els = driver.find_elements(*locator)
                if els:
                    try:
                        els[0].click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", els[0])
                    time.sleep(1)
                    break
            except Exception:
                pass

        # 3) 地址按钮多定位兜底，不只用一个 ID
        location_locators = [
            (By.ID, "nav-global-location-popover-link"),
            (By.ID, "glow-ingress-block"),
            (By.XPATH, '//a[@id="nav-global-location-popover-link"]'),
            (By.XPATH, '//div[@id="glow-ingress-block"]'),
            (By.XPATH, '//span[@id="glow-ingress-line1"]/ancestor::*[@id="nav-global-location-popover-link" or @id="glow-ingress-block"]'),
        ]
        safe_click_any(location_locators, timeout=15)
        time.sleep(1)

        # 4) 等邮编输入框出现
        zip_input = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.ID, "GLUXZipUpdateInput"))
        )

        try:
            zip_input.clear()
        except Exception:
            pass
        driver.execute_script("arguments[0].value = '';", zip_input)
        zip_input.send_keys(zipcode)
        time.sleep(0.5)

        # 5) Apply 按钮多定位
        apply_locators = [
            (By.XPATH, '//input[@aria-labelledby="GLUXZipUpdate-announce"]'),
            (By.XPATH, '//span[@id="GLUXZipUpdate"]//input'),
            (By.XPATH, '//input[contains(@id,"GLUXZipUpdate")]'),
        ]
        safe_click_any(apply_locators, timeout=10)
        time.sleep(1.5)

        # 6) Done / Continue / Confirm 按钮兜底
        done_locators = [
            (By.NAME, "glowDoneButton"),
            (By.XPATH, '//input[@name="glowDoneButton"]'),
            (By.XPATH, '//span[@id="GLUXConfirmClose"]//input'),
            (By.XPATH, '//input[contains(@aria-labelledby,"GLUXConfirmClose")]'),
        ]
        for locator in done_locators:
            try:
                els = driver.find_elements(*locator)
                if els:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", els[0])
                        time.sleep(0.3)
                        els[0].click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", els[0])
                    time.sleep(1)
                    break
            except Exception:
                pass

        # 7) 校验是否切换成功
        nav_text = ""
        try:
            nav_addr = driver.find_element(By.ID, "glow-ingress-line2")
            nav_text = (nav_addr.text or "").strip()
        except Exception:
            pass

        if zipcode not in nav_text:
            raise Exception(f"zipcode not applied: {zipcode}, nav_text={nav_text}")

        print(
            f"Zipcode switched to {zipcode} via ui in {time.time() - start:.1f}s",
            flush=True,
        )

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
    def page_diagnostic() -> str:
        title = ""
        current_url = ""
        source = ""
        try:
            title = driver.title
            current_url = driver.current_url
            source = driver.page_source.lower()
        except Exception:
            pass
        flags = []
        if "captcha" in source or "robot check" in source or "/errors/validatecaptcha" in current_url:
            flags.append("captcha_or_robot_check")
        if "sorry" in title.lower() or "sorry" in source[:1000]:
            flags.append("sorry_page")
        return f"title={title!r} url={current_url!r} flags={flags}"

    query_url = f"https://www.amazon.com/s?k={quote_plus(keyword)}&ref=nb_sb_noss"
    loaded = False
    last_diag = ""
    for attempt in range(SEARCH_RETRIES):
        try:
            driver.get(query_url)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-main-slot")))
            loaded = True
            break
        except (TimeoutException, WebDriverException):
            last_diag = page_diagnostic()
            print(
                f"Search page load failed asin={asin} keyword={keyword} "
                f"attempt={attempt + 1}/{SEARCH_RETRIES}: {last_diag}",
                flush=True,
            )
            time.sleep(2)

    if not loaded:
        return {
            "page": 0,
            "rank": 0,
            "position": 0,
            "type": RETRY_TYPE,
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
                    "rank": current_rank_page or 0,
                    "position": current_rank_total or 0,
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
        "page": 0,
        "rank": 0,
        "position": 0,
        "type": "N/A",
    }


def collect_records(timezone_name: str) -> List[Dict]:
    rows: List[Dict] = []
    driver = build_driver(headless=True)
    wait = WebDriverWait(driver, WAIT_TIME)
    active_zipcode: Optional[str] = None

    def failure_result() -> Dict[str, Optional[int]]:
        return {
            "page": 0,
            "rank": 0,
            "position": 0,
            "type": RETRY_TYPE,
        }

    def not_found_result() -> Dict[str, Optional[int]]:
        return {
            "page": 0,
            "rank": 0,
            "position": 0,
            "type": "N/A",
        }

    def append_record(
        asin: str,
        account_name: str,
        zipcode: str,
        keyword: str,
        rank_result: Dict[str, Optional[int]],
    ) -> None:
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

    def reopen_session(current_zipcode: str) -> bool:
        nonlocal active_zipcode, driver, wait
        active_zipcode = None
        try:
            driver.quit()
        except Exception:
            pass
        try:
            driver = build_driver(headless=True)
            wait = WebDriverWait(driver, WAIT_TIME)
            driver.get("https://www.amazon.com")
            time.sleep(2)
            change_zipcode(driver, wait, current_zipcode)
            active_zipcode = current_zipcode
            return True
        except Exception as exc:
            print(f"Reopen session failed for zipcode={current_zipcode}: {exc}", flush=True)
            return False

    try:
        driver.get("https://www.amazon.com")
        time.sleep(2)

        for asin_key, meta in ASIN_KEYWORDS_MAP.items():
            asin = meta.get("asin", asin_key)
            account_name = meta.get("name", "default")
            zipcodes = meta.get("zipcodes", [])
            keywords = [x["keyword"] for x in meta.get("keywords", []) if x.get("keyword")]

            for zipcode in zipcodes:
                zipcode_ready = False
                try:
                    if active_zipcode == zipcode:
                        zipcode_ready = True
                        print(f"Zipcode {zipcode} already active, skip switch", flush=True)
                    else:
                        change_zipcode(driver, wait, zipcode)
                        active_zipcode = zipcode
                    zipcode_ready = True
                except Exception as exc:
                    active_zipcode = None
                    print(
                        f"Zipcode setup failed account={account_name} asin={asin} "
                        f"zipcode={zipcode}: {exc}",
                        flush=True,
                    )
                    zipcode_ready = reopen_session(zipcode)

                if not zipcode_ready:
                    print(
                        f"Skip zipcode after failed setup account={account_name} asin={asin} "
                        f"zipcode={zipcode}; mark keywords as N/A",
                        flush=True,
                    )
                    for keyword in keywords:
                        append_record(asin, account_name, zipcode, keyword, not_found_result())
                    continue

                for keyword in keywords:
                    print(
                        f"Processing account={account_name} asin={asin} zipcode={zipcode} keyword={keyword}",
                        flush=True,
                    )
                    rank_result = failure_result()

                    for attempt in range(KEYWORD_REOPEN_RETRIES + 1):
                        try:
                            rank_result = find_asin_rank(driver, wait, keyword, asin)
                        except Exception as exc:
                            print(
                                f"find_asin_rank exception asin={asin} keyword={keyword} "
                                f"attempt={attempt + 1}: {exc}"
                            )
                            rank_result = failure_result()

                        if rank_result.get("type") != RETRY_TYPE:
                            break

                        if attempt < KEYWORD_REOPEN_RETRIES:
                            print(
                                f"Retry with reopen asin={asin} keyword={keyword} "
                                f"zipcode={zipcode} attempt={attempt + 2}"
                            )
                            if not reopen_session(zipcode):
                                break

                    if rank_result.get("type") == RETRY_TYPE:
                        print(
                            f"Search never stabilized account={account_name} asin={asin} "
                            f"zipcode={zipcode} keyword={keyword}; write N/A",
                            flush=True,
                        )
                        rank_result = not_found_result()

                    append_record(asin, account_name, zipcode, keyword, rank_result)
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


def get_feishu_webhook(account_name: str) -> Optional[str]:
    group = FEISHU_ACCOUNT_GROUPS.get(account_name, "default_group")
    env_name = f"FEISHU_WEBHOOK_{group.upper()}"
    return (os.getenv(env_name) or FEISHU_WEBHOOK_DEFAULTS[group]).strip()


def post_to_feishu_workflow(rows: List[Dict]) -> None:
    rows_by_webhook: Dict[str, List[Dict]] = {}
    for row in rows:
        webhook = get_feishu_webhook(row.get("account_name", "default"))
        if not webhook:
            continue
        rows_by_webhook.setdefault(webhook, []).append(row)

    if not rows_by_webhook:
        print("No Feishu webhook configured, skip webhook post.")
        return

    for webhook, webhook_rows in rows_by_webhook.items():
        payload = {
            "source": "github_actions",
            "event": "amazon_rank_synced",
            "row_count": len(webhook_rows),
            "rows": webhook_rows,
        }
        resp = requests.post(webhook, json=payload, timeout=30)
        resp.raise_for_status()
        accounts = sorted({row.get("account_name", "default") for row in webhook_rows})
        print(f"Feishu webhook post ok, accounts={accounts}, rows={len(webhook_rows)}")


def main() -> None:
    load_dotenv()
    timezone_name = os.getenv("TIMEZONE", "Asia/Shanghai")

    rows = collect_records(timezone_name=timezone_name)
    print(f"Collected rows={len(rows)}")

    upsert_to_supabase(rows)
    post_to_feishu_workflow(rows)


if __name__ == "__main__":
    main()
