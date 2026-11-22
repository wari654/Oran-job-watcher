import json
import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

NTFY_TOPIC = os.environ["NTFY_TOPIC"].strip()
SEEN_FILE = "seen_jobs.json"

URLS_TO_CHECK = [
    "https://www.optioncarriere.dz/emploi-informatique/Oran",
    "https://www.optioncarriere.dz/emploi-reseau/Oran",
    "https://www.optioncarriere.dz/emploi-technicien-informatique/Oran",
    "https://emploitic.com/offres-d-emploi/q-informatique-l-oran-algerie",
    "https://emploitic.com/offres-d-emploi/q-reseau-l-oran-algerie",
    "https://emploitic.com/offres-d-emploi/q-support-l-oran-algerie",
]

IGNORE_KEYWORDS = ["commercial", "vendeur", "prevendeur", "comptable", "chauffeur"]

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen_set):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(seen_set)), f, indent=2)

def send_phone_notification(title, company, link):
    r = requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=f"{company}\nTap to view & apply.".encode("utf-8"),
        headers={
            "Title": f"Oran Job: {title[:80]}",
            "Priority": "high",
            "Tags": "briefcase",
            "Click": link,
        },
        timeout=15,
    )
    r.raise_for_status()
    print(f"[SENT] {title} ({company})")

def scrape_jobs():
    seen = load_seen()
    matched = 0
    sent = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for url in URLS_TO_CHECK:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3500)
                soup = BeautifulSoup(page.content(), "html.parser")

                if "optioncarriere.dz" in url:
                    cards = soup.select("article.job")
                    print(f"[INFO] {url} -> {len(cards)} cards")
                    for job in cards:
                        a_tag = job.select_one("header h2 a") or job.select_one("h2 a") or job.select_one("a")
                        if not a_tag:
                            continue
                        title = a_tag.get_text(strip=True)
                        href = a_tag.get("href", "")
                        if not title or not href:
                            continue
                        full_link = href if href.startswith("http") else f"https://www.optioncarriere.dz{href}"
                        company_tag = job.select_one("p.company") or job.select_one(".company")
                        company = company_tag.get_text(strip=True) if company_tag else "Oran"

                        if any(bad in title.lower() for bad in IGNORE_KEYWORDS):
                            continue

                        matched += 1
                        if full_link not in seen:
                            seen.add(full_link)
                            send_phone_notification(title, company, full_link)
                            sent += 1

                elif "emploitic.com" in url:
                    links = soup.select("a[href*='/offres-d-emploi/']")
                    print(f"[INFO] {url} -> {len(links)} links")
                    for a_tag in links:
                        title = a_tag.get_text(" ", strip=True)
                        href = a_tag.get("href", "")
                        if len(title) < 6 or "/q-" in href or "/l-" in href:
                            continue
                        full_link = href if href.startswith("http") else f"https://emploitic.com{href}"

                        if any(bad in title.lower() for bad in IGNORE_KEYWORDS):
                            continue

                        matched += 1
                        if full_link not in seen:
                            seen.add(full_link)
                            send_phone_notification(title, "Emploitic Oran", full_link)
                            sent += 1

            except Exception as e:
                print(f"[WARN] {url} -> {e}")

        browser.close()

    save_seen(seen)
    print(f"[SUMMARY] Matched: {matched}, Sent: {sent}")

if __name__ == "__main__":
    scrape_jobs()
