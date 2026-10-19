# JoblessAI — AI-Powered Multi-Platform Job Scraper & Notifier

JoblessAI is an automated job aggregation and filtering pipeline tailored for engineering and software roles in Turkey. It periodically scrapes new job postings from **LinkedIn**, **Kariyer.net**, and **İŞKUR**, evaluates their descriptions against custom career criteria using **DeepSeek-V3**, and sends instant email notifications for matching positions.

## Features

- **Multi-Platform Scraping:** Fetches recent job postings across LinkedIn, Kariyer.net, and İŞKUR without requiring browser automation overhead.
- **Rule-Based Pre-Filtering:** Automatically discards irrelevant locations/workplace types before making LLM calls to save API tokens.
- **LLM Evaluation (`deepseek-chat`):** Analyzes full job descriptions to verify role relevance (Software, AI/ML, Embedded Systems, FPGA, Electrical & Electronics, Automation) and experience requirements (Entry-level / Junior up to 2 years).
- **Duplicate Prevention:** Tracks processed job IDs locally via `seen_jobs.txt` to avoid duplicate evaluations and notifications.
- **HTML Email Alerts:** Sends formatted email summaries with direct application links via Gmail SMTP.

## Project Structure

```
├── main.py              # Main scheduler loop and filtering pipeline
├── deepseek_client.py   # DeepSeek API wrapper and environment loader
├── notifier.py          # SMTP HTML email notification module
├── readLinkedin.py      # LinkedIn guest API scraper
├── readKariyer.py       # Kariyer.net scraper & JSON-LD parser
├── readIskur.py         # İŞKUR public portal scraper
├── requirements.txt     # Python dependencies
└── .env.example         # Environment variable template
```

## Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/JoblessAI.git
   cd JoblessAI
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
   - `DEEPSEEK_API_KEY`: Your API key from DeepSeek Platform.
   - `SENDER_EMAIL`: Gmail address used to send alerts.
   - `APP_PASSWORD`: 16-character Google App Password (requires 2FA enabled on your Google account).
   - `RECEIVER_EMAIL`: Destination email address for job notifications.

4. **Run the bot:**
   ```bash
   python main.py
   ```

## Customization

- **Keywords:** Modify the `SEARCH_KEYWORDS` list in `main.py` to target different job titles or technologies.
- **Filtering Prompt:** Adjust the `filtre_sorusu` prompt inside `evaluate_and_notify()` in `main.py` to customize location, domain, or seniority rules.

