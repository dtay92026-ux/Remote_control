from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# In-memory store for EA state
ea_state = {
    "DTAY89": {
        "command": "PAUSE",
        "strategy": "PURE_EXECUTION",
        "timeframe": "M15",  # Default timeframe matching EA
        "lotSize": 0.01,
        "maxTrades": 2,
        "tpEnabled": True,
        "tp1": 1.0,
        "enabled": False,
        "lastExecuted": "None",
    }
}


@app.route("/")
def index():
  return render_template("index.html", state=ea_state["DTAY89"])


@app.route("/api/bridge/command", methods=["GET"])
def get_command():
  pair = request.headers.get("X-DTAY89-PAIR", "DTAY89")
  state = ea_state.get(pair, ea_state["DTAY89"])

  # Send command payload including timeframe to the EA
  payload = {
      "command": state["command"],
      "strategy": state["strategy"],
      "timeframe": state["timeframe"],
      "lotSize": state["lotSize"],
      "maxTrades": state["maxTrades"],
      "tpEnabled": state["tpEnabled"],
      "tp1": state["tp1"],
  }

  # Reset one-shot manual triggers after they are fetched
  if state["command"] in ["MANUAL_BUY", "MANUAL_SELL"]:
    state["command"] = "PLAY" if state["enabled"] else "PAUSE"

  return jsonify(payload)


@app.route("/api/bridge/heartbeat", methods=["POST"])
def heartbeat():
  data = request.json or {}
  pair = data.get("pair", "DTAY89")
  if pair in ea_state:
    ea_state[pair]["enabled"] = data.get("enabled", False)
    ea_state[pair]["lastExecuted"] = data.get("lastExecuted", "None")
  return jsonify({"status": "success"})


@app.route("/api/control", methods=["POST"])
def control():
  data = request.json or {}
  pair = data.get("pair", "DTAY89")
  if pair in ea_state:
    if "command" in data:
      ea_state[pair]["command"] = data["command"]
      if data["command"] == "PLAY":
        ea_state[pair]["enabled"] = True
      elif data["command"] == "PAUSE":
        ea_state[pair]["enabled"] = False
    if "strategy" in data:
      ea_state[pair]["strategy"] = data["strategy"]
    if "timeframe" in data:
      ea_state[pair]["timeframe"] = data["timeframe"]
    if "lotSize" in data:
      ea_state[pair]["lotSize"] = float(data["lotSize"])
    if "maxTrades" in data:
      ea_state[pair]["maxTrades"] = int(data["maxTrades"])
  return jsonify({"status": "success", "state": ea_state[pair]})


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)
