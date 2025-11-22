# notifications.py
import logging
from typing import List, Optional

import requests

log = logging.getLogger(__name__)


class Notifier:
    def notify(self, msg: str) -> None:
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    def notify(self, msg: str) -> None:
        log.info("[ALERT] %s", msg)


class WebhookNotifier(Notifier):
    """
    Generic webhook notifier (Discord, Slack, etc.).
    """

    def __init__(self, url: str):
        self.url = url

    def notify(self, msg: str) -> None:
        if not self.url:
            return
        try:
            requests.post(self.url, json={"text": msg})
        except Exception as e:
            log.error("Webhook notify failed: %s", e)


class ListNotifier(Notifier):
    """
    Appends messages to a list (used by Streamlit to show events).
    """

    def __init__(self, target_list: List[str]):
        self.target_list = target_list

    def notify(self, msg: str) -> None:
        self.target_list.append(msg)
