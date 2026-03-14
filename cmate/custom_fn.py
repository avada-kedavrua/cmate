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


def is_port_in_use(port: int, host: str = 'localhost', protocol: str = 'tcp'):
    protocol = protocol.lower()

    protocol_map = {
        'tcp': socket.SOCK_STREAM,
        'udp': socket.SOCK_DGRAM
    }

    if protocol not in protocol_map:
        raise ValueError
    
    sock_type = protocol_map[protocol]
    with socket.socket(socket.AF_INET, sock_type) as sock:
        if protocol.lower() == 'tcp':
            result = sock.connect_ex((host, port))
            return result == 0
        else:
            try:
                sock.bind((host, port))
                return False
            except Exception:
                return True
