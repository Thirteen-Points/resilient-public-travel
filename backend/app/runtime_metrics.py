"""Read-only process/container memory diagnostics for deployment health."""
from pathlib import Path


def memory_usage():
    values = {}
    try:
        for line in Path('/proc/self/status').read_text().splitlines():
            key = {'VmRSS:': 'rss_mib', 'VmHWM:': 'peak_rss_mib'}.get(line.split()[0])
            if key:
                values[key] = round(int(line.split()[1]) / 1024, 2)
    except (OSError, ValueError):
        pass
    for filename, key in [('memory.current', 'container_used_mib'), ('memory.max', 'container_limit_mib')]:
        try:
            raw = (Path('/sys/fs/cgroup') / filename).read_text().strip()
            if raw.isdecimal():
                values[key] = round(int(raw) / 1048576, 2)
        except OSError:
            pass
    return values
