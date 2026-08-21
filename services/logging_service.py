import logging
from logging.handlers import RotatingFileHandler

from config.settings import SETTINGS


def configure_logging() -> None:
    SETTINGS.logs_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if root.handlers:
        return

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        SETTINGS.logs_path / "lexia.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)
