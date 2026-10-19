import random
import re
import time
from urllib.parse import quote
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from deepseek_client import sanitize_url
from readLinkedin import load_seen_ids

ISKUR_DOMAIN = "https://esube.iskur.gov.tr"
ISKUR_SEARCH_PAGE = f"{ISKUR_DOMAIN}/istihdam/AcikIsIlanAra.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": ISKUR_SEARCH_PAGE,
}


def _build_iskur_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    retries = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def get_iskur_jobs(keywords, limit_per_keyword=5) -> list:
    """Scrape public job listings from the ISKUR e-Sube portal."""
    if isinstance(keywords, str):
        keywords = [keywords]

    seen_ids = load_seen_ids()
    jobs = []
    session = _build_iskur_session()

    try:
        session.get(sanitize_url(ISKUR_SEARCH_PAGE), timeout=15)
    except Exception:
        pass

    for kw in keywords:
        encoded_kw = quote(kw)
        search_url = sanitize_url(
            f"{ISKUR_SEARCH_PAGE}?meslek={encoded_kw}&aranan={encoded_kw}"
        )

        try:
            resp = session.get(search_url, timeout=(8, 25))
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            detail_links = soup.find_all(
                "a", href=re.compile(r"AcikIsIlanDetay\.aspx\?uiID=(\d+)")
            )

            found_count = 0
            for a in detail_links:
                href = a["href"]
                match = re.search(r"uiID=(\d+)", href)
                if not match:
                    continue

                raw_id = match.group(1)
                job_id = f"iskur_{raw_id}"

                if job_id in seen_ids:
                    continue

                full_url = sanitize_url(
                    f"{ISKUR_DOMAIN}/istihdam/AcikIsIlanDetay.aspx?uiID={raw_id}"
                )

                detail = get_iskur_detail(session, full_url, job_id)
                if detail:
                    jobs.append(detail)
                    seen_ids.add(job_id)
                    found_count += 1

                if found_count >= limit_per_keyword:
                    break

                time.sleep(random.uniform(1.5, 3.0))

            time.sleep(random.uniform(2.5, 4.0))

        except Exception as e:
            print(f"İŞKUR '{kw}' araması sırasında hata: {e}")

    return jobs


def get_iskur_detail(session: requests.Session, url: str, job_id: str) -> dict | None:
    url = sanitize_url(url)
    try:
        resp = session.get(url, timeout=(8, 25))
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        baslik = "İŞKUR Pozisyonu"
        sirket = "İŞKUR İşvereni"
        konum = "Türkiye"

        title_elem = soup.find(id=re.compile(r"lblMeslek|lblPozisyon|lblIlanBaslik", re.I))
        if title_elem:
            baslik = title_elem.get_text(strip=True)

        company_elem = soup.find(id=re.compile(r"lblIsyeriUnvan|lblIsveren", re.I))
        if company_elem:
            sirket = company_elem.get_text(strip=True)

        city_elem = soup.find(id=re.compile(r"lblCalismaYeri|lblIl", re.I))
        if city_elem:
            konum = city_elem.get_text(strip=True)

        desc_elem = soup.find(
            id=re.compile(r"lblIsTanimi|pnlIsTanimi|lblGenelSartlar|divIlanDetay", re.I)
        )
        if desc_elem:
            metin = desc_elem.get_text(separator="\n", strip=True)
        else:
            main_container = soup.find("div", class_=re.compile(r"content|container|main", re.I))
            metin = (
                main_container.get_text(separator="\n", strip=True)
                if main_container
                else ""
            )

        return {
            "kaynak": "İŞKUR",
            "job_id": job_id,
            "url": url,
            "baslik": baslik,
            "sirket": sirket,
            "konum": konum,
            "calisma_tipi": "Yüzyüze / İş Yerinde",
            "metin": metin,
        }
    except Exception as e:
        print(f"İŞKUR ilan detay hatası ({job_id}): {e}")
        return None