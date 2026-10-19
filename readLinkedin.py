import os
import random
import re
import time
from urllib.parse import quote
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from deepseek_client import sanitize_url

LINKEDIN_DOMAIN = "https://www.linkedin.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE_DIR, "seen_jobs.txt")


def build_session() -> requests.Session:
    """Create a requests session configured with automatic retries and backoff."""
    s = requests.Session()
    s.headers.update(HEADERS)

    retries = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


session = build_session()


def load_seen_ids() -> set:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_seen_id(job_id: str):
    if not job_id:
        return
    seen = load_seen_ids()
    if job_id not in seen:
        with open(SEEN_FILE, "a", encoding="utf-8") as f:
            f.write(f"{job_id}\n")


def get_job_urls(keywords, location="Turkey", limit_per_keyword=5) -> list:
    """Fetch unseen LinkedIn job URLs via the public guest search endpoint."""
    global session
    if isinstance(keywords, str):
        keywords = [keywords]

    seen_ids = load_seen_ids()
    new_links = []

    for kw in keywords:
        encoded_kw = quote(kw)
        encoded_loc = quote(location)

        search_url = sanitize_url(
            f"{LINKEDIN_DOMAIN}/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={encoded_kw}&location={encoded_loc}&sortBy=DD&f_TPR=r432000"
        )

        try:
            resp = session.get(search_url, timeout=(5, 25))

            if resp.status_code == 429:
                print(f"⚠️ [{kw}] LinkedIn Rate Limit (429)! 30 sn bekleniyor...")
                time.sleep(30)
                continue

            if resp.status_code != 200:
                print(f"[{kw}] LinkedIn Arama Durumu: {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")

            found_count = 0
            for card in cards:
                link_tag = card.find("a", class_="base-card__full-link")
                if not link_tag or "href" not in link_tag.attrs:
                    continue

                raw_link = link_tag["href"]
                match = re.search(r"(\d{8,})", raw_link)
                if not match:
                    continue

                raw_id = match.group(1)
                prefixed_id = f"linkedin_{raw_id}"
                clean_url = sanitize_url(f"{LINKEDIN_DOMAIN}/jobs/view/{raw_id}")

                if prefixed_id not in seen_ids and raw_id not in seen_ids:
                    new_links.append(clean_url)
                    seen_ids.add(prefixed_id)
                    found_count += 1

                if found_count >= limit_per_keyword:
                    break

            time.sleep(random.uniform(2.0, 4.0))

        except requests.exceptions.Timeout:
            print(f"⚠️ '{kw}' araması zaman aşımına uğradı (Timeout). Session yenileniyor...")
            session = build_session()
            time.sleep(5)
        except Exception as e:
            print(f"'{kw}' araması sırasında hata: {e}")

    return new_links


def get_job_details(urls: list) -> list:
    """Scrape full job details and workplace type from LinkedIn job URLs."""
    jobs = []

    for url in urls:
        url = sanitize_url(url)
        match = re.search(r"(\d{8,})", url)
        if not match:
            continue
        raw_id = match.group(1)
        job_id = f"linkedin_{raw_id}"
        api_url = sanitize_url(f"{LINKEDIN_DOMAIN}/jobs-guest/jobs/api/jobPosting/{raw_id}")

        try:
            resp = session.get(api_url, timeout=(5, 20))
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            title_tag = soup.find("h2", class_="top-card-layout__title") or soup.find("h1")
            baslik = title_tag.get_text(strip=True) if title_tag else "Başlık Yok"

            sirket_tag = (
                soup.find("a", class_="topcard__org-name-link")
                or soup.find("span", class_="topcard__flavor")
            )
            sirket = sirket_tag.get_text(strip=True) if sirket_tag else "Bilinmiyor"

            konum_tag = soup.find("span", class_="topcard__flavor--bullet")
            konum = konum_tag.get_text(strip=True) if konum_tag else "Bilinmiyor"

            aciklama_tag = soup.find("div", class_="show-more-less-html__markup")
            metin = aciklama_tag.get_text(separator="\n", strip=True) if aciklama_tag else ""

            tum_icerik = (
                (soup.get_text() + " " + metin).replace("İ", "i").replace("I", "ı").lower()
            )
            konum_lower = konum.replace("İ", "i").replace("I", "ı").lower()

            if any(x in konum_lower for x in ["remote", "uzaktan"]):
                calisma_tipi = "Remote"
            elif any(x in konum_lower for x in ["hybrid", "hibrit"]):
                calisma_tipi = "Hybrid"
            elif any(
                x in tum_icerik
                for x in [
                    "workplace type: remote",
                    "çalışma şekli: uzaktan",
                    "tamamen uzaktan",
                    "100% remote",
                ]
            ):
                calisma_tipi = "Remote"
            elif any(
                x in tum_icerik
                for x in [
                    "workplace type: hybrid",
                    "çalışma şekli: hibrit",
                    "hibrit çalışma",
                ]
            ):
                calisma_tipi = "Hybrid"
            elif any(
                x in konum_lower for x in ["on-site", "yerinde", "iş yerinde", "yüzyüze"]
            ):
                calisma_tipi = "Yüzyüze (On-site)"
            else:
                calisma_tipi = "Yüzyüze / Belirtilmemiş"

            jobs.append(
                {
                    "kaynak": "LinkedIn",
                    "job_id": job_id,
                    "url": url,
                    "baslik": baslik,
                    "sirket": sirket,
                    "konum": konum,
                    "calisma_tipi": calisma_tipi,
                    "metin": metin,
                }
            )

            time.sleep(random.uniform(1.2, 2.5))

        except Exception as e:
            print(f"İlan detayı alınamadı (ID: {raw_id}): {e}")

    return jobs