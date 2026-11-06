import logging


def configure_logging():
    # Provider log bodies and HTTP URLs must never reach the default application log.
    for name in ("httpx", "httpcore", "gnani", "gnani-vachana", "urllib3", "google"):
        logger = logging.getLogger(name)
        logger.disabled = True
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
