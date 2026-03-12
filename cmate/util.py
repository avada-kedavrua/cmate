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

import ipaddress
import json
import logging
import io
import signal
import socket
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, List, Tuple, Union

import psutil

import yaml
from colorama import Fore, Style


class ParseFormatError(ValueError):
    """Exception raised when a file format is not supported."""
    pass


class Severity(Enum):
    INFO = "[RECOMMEND]"
    WARNING = "[WARNING]"
    ERROR = "[NOK]"

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
            Severity.INFO: Style.BRIGHT + Fore.CYAN,
            Severity.WARNING: Style.BRIGHT + Fore.YELLOW,
            Severity.ERROR: Style.BRIGHT + Fore.RED,
        }[self]


class ParseFormat(Enum):
    JSON = ".json"
    YAML = ".yaml"
    YML = ".yml"
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
        raise TimeoutError(
            f"Function '{func.__qualname__}' timed out after {timeout} seconds."
        )

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)

    try:
        return func(*args, **kwargs)
    finally:
        signal.alarm(0)


class RecordCollection:
    def __init__(self, records: List[logging.LogRecord], text: str = "") -> None:
        self._records = list(records)
        self._text = text

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)

    def __bool__(self) -> bool:
        return bool(self._records)

    def __getitem__(self, index: int) -> logging.LogRecord:
        return self._records[index]

    def __repr__(self) -> str:
        return f"<RecordCollection count={len(self)}>"

    @property
    def count(self) -> int:
        return len(self._records)

    @property
    def messages(self) -> List[str]:
        return [r.getMessage() for r in self._records]

    @property
    def tuples(self) -> List[Tuple[str, int, str]]:
        return [(r.name, r.levelno, r.getMessage()) for r in self._records]

    @property
    def text(self) -> str:
        return self._text

    def of_level(self, level: Union[str, int]) -> 'RecordCollection':
        if isinstance(level, str):
            level_no = logging.getLevelName(level.upper())
            if not isinstance(level_no, int):
                raise ValueError(f"Unknown log level: {level!r}")
        else:
            level_no = level
        return RecordCollection([r for r in self._records if r.levelno == level_no])

    def of_logger(self, name: str) -> 'RecordCollection':
        return RecordCollection([r for r in self._records if r.name == name])

    def containing(self, substring: str) -> 'RecordCollection':
        return RecordCollection(
            [r for r in self._records if substring in r.getMessage()]
        )


class LogCapture:
    """A context manager that captures log records."""
    _DEFAULT_FMT = "%(levelname)-8s %(name)s:%(filename)s:%(lineno)d  %(message)s"

    def __init__(
        self,
        *,
        level: int = logging.NOTSET,
        logger: Optional[logging.Logger] = None,
        propagate: bool = False,
        fmt: Optional[str] = None,
    ) -> None:
        self._level = level
        self._target_logger: logging.Logger = logger or logging.getLogger()
        self._propagate = propagate
        self._fmt = fmt or self._DEFAULT_FMT

        self._handler: Optional[CaptureHandler] = None
        self._saved_handlers: List[logging.Handler] = []
        self._saved_level: int = logging.NOTSET
        self._saved_propagate: bool = True
        self.records: RecordCollection = RecordCollection([])

    def __enter__(self) -> 'LogCapture':
        lg = self._target_logger

        self._saved_handlers = lg.handlers[:]
        self._saved_level = lg.level
        self._saved_propagate = lg.propagate

        for h in lg.handlers[:]:
            lg.removeHandler(h)

        self._handler = _CaptureHandler(self._fmt)
        self._handler.setLevel(self._level)
        lg.addHandler(self._handler)
        lg.setLevel(self._level)
        lg.propagate = self._propagate

        return self

    def __exit__(self, *_) -> None:
        lg = self._target_logger

        lg.removeHandler(self._handler)
        for h in self._saved_handlers:
            lg.addHandler(h)
        lg.setLevel(self._saved_level)
        lg.propagate = self._saved_propagate

        self.records = RecordCollection(self._handler.records, self._handler.flush_text())
        self._handler.close()
        self._handler = None

    @property
    def live(self) -> RecordCollection:
        if self._handler is None:
            raise RuntimeError("LogCapture is not active")
        return RecordCollection(self._handler.records)

    def clear(self) -> None:
        if self._handler is None:
            raise RuntimeError("LogCapture is not active")
        self._handler.reset()

    def __repr__(self) -> str:
        state = "active" if self._handler else "closed"
        return f"<LogCapture [{state}] records={len(self.records)}>"


class _CaptureHandler(logging.Handler):
    def __init__(self, fmt: str) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter(fmt))
        self.records: List[logging.LogRecord] = []
        self._stream = io.StringIO()

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
        try:
            self._stream.write(self.format(record) + "\n")
        except Exception:
            self.handleError(record)

    def reset(self) -> None:
        self.records.clear()
        self._stream.truncate(0)
        self._stream.seek(0)

    def flush_text(self) -> str:
        return self._stream.getvalue()
