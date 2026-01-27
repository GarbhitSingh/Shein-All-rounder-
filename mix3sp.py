import requests
import json
import time
import sys
import os

# ================= BASIC CONFIG =================
BASE_URL = "https://www.sheinindia.in"
CATEGORY_API = BASE_URL + "/api/category/83"

PAGE_SIZE = 40
MAX_PAGES = 300
DELAY = 1.5

BOT_TOKEN = "xxxx"
CHAT_ID = "xxxx"

SEEN_FILE = "seen_products.txt"
# ===============================================


# =============== CATEGORY CODES =================
WOMEN_CATEGORIES = {
    "Tops": "sc-00117294",
    "Dresses": "sc-00118066",
    "Bottoms": "sc-00117314",
    "Outerwear": "sc-00117329",
    "Shoes": "sc-00117420",
}

MEN_CATEGORIES = {
    "Tops": "sc-00117689",
    "Bottoms": "sc-00117705",
    "Outerwear": "sc-00117712",
    "Shoes": "sc-00117736",
}
# ===============================================


# ================= UTILITIES ====================
def load_cookies():
    try:
        with open("cookies.json", "r", encoding="utf-8") as f:
            cookies = json.load(f)
            print("✅ Cookies loaded")
            return cookies
    except Exception as e:
        print("[STOP] Cookies invalid:", e)
        sys.exit(1)


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r") as f:
        return set(x.strip() for x in f if x.strip())


def save_seen(code):
    with open(SEEN_FILE, "a") as f:
        f.write(code + "\n")


def headers():
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-IN,en;q=0.9",
        "user-agent": (
            "Mozilla/5.0 (Linux; Android 11) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "referer": BASE_URL + "/",
        "origin": BASE_URL,
        "x-requested-with": "XMLHttpRequest",
    }


def tg_send(text):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text},
            timeout=10
        )
    except:
        pass
# ===============================================


# ================= FILTER LOGIC =================
def strict_filter(product, gender, category):
    brick = product.get("brickNameText", "").lower()

    if gender == "Men":
        if category == "Bottoms":
            return any(x in brick for x in ["pant", "trouser", "jean", "short"])
        if category == "Shoes":
            return any(x in brick for x in ["shoe", "sneaker", "boot", "sandal", "slipper", "loafer"])
        return True

    if gender == "Women":
        if category == "Shoes":
            return any(x in brick for x in ["shoe", "heel", "sandal", "boot", "slipper"])
        return True

    return True
# ===============================================


# ================= SCAN =========================
def scan_category(name, code, gender, cookies, seen):
    print(f"[START] {gender} → {name}")
    page = 0

    while page < MAX_PAGES:
        params = {
            "currentPage": page,
            "pageSize": PAGE_SIZE,
            "format": "json",
            "sortBy": "relevance",
            "curated": "true",
            "platform": "Desktop",
            "store": "shein",
            "categoryCode": code,
            "query": f":relevance:genderfilter:{gender}",
        }

        r = requests.get(
            CATEGORY_API,
            headers=headers(),
            cookies=cookies,
            params=params,
            timeout=25
        )

        if r.status_code != 200:
            print(f"[WARN] HTTP {r.status_code}")
            break

        products = r.json().get("products", [])
        if not products:
            break

        print(f"[INFO] Page {page} → {len(products)}")

        for p in products:
            code = p.get("code")
            if not code or code in seen:
                continue

            if not strict_filter(p, gender, name):
                continue

            if p.get("couponStatus") != "Coupon Applicable":
                continue

            title = p.get("name", "Unknown")
            price = p.get("price", {}).get("displayformattedValue", "N/A")
            url = BASE_URL + p.get("url", "")

            print("[FOUND]", title)

            tg_send(
                f"🎟 COUPON APPLICABLE\n\n"
                f"👤 {gender}\n"
                f"📦 {name}\n"
                f"👗 {title}\n"
                f"💰 {price}\n"
                f"🔗 {url}"
            )

            seen.add(code)
            save_seen(code)

        page += 1
        time.sleep(DELAY)
# ===============================================


# ================= MENU =========================
def choose_categories(cat_dict, label):
    print(f"\nSELECT CATEGORY ({label}):")
    keys = list(cat_dict.keys())

    for i, k in enumerate(keys, 1):
        print(f"{i} → {k}")
    print(f"{len(keys)+1} → ALL ({label})")

    c = input("Choice: ").strip()

    if c == str(len(keys) + 1):
        return cat_dict.items()
    elif c.isdigit() and 1 <= int(c) <= len(keys):
        k = keys[int(c) - 1]
        return [(k, cat_dict[k])]
    else:
        print("Invalid choice")
        sys.exit(1)
# ===============================================


# ================= MAIN =========================
def main():
    cookies = load_cookies()
    seen = load_seen()

    print("\nSELECT GENDER:")
    print("1 → Women")
    print("2 → Men")
    print("3 → Both")

    g = input("Choice: ").strip()

    if g == "1":
        for name, code in choose_categories(WOMEN_CATEGORIES, "Women"):
            scan_category(name, code, "Women", cookies, seen)

    elif g == "2":
        for name, code in choose_categories(MEN_CATEGORIES, "Men"):
            scan_category(name, code, "Men", cookies, seen)

    elif g == "3":
        print("[INFO] Scanning BOTH genders")
        for name, code in WOMEN_CATEGORIES.items():
            scan_category(name, code, "Women", cookies, seen)
        for name, code in MEN_CATEGORIES.items():
            scan_category(name, code, "Men", cookies, seen)

    else:
        print("Invalid gender choice")
        sys.exit(1)

    print("[DONE] Scan finished")


if __name__ == "__main__":
    main()