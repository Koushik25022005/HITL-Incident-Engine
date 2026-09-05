import os

from dotenv import load_dotenv # type: ignore

load_dotenv()


OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODEL_NAME = os.environ.get("MODEL_NAME", "google/gemma-4b:free")

APP_REFFERER = os.environ.get("APP_REFFERER", "")
APP_TITLE = os.environ.get("APP_TITLE", "HITL_Incident-Engine")

CHECKPOINT_DB_PATH = os.environ.get("CHECKPOINT_DB_PATH", "incidents.db")


