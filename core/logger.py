import logging
from pathlib import Path

# ANSI escape codes
LOG_COLORS = {
    "DEBUG": "\033[94m",
    "INFO": "\033[92m",
    "WARNING": "\033[93m",
    "ERROR": "\033[91m",
    "CRITICAL": "\033[95m",
    "RESET": "\033[0m",
}

# Formatter berwarna untuk terminal
class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = LOG_COLORS.get(record.levelname, LOG_COLORS["RESET"])
        reset = LOG_COLORS["RESET"]
        record.levelname = f"{color}{record.levelname}{reset}"
        record.msg = f"{color}{record.msg}{reset}"
        return super().format(record)

# Formatter standar (untuk file)
plain_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Pastikan folder logs ada
Path("logs").mkdir(exist_ok=True)

# Stream handler (console)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(ColorFormatter("%(asctime)s - %(levelname)s - %(message)s"))

# File handler (no color)
file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
file_handler.setFormatter(plain_formatter)

# Logger utama
logger = logging.getLogger("myapp")
logger.setLevel(logging.INFO)
logger.addHandler(stream_handler)
logger.addHandler(file_handler)
logger.propagate = False
