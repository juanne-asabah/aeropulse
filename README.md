# AeroPulse: Global Air Quality & Health Dashboard

AeroPulse is a web app displaying live air quality and weather for major cities worldwide to help users—especially those with asthma, children, the elderly, and outdoor athletes—decide if it is safe to be outside. Users can search, filter, sort, compare cities, and look up any city on Earth.

The app runs on two web servers (`Web01` and `Web02`) behind an HAProxy load balancer (`Lb01`).

## Links

| Item | Link |
| :--- | :--- |
| GitHub repository | `https://github.com/juanne-asabah/aeropulse` |
| Live site (via load balancer) | https://www.juanne-lab.abrdns.com |
| Load balancer IP | `13.135.251.150` |
| Web01 (direct) | `http://35.177.108.124:5001` |
| Web02 (direct) | `http://18.171.134.109:5002` |
| Demo video (under 2 min) | `https://youtu.be/<your-video-id>` |

## API Keys & Authentication
- **API key:** None required (Open-Meteo is free without a key).
- **Login:** None (no user accounts).

## Features
- **Live data (12 major cities):** US AQI, temperature, PM2.5, PM10, UV index, CO, and NO2 (cards show AQI and temperature; the table and advisory popup show all metrics).
- **Search & global lookup:** Search tracked cities by city/country name or look up any city worldwide.
- **Filter & sort:** Filter by air quality (`Good`, `Moderate`, `Sensitive`, `Unhealthy`); sort by air quality, temperature, or name.
- **City comparison:** Compare two cities side by side (`/api/compare?city1=Tokyo&city2=Delhi`).
- **Views & advisories:** Switch between cards and table views, with a health advisory popup per city.
- **In-memory caching:** Caches API responses for 5 minutes to speed up repeat requests and stay within Open-Meteo rate limits (cards show `Cache: HIT` or `Cache: MISS`).
- **Error handling:**
  - Falls back to sample data with a user warning if Open-Meteo is unreachable.
  - Displays a "not found" message for nonexistent cities.
  - Shows an error banner with a **Retry** button on failed requests.
- **Load balancer test:** Built-in button sends 10 requests and displays which server handled each.
- **Security:** Sets safe response headers (`X-Content-Type-Options`, `X-Frame-Options`), stores no secrets in code, and excludes `.env` from Git.

## APIs Used
Data is provided by [Open-Meteo](https://open-meteo.com) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (thanks to the Open-Meteo team):
- [Air Quality API](https://open-meteo.com/en/docs/air-quality-api)
- [Weather Forecast API](https://open-meteo.com/en/docs)
- [Geocoding API](https://open-meteo.com/en/docs/geocoding-api)

## API Endpoints

| Endpoint | Description |
| :--- | :--- |
| `GET /` | Dashboard web page |
| `GET /api/cities?search=&category=&sort_by=` | List cities with search, filter, and sort |
| `GET /api/search?q=<city>` | Look up any city worldwide |
| `GET /api/compare?city1=&city2=` | Compare two cities |
| `GET /api/health` | Health check (includes responding `server_id`) |
| `GET /api/cache-stats` | Cache hit/miss statistics |

## Project Structure

```text
app.py                      Flask backend (API + serves frontend)
static/index.html           Web page
static/css/style.css        Styles
static/js/app.js            Frontend logic
haproxy/haproxy.cfg         HAProxy configuration for Lb01
deploy/systemd/             Systemd service files for Web01 and Web02
tests/test_app.py           Automated test suite (9 tests)
run_cluster.py              Local simulator for Web01, Web02, and a load balancer
Dockerfile                  Optional container build
.dockerignore               Files excluded from Docker image
.env.example                Environment variables template
requirements.txt            Python dependencies
