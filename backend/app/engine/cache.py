"""Bounded, thread-safe LRU; defensive copies isolate callers."""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock


class QueryCache:
    def __init__(self, maxsize=128):
        if maxsize < 1:
            raise ValueError("maxsize must be positive")
        self.maxsize = maxsize
        self._values = OrderedDict()
        self._lock = RLock()
        self.hits = self.misses = 0

    def get(self, key):
        with self._lock:
            if key not in self._values:
                self.misses += 1
                return None
            self.hits += 1
            self._values.move_to_end(key)
            return deepcopy(self._values[key])

    def put(self, key, value):
        with self._lock:
            self._values[key] = deepcopy(value)
            self._values.move_to_end(key)
            while len(self._values) > self.maxsize:
                self._values.popitem(last=False)
