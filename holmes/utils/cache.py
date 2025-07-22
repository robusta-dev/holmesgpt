import json
import time
import zlib
from threading import Timer
from typing import Any, Dict, Optional


class SetEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, set):
            return list(o)
        return json.JSONEncoder.default(self, o)


def compress(data):
    json_str = json.dumps(data, cls=SetEncoder)
    json_bytes = json_str.encode("utf-8")
    compressed = zlib.compress(json_bytes, level=1)

    return compressed


def decompress(compressed_data):
    try:
        decompressed = zlib.decompress(compressed_data)
        json_str = decompressed.decode("utf-8")
        data = json.loads(json_str)
        return data
    except Exception as e:
        raise Exception(f"Decompression failed: {str(e)}")


class TTLCache:
    def __init__(self, ttl_seconds: int):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl_seconds
        self._evict_interval = max(self._ttl / 10, 60)
        self._evict_timer = None
        self._start_evict_timer()

    def _start_evict_timer(self):
        self._evict_timer = Timer(self._evict_interval, self._evict)
        self._evict_timer.daemon = (
            True  # Allow the program to exit even if timer is alive
        )
        self._evict_timer.start()

    def _evict(self):
        current_time = time.time()
        expired_keys = [
            key for key, item in self._cache.items() if item["expiry"] <= current_time
        ]

        for key in expired_keys:
            del self._cache[key]

        self._start_evict_timer()

    def set(self, key: str, value: Any) -> None:
        expiry = time.time() + self._ttl

        self._cache[key] = {"value": compress(value), "expiry": expiry}

    def get(self, key: str) -> Optional[Any]:
        item = self._cache.get(key)

        if item is None:
            return None

        if item["expiry"] <= time.time():
            del self._cache[key]
            return None

        return decompress(item["value"])

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()

    def __del__(self):
        if self._evict_timer:
            self._evict_timer.cancel()
