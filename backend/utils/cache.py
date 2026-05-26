# utils/cache.py
import time
from typing import Any, Callable

class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds
        self._data: Any = None
        self._ts: float = 0.0

    def get(self, loader: Callable[[], Any]) -> Any:
        """
        Restituisce i dati cached se validi, altrimenti li ricarica tramite la funzione loader.
        """
        now = time.time()
        if self._data is None or (now - self._ts) > self._ttl:
            self._data = loader()
            self._ts = now
        return self._data

    def invalidate(self):
        """
        Forza la scadenza immediata della cache.
        """
        self._data = None
        self._ts = 0.0
