import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("VIRTUALCLOSET_DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "closet.db"
MODEL_ID = "patrickjohncyh/fashion-clip"
MODEL_VERSION = "fashionclip-prompts-v1"
