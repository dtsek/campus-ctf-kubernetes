import os
import subprocess
from collections import Counter
from datetime import date, timedelta

import requests
from flask import Flask, abort, render_template_string, request

app = Flask(__name__)

# Static list of Estonian cities with coordinates for the free Open-Meteo
# forecast API
CITIES = {
    "tallinn": {"name": "Tallinn", "lat": 59.4370, "lon": 24.7536},
    "tartu": {"name": "Tartu", "lat": 58.3780, "lon": 26.7290},
    "narva": {"name": "Narva", "lat": 59.3772, "lon": 28.1903},
    "parnu": {"name": "Pärnu", "lat": 58.3859, "lon": 24.4971},
    "kuressaare": {"name": "Kuressaare", "lat": 58.2529, "lon": 22.4866},
}

# Minimal subset of WMO weather codes used by Open-Meteo.
WEATHER_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Depositing rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Drizzle", "🌦️"),
    55: ("Dense drizzle", "🌦️"),
    61: ("Light rain", "🌧️"),
    63: ("Rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    71: ("Light snow", "🌨️"),
    73: ("Snow", "🌨️"),
    75: ("Heavy snow", "🌨️"),
    80: ("Rain showers", "🌦️"),
    81: ("Rain showers", "🌦️"),
    82: ("Violent rain showers", "⛈️"),
    95: ("Thunderstorm", "⛈️"),
}


def describe_code(code):
    return WEATHER_CODES.get(code, ("Unknown", "❓"))


# Parts of the day, as (key, label, icon, local hours).
PERIODS = [
    ("morning", "Morning", "🌅", range(6, 12)),
    ("afternoon", "Afternoon", "☀️", range(12, 18)),
    ("evening", "Evening", "🌙", list(range(18, 24)) + list(range(0, 6))),
]


def summarize_period(temps, codes):
    """Min/max temperature and the most frequent weather code of some hours."""
    code = max(Counter(codes).items(), key=lambda kv: (kv[1], kv[0]))[0]
    desc, icon = describe_code(code)
    return {
        "icon": icon,
        "desc": desc,
        "tmax": round(max(temps)),
        "tmin": round(min(temps)),
    }


def fetch_forecast(lat, lon):
    """3-day forecast (morning/afternoon/evening) from the free Open-Meteo API."""
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min",
                "hourly": "weathercode,temperature_2m",
                "forecast_days": 3,
                "timezone": "auto",
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        daily = data["daily"]
        hourly = data["hourly"]
    except (requests.RequestException, KeyError, ValueError):
        app.logger.exception("Forecast fetch failed")
        return []

    # Group hourly values by (date, hour) using the city's local time.
    by_hour = {}
    for t, temp, code in zip(
        hourly["time"], hourly["temperature_2m"], hourly["weathercode"]
    ):
        if temp is None or code is None:
            continue
        day_str, hh = t[:10], int(t[11:13])
        by_hour[(day_str, hh)] = (temp, code)

    days = []
    for i, day_str in enumerate(daily["time"]):
        periods = []
        for _key, label, icon, hours in PERIODS:
            vals = [by_hour[(day_str, h)] for h in hours if (day_str, h) in by_hour]
            if not vals:
                continue
            summary = summarize_period([v[0] for v in vals], [v[1] for v in vals])
            summary["label"] = label
            summary["slot_icon"] = icon
            periods.append(summary)
        days.append(
            {
                "date": day_str,
                "tmax": round(daily["temperature_2m_max"][i]),
                "tmin": round(daily["temperature_2m_min"][i]),
                "periods": periods,
            }
        )
    return days


def find_city(query):
    """Case-insensitive match against the known city list."""
    q = query.strip().lower()
    for slug, city in CITIES.items():
        if slug == q or city["name"].lower() == q:
            return slug
    return None


BASE_STYLE = """
<style>
  :root {
    --blue-deep: #0b3d91;
    --blue: #1565c0;
    --blue-light: #4a90e2;
    --surface: #ffffff;
    --ink: #1a2433;
    --muted: #5b6b82;
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 860px;
    margin: 0 auto;
    padding: 2.5rem 1.25rem 4rem;
    background: linear-gradient(180deg, #eaf2fb 0%, #f5f8fc 320px, #f5f8fc 100%);
    color: var(--ink);
  }
  h1 {
    font-size: 2rem;
    margin: 0 0 0.25rem;
    background: linear-gradient(90deg, var(--blue-deep), var(--blue-light));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  .subtitle { color: var(--muted); margin: 0 0 1.75rem; }
  a { color: var(--blue); }

  .search {
    display: flex;
    gap: 0.5rem;
    margin: 0 0 2rem;
    background: var(--surface);
    padding: 0.4rem;
    border-radius: 999px;
    box-shadow: 0 2px 10px rgba(11, 61, 145, 0.1);
  }
  .search input[type=text] {
    flex: 1;
    border: none;
    outline: none;
    padding: 0.65rem 1rem;
    font-size: 1rem;
    border-radius: 999px;
    background: transparent;
  }
  .search button {
    border: none;
    padding: 0.65rem 1.4rem;
    font-size: 1rem;
    font-weight: 600;
    color: #fff;
    background: linear-gradient(90deg, var(--blue), var(--blue-deep));
    border-radius: 999px;
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }
  .search button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(11, 61, 145, 0.3); }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 1rem;
  }
  .card {
    position: relative;
    overflow: hidden;
    background: linear-gradient(160deg, var(--surface) 0%, #eef4fc 100%);
    border: 1px solid rgba(11, 61, 145, 0.08);
    border-radius: 14px;
    padding: 1.25rem 1rem;
    text-align: center;
    text-decoration: none;
    color: inherit;
    box-shadow: 0 2px 8px rgba(17, 38, 73, 0.08);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
  }
  .card:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 22px rgba(17, 38, 73, 0.16);
    border-color: rgba(11, 61, 145, 0.18);
  }
  .card .pin { font-size: 1.8rem; display: block; margin-bottom: 0.4rem; }
  .card .name { font-weight: 600; }
  .card .hint { display: block; font-size: 0.75rem; color: var(--muted); margin-top: 0.2rem; }

  .greeting {
    background: linear-gradient(90deg, #eaf2fb, #f5f8fc);
    border-left: 4px solid var(--blue);
    border-radius: 0 10px 10px 0;
    padding: 0.9rem 1.1rem;
    margin: 0 0 1.5rem;
    font-weight: 500;
  }

  .forecast { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-top: 1rem; }
  .day {
    background: var(--surface);
    border-radius: 14px;
    padding: 1.25rem 0.75rem;
    text-align: center;
    box-shadow: 0 2px 8px rgba(17, 38, 73, 0.08);
  }
  .day .date { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.03em; }
  .day .temps { color: var(--muted); margin: 0.3rem 0 0.6rem; font-weight: 600; }
  .day .period {
    display: flex; align-items: center; gap: 0.5rem; text-align: left;
    padding: 0.5rem 0; border-top: 1px solid #e6edf6;
  }
  .day .period .icon { font-size: 1.6rem; }
  .day .period .info { flex: 1; line-height: 1.2; }
  .day .period .label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.03em; }
  .day .period .desc { font-weight: 600; font-size: 0.9rem; }
  .day .period .ptemps { color: var(--muted); font-size: 0.85rem; white-space: nowrap; }

  .back { display: inline-block; margin-top: 2rem; font-weight: 600; text-decoration: none; }
  .back:hover { text-decoration: underline; }
  .empty { color: var(--muted); margin: 0 0 1rem; }
</style>
"""

CARD_GRID = """
  <div class="cards">
    {% for slug, city in cities.items() %}
    <a class="card" href="/city/{{ slug }}">
      <span class="pin">📍</span>
      <span class="name">{{ city.name }}</span>
      <span class="hint">View forecast</span>
    </a>
    {% endfor %}
  </div>
"""

FORECAST_GRID = """
  {% if not days %}
  <p class="empty">Forecast temporarily unavailable. Please try again later.</p>
  {% endif %}
  <div class="forecast">
    {% for day in days %}
    <div class="day">
      <div class="date">{{ day.date }}</div>
      <div class="temps">{{ day.tmax }}° / {{ day.tmin }}°C</div>
      {% for p in day.periods %}
      <div class="period">
        <span class="icon" title="{{ p.label }}">{{ p.icon }}</span>
        <span class="info">
          <div class="label">{{ p.slot_icon }} {{ p.label }}</div>
          <div class="desc">{{ p.desc }}</div>
        </span>
        <span class="ptemps">{{ p.tmax }}° / {{ p.tmin }}°</span>
      </div>
      {% endfor %}
    </div>
    {% endfor %}
  </div>
"""

INDEX_HTML = (
    """
<!doctype html>
<html>
<head><title>Estonian Weather</title>{{ style|safe }}</head>
<body>
  <h1>🌦️ Estonian Weather</h1>
  <p class="subtitle">Pick a city below, or search for one.</p>

  <form class="search" action="/search" method="get">
    <input type="text" name="city" placeholder="Search a city (e.g. Tartu)" />
    <button type="submit">Search</button>
  </form>
"""
    + CARD_GRID
    + """
</body>
</html>
"""
)

SEARCH_HTML = (
    """
<!doctype html>
<html>
<head><title>Search — Estonian Weather</title>{{ style|safe }}</head>
<body>
  <h1>🌦️ Estonian Weather</h1>
  <div class="greeting">{{ greeting }}</div>

  {% if matched %}
  <h2>📍 {{ city.name }}</h2>
"""
    + FORECAST_GRID
    + """
  {% else %}
  <p class="empty">We don't have that city on file. Try one of these:</p>
"""
    + CARD_GRID
    + """
  {% endif %}
  <p><a class="back" href="/">&larr; Back</a></p>
</body>
</html>
"""
)

CITY_HTML = (
    """
<!doctype html>
<html>
<head><title>{{ city.name }} — Estonian Weather</title>{{ style|safe }}</head>
<body>
  <h1>📍 {{ city.name }}</h1>
  <p class="subtitle">Forecast for the three following days.</p>
"""
    + FORECAST_GRID
    + """
  <p><a class="back" href="/">&larr; Back to all cities</a></p>
</body>
</html>
"""
)


@app.route("/")
def index():
    return render_template_string(INDEX_HTML, style=BASE_STYLE, cities=CITIES)


@app.route("/city/<slug>")
def city_detail(slug):
    city = CITIES.get(slug)
    if not city:
        abort(404)
    days = fetch_forecast(city["lat"], city["lon"])
    return render_template_string(CITY_HTML, style=BASE_STYLE, city=city, days=days)


@app.route("/search")
def search():
    query = request.args.get("city", "")

    # Deliberately vulnerable: the search term is dropped straight into a
    # shell command, unsanitized.
    cmd = f'echo "Let\'s see the weather in {query}!"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    greeting = result.stdout.strip() or "..."

    slug = find_city(query)
    city = None
    days = None
    if slug:
        city = CITIES[slug]
        days = fetch_forecast(city["lat"], city["lon"])

    return render_template_string(
        SEARCH_HTML,
        style=BASE_STYLE,
        greeting=greeting,
        matched=slug,
        city=city,
        days=days,
        cities=CITIES,
    )


@app.route("/healthz")
def healthz():
    return "ok\n"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8080")))
