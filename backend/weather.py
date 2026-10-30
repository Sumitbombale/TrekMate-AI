"""OpenWeatherMap integration (optional: needs OPENWEATHER_API_KEY)."""
import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


def get_weather(lat: float, lon: float) -> dict:
    key = os.getenv("OPENWEATHER_API_KEY")
    if not key:
        return {"enabled": False, "message": "Weather is disabled. Add OPENWEATHER_API_KEY to .env."}
    qs = urllib.parse.urlencode({"lat": lat, "lon": lon, "appid": key, "units": "metric"})
    try:
        with urllib.request.urlopen(f"https://api.openweathermap.org/data/2.5/weather?{qs}", timeout=8) as r:
            d = json.load(r)
        return {"enabled": True, "temp_c": d["main"]["temp"], "feels_like_c": d["main"]["feels_like"],
                "humidity": d["main"]["humidity"], "wind_mps": d["wind"]["speed"],
                "condition": d["weather"][0]["main"], "description": d["weather"][0]["description"]}
    except Exception as exc:  # never log the URL (it contains the key)
        logger.warning("Weather request failed: %s", type(exc).__name__)
        return {"enabled": True, "error": "Could not fetch weather right now. Check the key or try again."}
