import os
import platform


class NodeInfo:
    def __init__(self, cpu, ram):
        self.cpu = cpu
        self.ram = ram

    def serialize(self):
        return {'cpu': self.cpu, 'ram': self.ram}


def _cpu_name():
    try:
        from cpuinfo import get_cpu_info
        info = get_cpu_info()
        # у py-cpuinfo >= 5 ключ 'brand' перейменовано на 'brand_raw'
        name = info.get('brand_raw') or info.get('brand') or platform.processor()
    except Exception:
        name = platform.processor() or platform.machine()
    return '%s (%d cores)' % (name, os.cpu_count() or 1)


def _ram():
    try:
        total = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
        return '%.1f GB' % (total / 1024.0 ** 3)
    except (AttributeError, ValueError, OSError):
        return 'unknown'


def get_node_info_for_current_machine():
    return NodeInfo(_cpu_name(), _ram())


def create_node_info(json):
    return NodeInfo(json['cpu'], json['ram'])
