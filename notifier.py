import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from deepseek_client import get_config_value, sanitize_url

SENDER_EMAIL = get_config_value("SENDER_EMAIL")
APP_PASSWORD = get_config_value("APP_PASSWORD")
RECEIVER_EMAIL = get_config_value("RECEIVER_EMAIL")


def send_job_email(job: dict) -> bool:
    """Send an HTML email notification for a matched job posting via Gmail SMTP."""
    if not all([SENDER_EMAIL, APP_PASSWORD, RECEIVER_EMAIL]):
        print("⚠️ Email credentials are missing in .env. Skipping email notification.")
        return False

    try:
        kaynak = job.get("kaynak", "Genel")
        clean_job_url = sanitize_url(job.get("url", ""))

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{kaynak}] {job['baslik']} - {job['sirket']}"
        msg["From"] = f"JoblessAI <{SENDER_EMAIL}>"
        msg["To"] = RECEIVER_EMAIL
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        text_content = f"""
Yeni Eslesme Bulundu!
Platform: {kaynak}
Pozisyon: {job['baslik']}
Sirket: {job['sirket']}
Konum: {job['konum']}
Calisma Sekli: {job['calisma_tipi']}
Ilan Linki: {clean_job_url}
        """

        badge_color = (
            "#0a66c2"
            if kaynak == "LinkedIn"
            else ("#e74c3c" if kaynak == "İŞKUR" else "#8e44ad")
        )

        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="display:inline-block; background-color:{badge_color}; color:#fff; padding:4px 10px; border-radius:4px; font-size:12px; font-weight:bold; margin-bottom:10px;">
              {kaynak}
            </div>
            <h2 style="color: #222; margin-top:5px;">Yeni Bir Eşleşme Bulundu!</h2>
            <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
              <tr><td style="padding: 8px; font-weight: bold; width: 130px;">Pozisyon:</td><td style="padding: 8px;">{job['baslik']}</td></tr>
              <tr style="background-color: #f9f9f9;"><td style="padding: 8px; font-weight: bold;">Şirket:</td><td style="padding: 8px;">{job['sirket']}</td></tr>
              <tr><td style="padding: 8px; font-weight: bold;">Konum:</td><td style="padding: 8px;">{job['konum']}</td></tr>
              <tr style="background-color: #f9f9f9;"><td style="padding: 8px; font-weight: bold;">Çalışma Şekli:</td><td style="padding: 8px;">{job['calisma_tipi']}</td></tr>
            </table>

            <div style="margin-top: 20px;">
              <a href="{clean_job_url}" style="background-color: {badge_color}; color: white; padding: 10px 18px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                İlana Git & Başvur
              </a>
            </div>
            <hr style="margin-top: 30px; border: none; border-top: 1px solid #eee;">
            <p style="font-size: 12px; color: #888;">JoblessAI Takip Botu</p>
          </body>
        </html>
        """

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

        print(f"📧 E-posta iletildi ({kaynak}): {job['baslik']}")
        return True
    except Exception as e:
        print(f"E-posta hatası: {e}")
        return False