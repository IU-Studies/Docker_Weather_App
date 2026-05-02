from flask import Flask, render_template, request, jsonify
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from prometheus_flask_exporter import PrometheusMetrics

# Load environment variables
load_dotenv()

# Create Flask app FIRST
app = Flask(__name__)

# Attach Prometheus metrics AFTER app creation
metrics = PrometheusMetrics(app)

# Environment variables
GEO_API_URL = os.getenv("GEO_API_URL")
WEATHER_API_URL = os.getenv("WEATHER_API_URL")
API_KEY = os.getenv("WEATHER_API_KEY", "default_key")

# Data file
DATA_FILE = 'data/weather_history.json'


def load_data():
    # Load stored weather history
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_data(record):
    # Save latest weather record
    data = load_data()
    data.insert(0, record)
    with open(DATA_FILE, 'w') as f:
        json.dump(data[:50], f)


def clear_data():
    # Clear stored history
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)


def get_weather_by_city(city, target_date=None):
    # Fetch coordinates using city name
    geo_url = f"{GEO_API_URL}?name={city}&count=1"
    geo_res = requests.get(geo_url).json()

    if "results" not in geo_res or len(geo_res["results"]) == 0:
        return None

    result = geo_res["results"][0]

    return fetch_weather_by_coords(
        result["latitude"],
        result["longitude"],
        result["name"],
        result.get("country", "Unknown"),
        target_date
    )


def fetch_weather_by_coords(lat, lon, city_name="Local", country="Unknown", target_date=None):
    # Fetch weather using coordinates
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    is_historical = target_date != datetime.now().strftime("%Y-%m-%d")

    weather_url = (
        f"{WEATHER_API_URL}?"
        f"latitude={lat}&longitude={lon}&start_date={target_date}&end_date={target_date}&"
        f"apikey={API_KEY}&"
        f"current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,"
        f"wind_speed_10m,wind_direction_10m,surface_pressure,cloud_cover,visibility,dew_point_2m,weather_code&"
        f"hourly=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,"
        f"wind_speed_10m,wind_direction_10m,surface_pressure,cloud_cover,visibility,dew_point_2m,weather_code,is_day&"
        f"daily=sunrise,sunset,uv_index_max,precipitation_probability_max&timezone=auto"
    )

    res = requests.get(weather_url).json()

    if "error" in res or "hourly" not in res:
        archive_url = (
            f"https://archive-api.open-meteo.com/v1/archive?"
            f"latitude={lat}&longitude={lon}&start_date={target_date}&end_date={target_date}&"
            f"hourly=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,"
            f"wind_speed_10m,wind_direction_10m,surface_pressure,cloud_cover,dew_point_2m,weather_code&"
            f"daily=sunrise,sunset,uv_index_max,precipitation_probability_max&timezone=auto"
        )
        res = requests.get(archive_url).json()

    if "hourly" not in res:
        return None

    h = res["hourly"]
    daily = res.get("daily", {})

    hourly_data = []

    for i in range(24):
        code = h.get("weather_code", [0] * 24)[i]

        icon = (
            "Clear" if code <= 1 else
            "Cloudy" if code <= 3 else
            "Rain" if code <= 65 else
            "Storm"
        )

        hour_time = h.get("time", [""] * 24)[i]

        hourly_data.append({
            "hour_index": i,
            "time_str": hour_time.split("T")[1] if hour_time else f"{i:02d}:00",
            "icon": icon,
            "temperature": h.get("temperature_2m", [0] * 24)[i],
            "feels_like": h.get("apparent_temperature", [0] * 24)[i],
            "humidity": h.get("relative_humidity_2m", ["N/A"] * 24)[i],
            "windspeed": h.get("wind_speed_10m", [0] * 24)[i],
            "winddirection": h.get("wind_direction_10m", [0] * 24)[i],
            "precipitation": h.get("precipitation", [0] * 24)[i],
            "is_day": "Day" if h.get("is_day", [1] * 24)[i] else "Night",
            "pressure": h.get("surface_pressure", ["N/A"] * 24)[i],
            "cloud_cover": h.get("cloud_cover", ["N/A"] * 24)[i],
            "visibility": round(h.get("visibility", [0] * 24)[i] / 1000, 1)
            if h.get("visibility") and h.get("visibility")[i] is not None else "N/A",
            "dew_point": h.get("dew_point_2m", ["N/A"] * 24)[i]
        })

    if not is_historical and "current" in res:
        cur = res["current"]

        base_data = {
            "icon": "Clear" if cur.get("weather_code", 0) <= 1 else "Cloudy",
            "temperature": cur.get("temperature_2m"),
            "feels_like": cur.get("apparent_temperature"),
            "humidity": cur.get("relative_humidity_2m"),
            "windspeed": cur.get("wind_speed_10m"),
            "winddirection": cur.get("wind_direction_10m"),
            "precipitation": cur.get("precipitation"),
            "is_day": "Day" if cur.get("is_day") else "Night",
            "pressure": cur.get("surface_pressure"),
            "cloud_cover": cur.get("cloud_cover"),
            "visibility": cur.get("visibility", 0) / 1000 if cur.get("visibility") else "N/A",
            "dew_point": cur.get("dew_point_2m"),
            "time": cur.get("time")
        }
    else:
        base_data = hourly_data[12].copy()
        base_data["time"] = f"{target_date}T12:00"

    return {
        "city": city_name,
        "country": country,
        "lat": lat,
        "lon": lon,
        "target_date": target_date,
        "base": base_data,
        "hourly_data": hourly_data,
        "uv_index": daily.get("uv_index_max", ["N/A"])[0],
        "rain_prob": daily.get("precipitation_probability_max", ["N/A"])[0],
        "sunrise": daily.get("sunrise", ["N/A"])[0][-5:] if daily.get("sunrise", [None])[0] else "N/A",
        "sunset": daily.get("sunset", ["N/A"])[0][-5:] if daily.get("sunset", [None])[0] else "N/A",
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/weather', methods=['POST'])
def weather():
    # Handle weather API request
    req_data = request.json

    if 'lat' in req_data:
        data = fetch_weather_by_coords(
            req_data['lat'],
            req_data['lon'],
            "Current Location",
            "Local",
            req_data.get('date')
        )
    else:
        data = get_weather_by_city(
            req_data.get('city'),
            req_data.get('date')
        )

    if data:
        save_data({
            "city": data["city"],
            "temperature": data["base"]["temperature"],
            "windspeed": data["base"]["windspeed"],
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return jsonify({"success": True, "data": data})

    return jsonify({"success": False, "message": "Data not found"}), 404


@app.route('/api/history', methods=['GET'])
def history():
    # Return stored history
    return jsonify({"success": True, "data": load_data()})


@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    # Clear history endpoint
    clear_data()
    return jsonify({"success": True})


if __name__ == '__main__':
    print("GEO_API_URL:", GEO_API_URL)
    print("WEATHER_API_URL:", WEATHER_API_URL)
    app.run(host='0.0.0.0', port=5000)