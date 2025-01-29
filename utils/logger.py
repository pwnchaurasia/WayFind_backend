import logging
import sys



LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(levelprefix)s %(asctime)s [%(name)s] %(levelname)s: %(message)s",
            # Uvicorn uses `levelprefix`, which automatically prefixes logs with the level name.
        },
    },
    "handlers": {
        "default": {
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["default"],
            "level": "ERROR",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        # Your app logger
        "my_app": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
    },
}




logger = logging.getLogger()

# create formatter
formatter = logging.Formatter(fmt="")