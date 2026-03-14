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

# ***************************************************************************************** #
# To define a custom function, just write its definition here, and use it in the cmate file #
# ***************************************************************************************** #

import os
import socket


def path_exists(path: str):
    try:
        return os.path.exists(path)
    except Exception:
        return False


def is_port_in_use(port: int, host: str = "localhost", protocol: str = "tcp"):
    protocol = protocol.lower()

    protocol_map = {"tcp": socket.SOCK_STREAM, "udp": socket.SOCK_DGRAM}

    if protocol not in protocol_map:
        raise ValueError

    sock_type = protocol_map[protocol]
    with socket.socket(socket.AF_INET, sock_type) as sock:
        if protocol.lower() == "tcp":
            result = sock.connect_ex((host, port))
            return result == 0
        else:
            try:
                sock.bind((host, port))
                return False
            except Exception:
                return True
