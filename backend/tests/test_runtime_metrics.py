from pathlib import Path
from backend.app.runtime_metrics import memory_usage


def test_health_memory_reports_only_numeric_process_and_container_usage(monkeypatch):
    files={'/proc/self/status':'Name:\tpython\nVmRSS:\t20480 kB\nVmHWM:\t30720 kB\n',
           '/sys/fs/cgroup/memory.current':'104857600', '/sys/fs/cgroup/memory.max':'134217728'}
    monkeypatch.setattr(Path,'read_text',lambda self: files[self.as_posix()])
    assert memory_usage()=={'rss_mib':20, 'peak_rss_mib':30, 'container_used_mib':100, 'container_limit_mib':128}


def test_health_memory_remains_available_without_linux_files(monkeypatch):
    def unavailable(_): raise FileNotFoundError
    monkeypatch.setattr(Path,'read_text',unavailable)
    assert memory_usage()=={}
