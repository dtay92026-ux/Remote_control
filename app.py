from datetime import datetime, timezone
from flask import Flask, jsonify, request
import os

app = Flask(__name__)

# Bridge Configuration state (risk and TP settings removed)
bridge_state = {
    "symbol": "XAUUSD",
    "strategy": "PURE_EXECUTION",
    "timeframe": "M15",
    "lotSize": 0.01,
    "maxTrades": 2,
    "command": "PAUSE",
}

ea_heartbeat = {
    "pair": "DTAY89",
    "symbol": "XAUUSD",
    "strategy": "PURE_EXECUTION",
    "enabled": False,
    "lastExecuted": "None",
    "lastSeen": "Never",
}

SUPPORTED_STRATEGIES = [
    "PURE_EXECUTION",
    "TREND_BREAKOUT",
    "RANGE_REVERSAL",
    "SUPPORT_RESISTANCE",
    "EMA_CROSSOVER",
    "RSI_EXTREME",
    "MACD_MOMENTUM",
    "ATR_BREAKOUT",
    "BOLLINGER_BOUNCE",
    "STOCHASTIC_EXTREME",
    "PARABOLIC_SAR",
    "CCI_EXTREME",
    "WILLIAMS_R",
    "MOMENTUM_OSCILLATOR",
    "SUPER_TREND",
    "VWAP_BOUNCE",
    "ICHIMOKU_BREAKOUT",
]


@app.route("/api/bridge/command", methods=["GET"])
def get_command():
  return jsonify(bridge_state)


@app.route("/api/bridge/command", methods=["POST"])
def post_command():
  global bridge_state
  data = request.get_json()
  if data:
    for key in bridge_state:
      if key in data:
        bridge_state[key] = data[key]
  return jsonify({"status": "success", "state": bridge_state})


@app.route("/api/bridge/heartbeat", methods=["POST"])
def post_heartbeat():
  global ea_heartbeat
  data = request.get_json()
  if data:
    ea_heartbeat.update(data)
    ea_heartbeat["lastSeen"] = datetime.now(timezone.utc).strftime(
        "%H:%M:%S UTC"
    )
  return jsonify({"status": "success"})


@app.route("/api/status", methods=["GET"])
def get_status():
  return jsonify({
      "bridge": bridge_state,
      "heartbeat": ea_heartbeat,
      "supported_strategies": SUPPORTED_STRATEGIES,
  })


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
