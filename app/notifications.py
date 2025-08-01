import logging
import requests
from .config import settings

def send_bark_notification(title: str, body: str):
    """
    Sends a notification via Bark.
    """
    if not settings.BARK_URL:
        logging.warning("BARK_URL is not configured. Skipping notification.")
        return

    try:
        url = f"{settings.BARK_URL}/{title}/{body}"
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        logging.info(f"Successfully sent Bark notification: {title}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Bark notification. Error: {e}")
