import socket


def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    address, port = s.getsockname()
    s.close()
    return port


def get_ip():
    # Оригінал шукав лише адреси 192.* через netifaces (у GCP адреси 10.*,
    # а netifaces не має збірок під нові Python). Беремо IP інтерфейсу,
    # через який ОС маршрутизує трафік назовні (UDP connect нічого не надсилає).
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()
