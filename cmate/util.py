import os
import json
import socket
import logging
from typing import Any
from enum import Enum
from functools import total_ordering

import yaml
import psutil
from msguard.security import open_s
from colorama import Fore, Style


class ANSIColoredFormatter(logging.Formatter):
    COLORS = {
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED
    }

    def format(self, record):
        message = super().format(record)
        if record.levelname in self.COLORS:
            message = f"{self.COLORS[record.levelname]}{message}{Fore.RESET}"
        return message


def get_logger():
    logger = logging.getLogger("msprechecker")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        formatter = ANSIColoredFormatter("%(message)s")
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


cmate_logger = get_logger()


@total_ordering
class Severity(Enum):
    INFO = '[RECOMMEND]'
    WARNING = '[WARNING]'
    ERROR = '[NOK]'

    _ORDER_MAP = {
        "INFO": 0,
        "WARNING": 1,
        "ERROR": 2
    }

    def __str__(self):
        return f"{self.color_code}{self.value}{Fore.RESET}"

    def __gt__(self, other):
        order_map = self._ORDER_MAP.value
        if isinstance(other, Severity):
            return order_map[self.name] > order_map[other.name]

        if isinstance(other, str):
            return order_map[self.name] > order_map[other.upper()]

        return super().__gt__(self, other)

    @property
    def color_code(self):
        return {
            Severity.INFO: Style.BRIGHT + Fore.CYAN,
            Severity.WARNING: Style.BRIGHT + Fore.YELLOW,
            Severity.ERROR: Style.BRIGHT + Fore.RED
        }[self]


def _ext_to_type(path: str) -> str:
    _, ext = os.path.splitext(path)
    if ext.startswith('.'):
        ext = ext[1:]
    return ext.lower()


def load(path: str, parse_type: str = None) -> Any:
    """Load configuration from `path` and return parsed object.

    - If `parse_type` is not provided, it's derived from file extension.
    - Supported types: `json`, `yaml`/`yml`.
    """
    if parse_type is None:
        parse_type = _ext_to_type(path)

    if parse_type in ('yaml', 'yml'):
        with open_s(path, 'r', encoding='utf-8') as f:
            docs = list(yaml.safe_load_all(f))
            if len(docs) == 0:
                return None
            if len(docs) == 1:
                return docs[0]
            return docs

    if parse_type == 'json':
        with open_s(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    raise TypeError(f"Unsupported parse type: {parse_type}")


def get_cur_ip():
    for interface, addrs in psutil.net_if_addrs().items():
        if any(interface.startswith(prefix) for prefix in ("docker", "lo")):
            continue
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127"):
                return addr.address
    return ''
