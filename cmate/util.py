# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025-2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          `http://license.coscl.org.cn/MulanPSL2`
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

import json
import os
import signal
import socket
from enum import Enum
from functools import total_ordering
from typing import Any, Optional

import psutil

import yaml
from colorama import Fore, Style
from msguard.security import open_s


@total_ordering
class Severity(Enum):
    INFO = "[RECOMMEND]"
    WARNING = "[WARNING]"
    ERROR = "[NOK]"

    _ORDER_MAP = {"INFO": 0, "WARNING": 1, "ERROR": 2}

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
            Severity.ERROR: Style.BRIGHT + Fore.RED,
        }[self]


def _ext_to_type(path: str) -> str:
    _, ext = os.path.splitext(path)
    if ext.startswith("."):
        ext = ext[1:]
    return ext.lower()


def load(path: str, parse_type: Optional[str] = None) -> Any:
    """Load configuration from `path` and return parsed object.

    - If `parse_type` is not provided, it's derived from file extension.
    - Supported types: `json`, `yaml`/`yml`.
    """
    if parse_type is None:
        parse_type = _ext_to_type(path)

    if parse_type in ("yaml", "yml"):
        with open_s(path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            if len(docs) == 0:
                return None
            if len(docs) == 1:
                return docs[0]
            return docs

    if parse_type == "json":
        with open_s(path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise TypeError(f"Unsupported parse type: {parse_type}")


def get_cur_ip():
    for interface, addrs in psutil.net_if_addrs().items():
        if any(interface.startswith(prefix) for prefix in ("docker", "lo")):
            continue
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127"):
                return addr.address
    return ""


def func_timeout(timeout, func, *args, **kwargs):
    def handler(signum, frame):
        raise TimeoutError(
            f"Function '{func.__qualname__}' timed out after {timeout} seconds."
        )

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)

    try:
        return func(*args, **kwargs)
    finally:
        signal.alarm(0)
