# -*- coding: utf-8 -*-
# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict, deque
from .util import get_cur_ip


class NAType:
    __instance = None
    
    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance
    
    @staticmethod
    def __repr__():
        return 'NA'
    
    @staticmethod
    def __str__():
        return 'NA'
    
    @staticmethod
    def __bool__():
        return False
    
    @staticmethod
    def __eq__(other):
        return isinstance(other, NAType)
    
    @staticmethod
    def __ne__(other):
        return not isinstance(other, NAType)
    
    @staticmethod
    def __lt__(other):
        return False
    
    @staticmethod
    def __le__(other):
        return False
    
    @staticmethod
    def __gt__(other):
        return False
    
    @staticmethod
    def __ge__(other):
        return False
    
    @staticmethod
    def __hash__():
        return hash('NA')


NA = NAType()


class Namespace(dict):
    def __getitem__(self, name):
        return super().get(name, NA)


class DataSource:
    ns_sym = '::'

    def __init__(self):
        self._nss = defaultdict(Namespace)

        self._nss['global']['cur_ip'] = get_cur_ip()

    def __contains__(self, key):
        try:
            ns, p = self._split(key)
        except ValueError:
            return False
        return ns in self._nss and p in self._nss[ns]

    def __setitem__(self, key, val):
        ns, p = self._split(key)
        self._nss[ns][p] = val

    def __getitem__(self, key):
        ns, p = self._split(key)
        if ns not in self._nss:
            raise KeyError(f"Namespace '{ns}' not found while resolving '{key}'")
        return self._nss[ns][p]

    def __copy__(self):
        new = DataSource()
        for ns, mapping in self._nss.items():
            new._nss[ns] = Namespace(mapping.copy())
        return new
    
    @property
    def namespaces(self):
        return frozenset(self._nss.keys())

    def flatten(self, namespace, data):
        """Flatten nested dict/list into scope paths."""
        if not isinstance(data, (dict, list)):
            # allow flattening a scalar as the root value
            self._nss[namespace]['__root__'] = data
            return

        q = deque([(data, '')])
        while q:
            node, pth = q.popleft()

            key_path = pth if pth else '__root__'
            self._nss[namespace][key_path] = node

            if isinstance(node, dict):
                for k, v in node.items():
                    new_p = f"{pth}.{k}" if pth else f"{k}"
                    q.append((v, new_p))
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    new_p = f"{pth}[{i}]" if pth else f"[{i}]"
                    q.append((item, new_p))

    def copy(self):
        return self.__copy__()

    def _split(self, key):
        parts = key.split(self.ns_sym)
        if len(parts) != 2:
            raise ValueError(f"Invalid key '{key}' (expected exactly one '{self.ns_sym}' separator)")
        return parts[0], parts[1]
