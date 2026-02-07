from datetime import datetime


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")
