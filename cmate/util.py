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
import signal
import socket
import ipaddress
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import yaml
import psutil
from colorama import Fore, Style


class ParseFormatError(ValueError):
    """Exception raised when a file format is not supported."""
    pass


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


class ParseFormat(Enum):
    JSON    = ".json"
    YAML    = ".yaml"
    YML     = ".yml"
    UNKNOWN = "unknown"


def _parse_format_from_path(path: Path) -> ParseFormat:
    """Return the parse format from the file path."""
    try:
        return ParseFormat(path.suffix)
    except ValueError:
        return ParseFormat.UNKNOWN


def load_from_file(path: Path, parse_format: ParseFormat = ParseFormat.UNKNOWN) -> Any:
    if parse_format == ParseFormat.UNKNOWN:
        parse_format = _parse_format_from_path(path)

    if not isinstance(path, Path):
        path = Path(path)

    path = path.resolve()
    text = path.read_text(encoding="utf-8")

    if parse_format == ParseFormat.YAML or parse_format == ParseFormat.YML:
        if not text:
            return None

        docs = list(yaml.safe_load_all(text))
        return docs[0] if len(docs) == 1 else docs

    if parse_format == ParseFormat.JSON:
        return json.loads(text)

    raise ParseFormatError(f"Unsupported parse format: {parse_format}")


def get_cur_ip() -> Optional[ipaddress.IPv4Address]:
    """Return the first non-loopback, non-docker IPv4 address, or None if not found."""
    for interface, addrs in psutil.net_if_addrs().items():
        if any(interface.startswith(p) for p in ("docker", "lo")):
            continue
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127"):
                return ipaddress.IPv4Address(addr.address)
    return None


def func_timeout(timeout: float, func: Callable, *args, **kwargs):
    """Execute a function with a timeout.
    
    Args:
        timeout (float): The timeout duration in seconds.
        func (Callable): The function to execute.
        *args: The arguments to pass to the function.
        **kwargs: The keyword arguments to pass to the function.
    
    Raises:
        TimeoutError: If the function takes longer than the timeout.
    """
    def handler(signum, frame):
        raise TimeoutError(f"Function '{func.__qualname__}' timed out after {timeout} seconds.")

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)

    try:
        return func(*args, **kwargs)
    finally:
        signal.alarm(0)
