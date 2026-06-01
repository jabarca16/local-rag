import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

os.makedirs("/tmp/uploads", exist_ok=True)
os.makedirs("/app/logs", exist_ok=True)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "default"},
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": "/app/logs/api.log",
                    "maxBytes": 10485760,
                    "backupCount": 3,
                    "formatter": "default",
                },
            },
            "root": {"handlers": ["console", "file"], "level": "INFO"},
        },
    )
