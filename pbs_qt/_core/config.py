import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where the app keeps its data. Defaults to the core package folder, but an
# embedder (e.g. the desktop app) can redirect it via environment variables so
# it can own its own database and staging area.
DATA_DIR = os.environ.get("ROOBA_DATA_DIR") or BASE_DIR
DB_PATH = os.environ.get("ROOBA_DB_PATH") or os.path.join(DATA_DIR, "pbs.db")
STAGING_DIR = os.environ.get("ROOBA_STAGING_DIR") or os.path.join(DATA_DIR, "staging")

DATABASE_URL = f"sqlite:///{DB_PATH}"

DEFAULT_USER_ID = 1

os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
os.makedirs(STAGING_DIR, exist_ok=True)