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

# Attach metrics AFTER app creation
metrics = PrometheusMetrics(app)

# Environment variables
GEO_API_URL = os.getenv("GEO_API_URL")
WEATHER_API_URL = os.getenv("WEATHER_API_URL")
API_KEY = os.getenv("WEATHER_API_KEY", "default_key")

# Data file
DATA_FILE = 'data/weather_history.json'


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return []
    return []


def save_data(record):
    data = load_data()
    data.insert(0, record)
    with open(DATA_FILE, 'w') as f:
        json.dump(data[:50], f)


def clear_data():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/weather', methods=['POST'])
def weather():
    req_data = request.json

    if 'lat' in req_data:
        data = {"message": "Coordinates request working"}
    else:
        data = {"message": "City request working"}

    return jsonify({"success": True, "data": data})


@app.route('/api/history', methods=['GET'])
def history():
    return jsonify({"success": True, "data": load_data()})


@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    clear_data()
    return jsonify({"success": True})


if __name__ == '__main__':
    print("Starting Flask App...")
    app.run(host='0.0.0.0', port=5000)