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
CACHE_TTL = int(os.environ.get("CACHE_TTL_SECONDS", 300))
ENABLE_FALLBACK = (os.environ.get("ENABLE_FALLBACK", "True").lower() in ("true", "1", "yes"))

app = Flask(__name__, static_folder="static", static_url_path="")
START_TIME = time.time()
logging.basicConfig(level=logging.INFO, format=f"[%(asctime)s] [{SERVER_ID}] [%(levelname)s] %(message)s")
logger = logging.getLogger("AeroPulse")

class InMemoryTTLCache:
  def __init__(self, default_ttl=300):
    self._data, self._lock, self.default_ttl = {}, threading.Lock(), default_ttl
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
      self._data[key] = (value, time.time() + (self.default_ttl if ttl is None else ttl))

  def stats(self):
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
  ("Paris", "France", 48.8566, 2.3522, 38, 15.1, 65, 9.1, 16.7, 3.8),
  ("Nairobi", "Kenya", -1.2921, 36.8219, 45, 23.4, 58, 11.0, 21.0, 7.5),
  ("Sydney", "Australia", -33.8688, 151.2093, 24, 21.0, 62, 5.9, 12.3, 6.2),
  ("Delhi", "India", 28.6139, 77.2090, 178, 29.8, 45, 108.5, 195.0, 6.8),
  ("Cairo", "Egypt",30.0444, 31.2357, 112, 28.0, 40, 40.2, 85.0, 7.0),
  ("São Paulo", "Brazil", -23.5505, -46.6333, 68, 24.5, 70, 20.3, 34.0, 8.0),
  ("Singapore", "Singapore", 1.3521, 103.8198, 49, 30.5, 82, 12.0, 20.5, 9.2),
  ("Berlin", "Germany", 52.5200, 13.4050, 35, 13.0, 68, 8.4, 15.2, 3.0),
  ("Toronto", "Canada", 43.6532, -79.3832, 31, 11.5, 60, 7.5, 13.8, 4.0),
]
DEFAULT_CITIES = [{"name": c[0], "country": c[1], "lat": c[2], "lon": c[3]} for c in CITY_DATA]
FALLBACK = {c[0]: c[4:] for c in CITY_DATA}

FIELDS = {"european_aqi": ("aqi_european", 20), "temperature_2m": ("temperature", 20.0),
          "apparent_temperature": ("feels_like", 20.0), "relative_humidity_2m": ("humidity", 50),
          "wind_speed_10m": ("wind_speed", 5.0), "uv_index": ("uv_index", 3.0), "pm2_5": ("pm2_5", 8.0),
          "pm10": ("pm10", 15.0), "carbon_monoxide": ("co", 200.0), "nitrogen_dioxide": ("no2", 15.0),
          "sulphur_dioxide": ("so2", 5.0), "ozone": ("o3", 45.0), "weather_code": ("weather_code", 0)}

SOURCES = [("https://air-quality-api.open-meteo.com/v1/air-quality",
            "european_aqi,us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,uv_index"),
            ("https://api.open-meteo.com/v1/forecast",
            "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m")]

@app.before_request
def start_timer():
  request.environ["t0"] = time.time()

@app.after_request
def add_headers(response):
  response.headers["X-Served-By"] = SERVER_ID
  response.headers["X-Server-Port"] = str(PORT)
  response.headers["X-Response-Time-Ms"] = str(round((time.time() - request.environ["t0"]) * 1000, 2))
  response.headers["X-Content-Type-Options"] = "nosniff"
  response.headers["X-Frame-Options"] = "SAMEORIGIN"
  return response

def get_aqi_category(us_aqi):
  for limit, label in [(50, "Good"), (100, "Moderate"), (150, "Unhealthy for Sensitive Groups"), (200, "Unhealthy"), (300, "Very Unhealthy")]:
    if us_aqi <= limit:
      return label
  return "Hazardous"

def make_metric(city, data, **extra):
  us_aqi = int(data.get("us_aqi") or 30)
  metric = {out: data.get(src, default) for src, (out, default) in FIELDS.items()}
  return {
    "name" : city["name"], "country": city["country"], "latitude": city["lat"], "longitude": city["lon"],
    "aqi_us": us_aqi, "category": get_aqi_category(us_aqi), **metric,
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **extra
  }
def fetch_city_metrics(city):
  key = f"city_metrics_{city['name']}"
  cached = cache.get(key)
  if cached:
    return {
      **cached, "cache_source": "HIT"
    }
  try:
    data = {}
    for url, fields in SOURCES:
      res = requests.get(url, params={"latitude": city["lat"], "longitude": city["lon"], "current": fields}, timeout=3.5)
      res.raise_for_status()
      data.update(res.json().get("current", {}))
    metric = make_metric(city, data, is_fallback=False, cache_source="MISS")
    cache.set(key, metric)
    return metric
  except Exception as err:
    logger.warning(f"External API error for {city['name']}: {err}")
    if not ENABLE_FALLBACK:
      raise
    aqi, temp, hum, pm25, pm10, uv = FALLBACK.get(city["name"], (40, 20.0, 50, 10.0, 20.0, 4.0))
    data = {
      "us_aqi": aqi, "european_aqi": 25, "temperature_2m": temp, "apparent_temperature": temp,
      "relative_humidity_2m": hum, "pm2_5": pm25, "pm10": pm10, "uv_index": uv, "wind_speed_10m": 10.0,
      "carbon_monoxide": 210.0, "nitrogen_dioxide": 18.0, "sulphur_dioxide": 4.0, "ozone": 50.0,
      "weather_code": 1
    }
    metric = make_metric(city, data, is_fallback=True, fallback_reason=str(err), cache_source="FALLBACK")
    cache.set(key, metric, ttl=60)
    return metric

def geocode(name):
  res = requests.get("https://geocoding-api.open-meteo.com/v1/search", timeout=3.5, params={"name": name, "count": 1, "language": "en", "format": "json"})
  res.raise_for_status()
  if not res.json().get("results"):
    raise ValueError(f"City '{name}' not found")
  hit = res.json()["results"][0]
  return {"name": hit["name"], "country": hit.get("country", "Unknown"), "lat": hit["latitude"], "lon": hit["longitude"]}

@app.route("/")
def index():
  return send_from_directory(app.static_folder, "index.html")

@app.route("/api/health")
def health_check():
  return jsonify(status="healthy", service="AeroPulse API", server_id=SERVER_ID, port=PORT, 
                 uptime_seconds=round(time.time() - START_TIME, 2), cache=cache.stats(), 
                 timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

@app.route("/api/cache-stats")
def cache_stats():
  return jsonify(server_id=SERVER_ID, cache=cache.stats())

@app.route("/api/cache/clear", methods=["POST"])
def cache_clear():
  cache.clear()
  return jsonify(message="Cache successfully cleared", server_id=SERVER_ID)

@app.route("/api/cities")
def list_cities():
  search = request.args.get("search", "").strip().lower()
  category = request.args.get("category", "").strip().lower()
  field, _, direction = request.args.get("sort_by", "aqi_asc").strip().lower().partition("_")

  with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(fetch_city_metrics, DEFAULT_CITIES))

  results = [c for c in results if search in c["name"].lower() or search in c["country"].lower()]
  ranges = {"good": (0, 50), "moderate" : (51, 100), "sensitive": (101, 150), "unhealthy": (151, 9999)}
  if category in ranges:
    results = [c for c in results if ranges[category][0]  <= c["aqi_us"] <= ranges[category][1]]
  sort_keys = {"aqi": "aqi_us", "temp": "temperature", "name": "name"}
  if field in sort_keys:
    results.sort(key=lambda c: c[sort_keys[field]], reverse=(direction == "desc"))

  by_aqi = sorted(results, key=lambda c: c["aqi_us"])
  return jsonify(server_id=SERVER_ID, total_cities=len(results), cities=results, summary={
    "average_aqi": round(sum(c["aqi_us"] for c in results) / len(results), 1) if results else 0,
    "cleanest_city": by_aqi[0]["name"] if results else "N/A",
    "highest_risk_city": by_aqi[-1]["name"] if results else "N/A"
  })

@app.route("/api/search")
def search_global_city():
  query = request.args.get("q", "").strip()
  if not query:
    return jsonify(error="Missing search query parameter 'q'"), 400
  try:
    return jsonify(fetch_city_metrics(geocode(query)))
  except ValueError as err:
    return jsonify(error=str(err)), 404
  except requests.exceptions.Timeout:
    return jsonify(error="External geocoding API timed out. Please try again."), 504
  except Exception as err:
    logger.error(f"Search error for '{query}' : {err}")
    return jsonify(error=f"Failed to retrieve data: {err}"), 500
  
@app.route("/api/compare")
def compare_cities():
  names = [request.args.get("city1", "").strip(), request.args.get("city2", "").strip()]
  if not all(names):
    return jsonify(error="Both 'city1' and 'city2' query parameters are required"), 400

  def resolve(name):
    known = next((c for c in DEFAULT_CITIES if c["name"].lower() == name.lower()), None)
    return fetch_city_metrics(known or geocode(name))

  try:
    m1, m2 = resolve(names[0]), resolve(names[1])
    return jsonify(server_id=SERVER_ID, comparison={
      "cleaner_city": m1["name"] if m1["aqi_us"] < m2["aqi_us"] else m2["name"],
      "aqi_difference": abs(m1["aqi_us"] - m2["aqi_us"]), "city1": m1, "city2": m2
    })
  except ValueError as err:
    return jsonify(error=str(err)), 404
  except Exception as err:
    return jsonify(error=f"Comparison failed: {err}"), 500

if __name__ == "__main__":
  logger.info(f"Starting AeroPulse service on {HOST}:{PORT} (ID: {SERVER_ID})")
  app.run(host=HOST, port=PORT, debug=False)