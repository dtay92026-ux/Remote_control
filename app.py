from flask import Flask, jsonify, request
import os

app = Flask(__name__)

# Global bridge state shared with EA and Dashboard
bridge_state = {
    "enabled": False,
    "strategy": "TREND_BREAKOUT",
    "symbol": "XAUUSDm",
    "timeframe": "M15",
    "command": "NONE",
    "lotSize": 0.01,
    "maxTrades": 2,
}

# List of all 17 supported strategies
SUPPORTED_STRATEGIES = [
    "TREND_BREAKOUT",
    "RANGE_REVERSAL",
    "PURE_EXECUTION",
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
  """Endpoint polled by the MetaTrader 5 Expert Advisor"""
  cmd = bridge_state["command"]
  # Reset command after polling to prevent infinite loops
  bridge_state["command"] = "NONE"

  return jsonify({
      "enabled": bridge_state["enabled"],
      "strategy": bridge_state["strategy"],
      "symbol": bridge_state["symbol"],
      "timeframe": bridge_state["timeframe"],
      "command": cmd,
      "lotSize": bridge_state["lotSize"],
      "maxTrades": bridge_state["maxTrades"],
  })


@app.route("/api/bridge/heartbeat", methods=["POST"])
def receive_heartbeat():
  """Receives status updates from the MT5 EA"""
  data = request.json or {}
  bridge_state["enabled"] = data.get("enabled", bridge_state["enabled"])
  return jsonify({"status": "received"})


@app.route("/api/set_strategy", methods=["POST"])
def set_strategy():
  data = request.json or {}
  strat = data.get("strategy")
  if strat in SUPPORTED_STRATEGIES:
    bridge_state["strategy"] = strat
    return jsonify({"success": True, "strategy": strat})
  return jsonify({"success": False, "error": "Invalid strategy"}), 400


@app.route("/api/control", methods=["POST"])
def control_ea():
  data = request.json or {}
  action = data.get("action")  # PLAY, PAUSE, MANUAL_BUY, MANUAL_SELL
  if action in ["PLAY", "PAUSE", "MANUAL_BUY", "MANUAL_SELL"]:
    bridge_state["command"] = action
    if action == "PLAY":
      bridge_state["enabled"] = True
    elif action == "PAUSE":
      bridge_state["enabled"] = False
    return jsonify({"success": True, "action": action})
  return jsonify({"success": False, "error": "Invalid action"}), 400


@app.route("/", methods=["GET"])
def index():
  return jsonify({
      "app": "D'TAY89 Trading Bridge",
      "active_strategy": bridge_state["strategy"],
      "available_strategies": SUPPORTED_STRATEGIES,
      "state": bridge_state,
  })


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
