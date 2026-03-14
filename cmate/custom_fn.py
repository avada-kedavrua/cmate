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
import shutil
import socket
import subprocess


def path_exists(path: str) -> bool:
    """Check if a path exists.

    Args:
        path (str): Path to check.

    Returns:
        bool: True if the path exists, False otherwise.
    """

    try:
        return os.path.exists(path)
    except TypeError:
        return False


def is_port_in_use(port: int, host: str = "localhost", protocol: str = "tcp") -> bool:
    """Check if a port is in use.

    Args:
        port (int): Port number.
        host (str, optional): Host address. Defaults to "localhost".
        protocol (str, optional): Protocol. Defaults to "tcp".

    Returns:
        bool: True if the port is in use, False otherwise.
    """

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


def image_exists(image_name: str) -> bool:
    """Check if the image exists in the local docker

    Args:
        image_name (str): Image name.

    Returns:
        bool: True if the image exists, False otherwise.
    """
    docker_pth = shutil.which("docker")
    if not docker_pth:
        return False

    cmd = [docker_pth, "inspect", image_name]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return proc.returncode == 0


def get_k8s_namespaces() -> list:
    """Get the list of all namespaces in the current Kubernetes cluster.

    Returns:
        list: List of namespace names.
    """

    kubectl_pth = shutil.which("kubectl")
    if not kubectl_pth:
        return []

    cmd = [
        kubectl_pth,
        "get",
        "namespaces",
        "-o",
        "jsonpath='{.items[*].metadata.name}'",
    ]

    try:
        res = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
    except subprocess.CalledProcessError:
        return []

    return res.strip("'").split()
