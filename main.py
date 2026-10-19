from textwrap import dedent
import time
from deepseek_client import ask_ai_bool
from notifier import send_job_email
from readIskur import get_iskur_jobs
from readKariyer import get_kariyernet_jobs
from readLinkedin import get_job_details, get_job_urls, save_seen_id

SEARCH_KEYWORDS = [
    "Yeni Mezun",
    "Junior",
    "Aday Mühendis",
    "Yetiştirilmek Üzere",
    "Stajyer",
    "AI Engineer",
    "Machine Learning",
    "Deep Learning",
    "Software Engineer",
    "Yazılım Mühendisi",
    "Python Developer",
    "Elektrik Elektronik Mühendisi",
    "Embedded Software",
    "Gömülü Sistemler",
    "FPGA",
    "Otomasyon Mühendisi",
    "PLC",
    "Test Mühendisi",
]

CHECK_INTERVAL_SECONDS = 3600


def evaluate_and_notify(ilan: dict):
    """Pre-filter job listing, evaluate with LLM, and trigger email notification if matched."""
    metin = ilan.get("metin", "").strip()
    baslik = ilan.get("baslik", "")
    job_id = ilan.get("job_id", "")

    if not metin or len(metin) < 40:
        if job_id:
            save_seen_id(job_id)
        return

    konum_temiz = ilan.get("konum", "").replace("İ", "i").replace("I", "ı").lower()
    tip_temiz = ilan.get("calisma_tipi", "").replace("İ", "i").replace("I", "ı").lower()

    is_onsite = any(
        x in tip_temiz
        for x in ["on-site", "iş yerinde", "işyerinde", "yüzyüze", "yüz yüze"]
    )
    is_istanbul = "istanbul" in konum_temiz

    # Pre-filter out on-site positions located in Istanbul to save API tokens
    if is_onsite and is_istanbul:
        print(f"[ÖN ELENDİ] {baslik} -> İstanbul içi yüzyüze/iş yerinde.")
        save_seen_id(job_id)
        return

    filtre_sorusu = dedent(f"""Aşağıdaki iş ilanını kurallara göre değerlendir ve sadece JSON formatında yanıt ver.

    KURALLAR:
    1. Alan / Rol:
       - Elektrik-Elektronik, Bilgisayar veya Yazılım Mühendislerinin yapabileceği her türlü teknik iş uygundur (Yazılım, Yapay Zeka, Veri, Donanım, Gömülü Sistemler, IoT, Otomasyon/PLC/SCADA, Test/QA, Bakım/Saha Mühendisliği vb.).
       - Teknik olmayan veya alakasız alanlar elenir (İnşaat, Mimarlık, Kimya, Tıp, Satış, Pazarlama, Muhasebe, İK vb.).
    2. Konum / Çalışma Modeli:
       - Uzaktan (Remote): Kesinlikle uygun.
       - Yüzyüze (On-site): Çalışma yeri İstanbul ise KESİNLİKLE ELENİR; İstanbul dışındaki tüm iller uygundur.
    3. Tecrübe Sınırı:
       - Tecrübe istemeyen, "Yeni Mezun", "Stajyer", "Yetiştirilmek üzere" veya en fazla 2 yıla kadar tecrübe arayan ilanlar uygundur.
       - 2 yıldan fazla (3+, 5+ yıl vb.) tecrübe şartı koşan veya doğrudan Senior / Lead ilanları elenir.

    Tüm şartları sağlıyorsa "uygun": true, sağlamıyorsa "uygun": false döndür.

    DEĞERLENDİRİLECEK İLAN:
    Platform: {ilan.get('kaynak', '')}
    İş Başlığı: {baslik}
    Konum: {ilan.get('konum', '')}
    Çalışma Tipi: {ilan.get('calisma_tipi', '')}
    İlan Metni:
    {metin}

    Çıktı (sadece JSON):""")

    try:
        uygun_mu = ask_ai_bool(filtre_sorusu)
        if uygun_mu:
            print(f"🎯 [{ilan.get('kaynak')}] UYGUN: {baslik} ({ilan.get('sirket', '')})")
            if send_job_email(ilan):
                save_seen_id(job_id)
        else:
            print(f"[{ilan.get('kaynak')} - ELENDİ] {baslik} ({ilan.get('sirket', '')})")
            save_seen_id(job_id)

        time.sleep(1)
    except Exception as e:
        print(f"⚠️ Hata ({baslik}): {e}")


def run_Cycle():
    """Run a single scraping and evaluation cycle across all job boards."""
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Tüm platformlar taranıyor...")

    try:
        linkedin_urls = get_job_urls(
            keywords=SEARCH_KEYWORDS, location="Turkey", limit_per_keyword=3
        )
        if linkedin_urls:
            for item in get_job_details(linkedin_urls):
                evaluate_and_notify(item)
    except Exception as e:
        print(f"LinkedIn genel tarama hatası: {e}")

    try:
        for item in get_kariyernet_jobs(SEARCH_KEYWORDS, limit_per_keyword=3):
            evaluate_and_notify(item)
    except Exception as e:
        print(f"Kariyer.net genel tarama hatası: {e}")

    try:
        for item in get_iskur_jobs(SEARCH_KEYWORDS, limit_per_keyword=3):
            evaluate_and_notify(item)
    except Exception as e:
        print(f"İŞKUR genel tarama hatası: {e}")


if __name__ == "__main__":
    while True:
        run_Cycle()
        print(f"{CHECK_INTERVAL_SECONDS // 60} dakika bekleniyor...\n")
        time.sleep(CHECK_INTERVAL_SECONDS)