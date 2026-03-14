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

from collections import defaultdict, deque
from typing import Dict, Tuple

from .util import get_cur_ip


class NAType:
    """Sentinel for missing/inapplicable values. Falsy, not equal to None."""

    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __repr__(self):
        return "NA"

    def __str__(self):
        return "NA"

    def __bool__(self):
        return False

    def __hash__(self):
        return hash("NA")

    def __eq__(self, other):
        return isinstance(other, NAType)

    def __ne__(self, other):
        return not isinstance(other, NAType)

    def __lt__(self, other):
        return False

    def __le__(self, other):
        return False

    def __gt__(self, other):
        return False

    def __ge__(self, other):
        return False


NA = NAType()


class Namespace(dict):
    """A dict that returns NA for missing keys instead of raising KeyError."""

    def __getitem__(self, name):
        return super().get(name, NA)


class NamespacedKey:
    """
    Encapsulates a (namespace, path) pair so call sites never hand-roll
    'ns::path' strings. Equality and hashing are based on the pair.
    """

    SEP = "::"

    __slots__ = ("namespace", "path")

    def __init__(self, namespace: str, path: str):
        self.namespace = namespace
        self.path = path

    @classmethod
    def parse(cls, raw: str) -> "NamespacedKey":
        """Parse 'ns::path' into a NamespacedKey; raises ValueError if malformed."""
        parts = raw.split(cls.SEP)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid key {raw!r}: expected exactly one {cls.SEP!r} separator"
            )
        return cls(parts[0], parts[1])

    def __str__(self):
        return f"{self.namespace}{self.SEP}{self.path}"

    def __repr__(self):
        return f"NamespacedKey({self.namespace!r}, {self.path!r})"

    def __eq__(self, other):
        if isinstance(other, NamespacedKey):
            return self.namespace == other.namespace and self.path == other.path
        return NotImplemented

    def __hash__(self):
        return hash((self.namespace, self.path))


class DataSource:
    """
    Two-level key-value store: namespace → path → value.

    Accepts either NamespacedKey objects or raw 'ns::path' strings as keys.
    """

    def __init__(self):
        self._nss: Dict[str, Namespace] = defaultdict(Namespace)
        self._nss["global"]["cur_ip"] = get_cur_ip().compressed

    def _resolve(self, key) -> Tuple[str, str]:
        """Return (namespace, path) from a NamespacedKey or raw string."""
        if isinstance(key, NamespacedKey):
            return key.namespace, key.path
        parsed = NamespacedKey.parse(key)
        return parsed.namespace, parsed.path

    def __contains__(self, key) -> bool:
        try:
            ns, p = self._resolve(key)
        except ValueError:
            return False
        return ns in self._nss and p in self._nss[ns]

    def __getitem__(self, key):
        ns, p = self._resolve(key)
        if ns not in self._nss:
            raise KeyError(f"Namespace {ns!r} not found while resolving {key!r}")
        return self._nss[ns][p]

    def __setitem__(self, key, val):
        ns, p = self._resolve(key)
        self._nss[ns][p] = val

    def __delitem__(self, key):
        ns, p = self._resolve(key)
        if ns not in self._nss:
            raise KeyError(f"Namespace {ns!r} not found while resolving {key!r}")
        del self._nss[ns][p]

    def __copy__(self):
        new = DataSource.__new__(DataSource)
        new._nss = defaultdict(Namespace)
        for ns, mapping in self._nss.items():
            new._nss[ns] = Namespace(mapping.copy())
        return new

    def copy(self):
        return self.__copy__()

    def flatten(self, namespace: str, data) -> None:
        """Recursively expand a dict/list into dotted paths under *namespace*."""
        q = deque([(data, "")])
        while q:
            node, pth = q.popleft()
            key_path = pth if pth else "__root__"
            self._nss[namespace][key_path] = node

            if isinstance(node, dict):
                for k, v in node.items():
                    new_p = f"{pth}.{k}" if pth else k
                    q.append((v, new_p))
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    new_p = f"{pth}[{i}]" if pth else f"[{i}]"
                    q.append((item, new_p))

    def unflatten(self, namespace: str, data) -> None:
        """Remove all dotted paths that *flatten* would have created for *data*."""
        q = deque([(data, "")])
        while q:
            node, pth = q.popleft()
            key_path = pth if pth else "__root__"
            del self._nss[namespace][key_path]

            if isinstance(node, dict):
                for k, v in node.items():
                    new_p = f"{pth}.{k}" if pth else k
                    q.append((v, new_p))
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    new_p = f"{pth}[{i}]" if pth else f"[{i}]"
                    q.append((item, new_p))
