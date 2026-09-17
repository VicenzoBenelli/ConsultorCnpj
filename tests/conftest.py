from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
TEST_ENV_FILE = ROOT_DIR / ".env.test"

load_dotenv(TEST_ENV_FILE, override=False)