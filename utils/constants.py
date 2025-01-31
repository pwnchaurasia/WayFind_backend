import os
import pathlib


BASE_DIR = pathlib.Path(".").parent.absolute()
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters":{
        "verbose": {"format": "%(asctime)s %(levelname)s %(filename)s:%(lineno)d  %(message)s"},
        "simple": {"format": "%(levelname)s %(message)s"}
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "app": {
            "level": "DEBUG",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": "verbose",
            "filename": os.path.join(LOG_DIR, "app.log"),
            "when": "W4",
            "interval": 1,
            "backupCount": 7,
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False
        },
        "app":{
            "handlers": ["app"],
            "level": "DEBUG",
            "propagate": False
        }
    },
}
