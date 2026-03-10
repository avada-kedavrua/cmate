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

import concurrent.futures
import json
import os
import socket
from enum import Enum
from typing import Any, Optional

import psutil
import yaml
from colorama import Fore, Style
from msguard.security import open_s


class Severity(Enum):
    INFO    = "[RECOMMEND]"
    WARNING = "[WARNING]"
    ERROR   = "[NOK]"

    def _rank(self) -> int:
        # Canonical ordering: INFO < WARNING < ERROR
        _order = ["INFO", "WARNING", "ERROR"]
        return _order.index(self.name)

    def __lt__(self, other: "Severity") -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._rank() < other._rank()

    def __le__(self, other: "Severity") -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._rank() <= other._rank()

    def __gt__(self, other: "Severity") -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._rank() > other._rank()

    def __ge__(self, other: "Severity") -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._rank() >= other._rank()

    def __str__(self) -> str:
        return f"{self.color_code}{self.value}{Fore.RESET}"

    @property
    def color_code(self) -> str:
        return {
            Severity.INFO:    Style.BRIGHT + Fore.CYAN,
            Severity.WARNING: Style.BRIGHT + Fore.YELLOW,
            Severity.ERROR:   Style.BRIGHT + Fore.RED,
        }[self]


def _ext_to_type(path: str) -> str:
    _, ext = os.path.splitext(path)
    return ext.lstrip(".").lower()


def load(path: str, parse_type: Optional[str] = None) -> Any:
    """
    Load a JSON or YAML file.  parse_type defaults to the file extension.
    Multi-document YAML returns a list; single-document returns the object directly.
    """
    if parse_type is None:
        parse_type = _ext_to_type(path)

    if parse_type in ("yaml", "yml"):
        with open_s(path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        if len(docs) == 0:
            return None
        return docs[0] if len(docs) == 1 else docs

    if parse_type == "json":
        with open_s(path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise TypeError(f"Unsupported parse type: {parse_type!r}")


def get_cur_ip() -> str:
    """Return the first non-loopback, non-docker IPv4 address, or empty string."""
    for interface, addrs in psutil.net_if_addrs().items():
        if any(interface.startswith(p) for p in ("docker", "lo")):
            continue
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127"):
                return addr.address
    return ""


def func_timeout(timeout: int, func, *args, **kwargs):
    """
    Run *func* with a wall-clock timeout using a thread pool.
    Works on all platforms and in any thread (unlike SIGALRM).
    Raises TimeoutError if the function does not complete in time.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"Function {func.__qualname__!r} timed out after {timeout}s"
            )