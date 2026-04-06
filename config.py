import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
DONE_DIR = INPUT_DIR / "done"
OUTPUT_DIR = BASE_DIR / "output"
SAMPLES_DIR = BASE_DIR / "samples"
PROMPTS_DIR = BASE_DIR / "prompts"
BROWSER_DATA_DIR = BASE_DIR / "browser_data"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
WANTEDLY_EMAIL = os.getenv("WANTEDLY_EMAIL", "")
WANTEDLY_PASSWORD = os.getenv("WANTEDLY_PASSWORD", "")

CLAUDE_MODEL = "claude-sonnet-4-20250514"

ARTICLE_EXTENSIONS = {".txt", ".md"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

for d in [INPUT_DIR, DONE_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)
