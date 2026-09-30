from datetime import datetime
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Global state that the EA polls and the web app controls
bridge_state = {
    "command": "STOP",  # START, STOP, BUY, SELL, CONFIG
    "symbol": "XAUUSD",
    "strategy": "PURE_EXECUTION",
    "lotSize": 0.01,
    "stopLoss": 100.0,
    "maxTrades": 1,
    "account": "DEMO",
    "updatedAt": int(datetime.utcnow().timestamp()),
}

# Live status reported back from the MT5 EA heartbeat
ea_heartbeat = {
    "pair": "DTAY89",
    "symbol": "XAUUSD",
    "timeframe": "M15",
    "strategy": "PURE_EXECUTION",
    "account": "DEMO",
    "enabled": False,
    "lastCommand": "",
    "lastExecuted": "",
    "lastSeen": "Never",
}


@app.route("/")
def index():
  return render_template("index.html", state=bridge_state, ea=ea_heartbeat)


@app.route("/api/bridge/command", methods=["GET"])
def get_command():
  # EA polls this endpoint to check what it should do
  return jsonify(bridge_state)


@app.route("/api/bridge/heartbeat", methods=["POST"])
def post_heartbeat():
  global ea_heartbeat
  data = request.get_json()
  if data:
    ea_heartbeat.update(data)
    ea_heartbeat["lastSeen"] = datetime.utcnow().strftime("%H:%M:%S UTC")
  return jsonify({"status": "success"})


@app.route("/api/control", methods=["POST"])
def update_control():
  global bridge_state
  data = request.get_json()
  if not data:
    return jsonify({"error": "No data provided"}), 400

  # Update state parameters sent from the web dashboard
  for key in [
      "command",
      "symbol",
      "strategy",
      "lotSize",
      "stopLoss",
      "maxTrades",
      "account",
  ]:
    if key in data:
      bridge_state[key] = data[key]

  # Update timestamp so the EA knows a new command/config change occurred
  bridge_state["updatedAt"] = int(datetime.utcnow().timestamp())
  return jsonify(bridge_state)


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)
