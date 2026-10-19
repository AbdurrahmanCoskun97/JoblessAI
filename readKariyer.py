import json
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

KARIYER_DOMAIN = "https://www.kariyer.net"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": f"{KARIYER_DOMAIN}/",
}

TURKIYE_ILLER = [
    "adana", "adıyaman", "afyon", "ağrı", "aksaray", "amasya", "ankara", "antalya",
    "ardahan", "artvin", "aydın", "balıkesir", "bartın", "batman", "bayburt", "bilecik",
    "bingöl", "bitlis", "bolu", "burdur", "bursa", "çanakkale", "çankırı", "çorum",
    "denizli", "diyarbakır", "düzce", "edirne", "elazığ", "erzincan", "erzurum",
    "eskişehir", "gaziantep", "giresun", "gümüşhane", "hakkari", "hatay", "ığdır",
    "ısparta", "istanbul", "izmir", "kahramanmaraş", "karabük", "karaman", "kars",
    "kastamonu", "kayseri", "kırıkkale", "kırklareli", "kırşehir", "kilis", "kocaeli",
    "konya", "kütahya", "malatya", "manisa", "mardin", "mersin", "muğla", "muş",
    "nevşehir", "niğde", "ordu", "osmaniye", "rize", "sakarya", "samsun", "siirt",
    "sinop", "sivas", "şanlıurfa", "şırnak", "tekirdağ", "tokat", "trabzon", "tunceli",
    "uşak", "van", "yalova", "yozgat", "zonguldak",
]


def _build_kariyer_session() -> requests.Session:
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


def _normalize_tr(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


def _extract_json_ld_job(soup: BeautifulSoup) -> dict:
    """Extract structured JobPosting metadata from JSON-LD scripts if available."""
    result = {}
    scripts = soup.find_all("script", type="application/ld+json")
    for s in scripts:
        if not s.string:
            continue
        try:
            data = json.loads(s.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    result["baslik"] = item.get("title")
                    org = item.get("hiringOrganization")
                    if isinstance(org, dict):
                        result["sirket"] = org.get("name")

                    loc = item.get("jobLocation")
                    cities = []
                    locs = loc if isinstance(loc, list) else ([loc] if loc else [])
                    for l in locs:
                        if isinstance(l, dict):
                            addr = l.get("address", {})
                            if isinstance(addr, dict):
                                city = addr.get("addressLocality") or addr.get("addressRegion")
                                if city and city not in cities:
                                    cities.append(str(city))
                    if cities:
                        result["konum"] = ", ".join(cities)

                    desc_html = item.get("description")
                    if desc_html:
                        desc_soup = BeautifulSoup(desc_html, "html.parser")
                        result["metin"] = desc_soup.get_text(separator="\n", strip=True)
                    return result
        except Exception:
            continue
    return result


def get_kariyernet_jobs(keywords, limit_per_keyword=5) -> list:
    """Search Kariyer.net for given keywords and return details of unseen postings."""
    if isinstance(keywords, str):
        keywords = [keywords]

    seen_ids = load_seen_ids()
    jobs = []
    session = _build_kariyer_session()

    for kw in keywords:
        encoded_kw = quote(kw)
        search_url = sanitize_url(
            f"{KARIYER_DOMAIN}/is-ilanlari?kw={encoded_kw}&sort=date"
        )

        try:
            resp = session.get(search_url, timeout=(5, 20))
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("a", href=re.compile(r"/is-ilani/"))

            found_count = 0
            for a in links:
                href = sanitize_url(a.get("href", ""))
                clean_href = href.split("?")[0]
                id_match = re.search(r"-(\d{6,})$", clean_href) or re.search(
                    r"-(\d{6,})", clean_href
                )
                if not id_match:
                    continue

                raw_id = id_match.group(1)
                job_id = f"kariyer_{raw_id}"

                if job_id in seen_ids:
                    continue

                full_url = sanitize_url(
                    f"{KARIYER_DOMAIN}{clean_href}"
                    if clean_href.startswith("/")
                    else clean_href
                )

                detail = get_kariyernet_detail(session, full_url, job_id)
                if detail:
                    jobs.append(detail)
                    seen_ids.add(job_id)
                    found_count += 1

                if found_count >= limit_per_keyword:
                    break

                time.sleep(random.uniform(1.0, 2.0))

            time.sleep(random.uniform(2.0, 3.5))

        except Exception as e:
            print(f"Kariyer.net '{kw}' araması hatası: {e}")

    return jobs


def get_kariyernet_detail(session: requests.Session, url: str, job_id: str) -> dict | None:
    url = sanitize_url(url)
    try:
        resp = session.get(url, timeout=(5, 20))
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        ld_data = _extract_json_ld_job(soup)

        title_elem = soup.find("h1")
        baslik = (
            ld_data.get("baslik")
            or (title_elem.get_text(strip=True) if title_elem else None)
            or "Başlık Yok"
        )

        sirket_elem = soup.find("a", class_=re.compile(r"company-name|sirket", re.I))
        sirket = (
            ld_data.get("sirket")
            or (sirket_elem.get_text(strip=True) if sirket_elem else None)
            or "Şirket Belirtilmedi"
        )

        konum = ld_data.get("konum")
        if not konum:
            loc_elem = soup.find(
                class_=re.compile(r"location|city|sehir|konum", re.I)
            )
            if loc_elem and len(loc_elem.get_text(strip=True)) < 60:
                konum = loc_elem.get_text(strip=True)

        if not konum:
            for tag in soup.find_all(["span", "div", "p"]):
                if tag.find(["div", "p", "section", "ul", "table"]):
                    continue
                txt = tag.get_text(strip=True)
                if 2 < len(txt) <= 45:
                    txt_low = _normalize_tr(txt)
                    if any(il in txt_low for il in TURKIYE_ILLER):
                        konum = txt
                        break

        if not konum:
            konum = "Türkiye"

        body_elem = soup.find(
            "div", class_=re.compile(r"job-detail|description|ilan-detay|aligment", re.I)
        )
        metin = (
            ld_data.get("metin")
            or (body_elem.get_text(separator="\n", strip=True) if body_elem else None)
            or ""
        )

        if not metin:
            main_elem = soup.find("main") or soup.find("article")
            if main_elem:
                metin = main_elem.get_text(separator="\n", strip=True)

        icerik_kucuk = _normalize_tr(f"{baslik} {konum} {metin}")
        if any(k in icerik_kucuk for k in ["uzaktan", "remote", "evden çalışma"]):
            calisma_tipi = "Remote"
        elif any(k in icerik_kucuk for k in ["hibrit", "hybrid"]):
            calisma_tipi = "Hybrid"
        else:
            calisma_tipi = "Yüzyüze / Belirtilmemiş"

        return {
            "kaynak": "Kariyer.net",
            "job_id": job_id,
            "url": url,
            "baslik": baslik,
            "sirket": sirket,
            "konum": konum,
            "calisma_tipi": calisma_tipi,
            "metin": metin,
        }
    except Exception as e:
        print(f"Kariyer.net ilan okuma hatası ({url}): {e}")
        return None