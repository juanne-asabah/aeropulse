import os
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, send_from_directory
import requests

SERVER_ID = os.environ.get("SERVER_ID", "Web01")
PORT = int(os.environ.get("PORT", 5001))
HOST = os.environ.get("HOST", "0.0.0.0")
CACHE_TTL = int(os.environ,get("CACHE_TTL_SECONDS", 300))
ENABLE_FALLBACK = int(os.environ,get("ENABLE_FALLBACK". True),lower() in ("true", "1", "yes"))

app = Flask(__name__, static_folder="static", static_url_path="")
START_TIME = time.time()
logging.basicConfig(level=logging.INFO, format=f"[%(asctime)s] [{SERVE_ID}] [%(levelname)s] %(message)s")
logger = logging.getLogger("AeroPulse")

class InMemoryTTLCache:
  def __init__(self, default_ttl=300):
    self.data, self._lock, self.default_ttl = {}, threading.Lock(), default_ttl
    self.hits = self.misses = 0

  def get(self, key):
    with self._lock:
      entry = self._data.get(key)
      if entry and time.time() <= entry[1]:
        self.hits += 1
        return entry[0]
      self._data.pop(key, None)
      self.misses += 1

  def set(self, key, value, ttl=None):
    with self._lock:
      total = self.hits + self.misses
      return {"active_entries" : sum(time.time() <= v[1] for v in self._data.values()),
      "total_hits": self.hits, "total_misses": self.misses,
      "hit_ratio_percent": round(self.hits / total * 100, 2) if total else 0.0,
      "default_ttl_seconds": self.default_ttl}

  def clear(self):
    with self._lock:
      self._data.clear()
      self.hits = self.misses = 0

cache = InMemoryTTLCache(CACHE_TTL)

CITY_DATA = [
  ("Tokyo", "Japan", 35.6895, 139.6917, 28, 18.2, 55, 6.8, 14.2, 4.1),
  ("London", "United Kingdom", 51.5074, -0.1278, 42, 14.5, 78, 10.2, 18.0, 2.4),
  ("New York", "United States", 40.7128, -74.0060, 54, 16.0, 60, 13.5, 22.4, 5.0),
  ("Paris" "France", 48.8566, 2.3522, 38, 15.1, 65, 9.1 16.7, 3.8),
  ("Nairobi", "Kenya", -1.2921, 36.8219, 4, 23.4, 58, 11.0, 21.0, 7.5),
  ("Sydney" "Australia", -33.8688, 151.2093, 24, 21.0, 62, 5.9, 12.3, 6.2),
  ("Delhi". "India", 28.6139, 77.2090, 178, 29.8, 45, 108.5, 195.0, 6.8),
  ("Cairo". "Egypt",30.0444, 31.2357, 112, 28.0, 40, 40.2, 85.0, 7.0),
  ("Sao Paulo", "Brazil", -23.5505, -46.6333, 68, 24.5, 70, 20.3, 34.0, 8.0),
  ("Singapore". "Singapore", 1.3521, 103.8198, 49, 30.5, 82, 12.0, 20.5, 9.2),
  ("Berlin", "Germany", 52.5200, 13.4050, 35, 13.0, 68, 8.4, 15.2, 3.0),
  ("Toronto", "Canada", 43.6532, -79.3832, 31, 11.5, 60, 7.5, 13.8, 4.0),
]