import json
import os
import re
import time
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def sanitize_url(url: str) -> str:
    """Clean markdown formatting artifacts from URLs if present."""
    if not url:
        return ""
    url = url.strip()
    md_match = re.match(r"^\[.*?\]\((.*?)\)(.*)$", url)
    if md_match:
        return md_match.group(1) + md_match.group(2)
    return url.strip("[]()")


def load_env_file(env_filename: str = ".env") -> dict:
    """Parse local .env file without requiring external dependencies."""
    env_vars = {}
    env_path = os.path.join(BASE_DIR, env_filename)
    if not os.path.exists(env_path):
        return env_vars

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                env_vars[key.strip()] = val.strip().strip('"').strip("'")
    except Exception as e:
        print(f"⚠️ Error reading .env file: {e}")

    return env_vars


def get_config_value(key_name: str, default: str = "") -> str:
    """Retrieve configuration value from environment variables, .env, or config.json."""
    if os.environ.get(key_name):
        return os.environ[key_name].strip()

    env_vars = load_env_file(".env")
    if key_name in env_vars and env_vars[key_name]:
        return env_vars[key_name]

    config_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                if key_name in config_data and config_data[key_name]:
                    return str(config_data[key_name]).strip()
        except Exception as e:
            print(f"⚠️ Error reading config.json: {e}")

    return default


def load_deepseek_api_key() -> str:
    """Load DeepSeek API key from config sources or local key files."""
    api_key = get_config_value("DEEPSEEK_API_KEY")
    if api_key:
        return api_key

    for filename in ["api_key.txt", "deepseek_api_key.txt"]:
        file_path = os.path.join(BASE_DIR, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        cleaned = line.strip().strip('"').strip("'")
                        if cleaned and not cleaned.startswith("#"):
                            if "=" in cleaned:
                                cleaned = cleaned.split("=", 1)[1].strip().strip('"').strip("'")
                            return cleaned
            except Exception as e:
                print(f"⚠️ Error reading {filename}: {e}")

    return ""


DEEPSEEK_API_KEY = load_deepseek_api_key()

client = OpenAI(
    api_key=DEEPSEEK_API_KEY or "missing-api-key",
    base_url="https://api.deepseek.com",
)


def _parse_bool_response(raw_content: str) -> bool:
    """Safely parse the JSON response from the LLM into a boolean."""
    if not raw_content:
        return False

    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$", "", raw_content.strip(), flags=re.IGNORECASE
    )
    data = json.loads(cleaned)
    val = data.get("uygun", False)

    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() == "true"
    return bool(val)


def ask_ai_bool(prompt: str, retries: int = 3) -> bool:
    """Evaluate job posting against filtering criteria using DeepSeek-V3."""
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is not configured. Please check your .env file.")

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Sen iş ilanlarını verilen kurallara göre değerlendiren"
                            " uzman bir kariyer filtresisin. Yalnızca geçerli bir"
                            ' JSON formatında yanıt ver: {"uygun": true} veya'
                            ' {"uygun": false}'
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            raw_content = response.choices[0].message.content
            return _parse_bool_response(raw_content)

        except Exception as e:
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 3
                print(f"⚠️ DeepSeek API error ({e}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e