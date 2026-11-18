from pathlib import Path
from app.config.settings import get_settings
from app.database.session import Base, engine
import app.models  # noqa: F401  Ensure all models are registered


def init_db() -> None:
    settings = get_settings()
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.ML_MODELS_DIR).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
