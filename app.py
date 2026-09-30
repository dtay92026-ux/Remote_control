from datetime import datetime
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Global configuration state controlled by your web app and read by the MT5 EA
current_settings = {
    "symbol": "XAUUSDm",
    "strategy": "PURE_EXECUTION",
    "timeframe": "M15",
    "lotSize": 0.01,
    "maxTrades": 2,
    "riskUSD": 50.0,  # Exact dollar risk per trade
    "tpUSD": 100.0,  # Exact dollar take profit per trade
    "tpEnabled": True,
    "command": "PAUSE",  # PLAY, PAUSE, MANUAL_BUY, MANUAL_SELL
}

# Live status received from the EA via heartbeats
ea_status = {
    "connected": False,
    "last_seen": None,
    "symbol": "",
    "strategy": "",
    "enabled": False,
    "riskUSD": 50.0,
    "lastExecuted": "None",
}


@app.route("/")
def index():
  # Serves your dashboard template if available, otherwise returns JSON status
  try:
    return render_template("index.html")
  except Exception:
    return jsonify({
        "status": "D'TAY89 Remote Control API is running",
        "settings": current_settings,
        "ea_status": ea_status,
    })


# ==========================================
# BRIDGE ENDPOINTS (Called by MT5 EA)
# ==========================================


@app.route("/api/bridge/command", methods=["GET"])
def bridge_command():
  pair_header = request.headers.get("X-DTAY89-PAIR", "Unknown")
  # Return current settings/commands to the EA polling this endpoint
  return jsonify(current_settings)


@app.route("/api/bridge/heartbeat", methods=["POST"])
def bridge_heartbeat():
  global ea_status
  data = request.json
  if data:
    ea_status["connected"] = True
    ea_status["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ea_status["symbol"] = data.get("symbol", "")
    ea_status["strategy"] = data.get("strategy", "")
    ea_status["enabled"] = data.get("enabled", False)
    ea_status["riskUSD"] = data.get("riskUSD", 50.0)
    ea_status["lastExecuted"] = data.get("lastExecuted", "None")

  return jsonify({"status": "acknowledged"})


# ==========================================
# DASHBOARD ENDPOINTS (Called by your UI)
# ==========================================


@app.route("/api/dashboard/status", methods=["GET"])
def dashboard_status():
  return jsonify({"settings": current_settings, "ea_status": ea_status})


@app.route("/api/dashboard/update", methods=["POST"])
def dashboard_update():
  global current_settings
  data = request.json
  if not data:
    return jsonify({"status": "error", "message": "No data received"}), 400

  # Update settings based on web dashboard inputs
  if "lotSize" in data:
    current_settings["lotSize"] = float(data["lotSize"])
  if "riskUSD" in data:
    current_settings["riskUSD"] = float(data["riskUSD"])
  if "tpUSD" in data:
    current_settings["tpUSD"] = float(data["tpUSD"])
  if "symbol" in data:
    current_settings["symbol"] = data["symbol"]
  if "strategy" in data:
    current_settings["strategy"] = data["strategy"]
  if "timeframe" in data:
    current_settings["timeframe"] = data["timeframe"]
  if "maxTrades" in data:
    current_settings["maxTrades"] = int(data["maxTrades"])
  if "tpEnabled" in data:
    current_settings["tpEnabled"] = bool(data["tpEnabled"])
  if "command" in data:
    current_settings["command"] = data["command"]

  return jsonify({"status": "success", "settings": current_settings})


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000, debug=True)
