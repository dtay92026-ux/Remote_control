from datetime import datetime
import json
import os
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

STATE_FILE = "bridge_state.json"

# 18 Advanced Strategies with Optimal Timeframes
STRATEGIES = {
    "PURE_EXECUTION": {"name": "Pure Execution (Manual/Custom)", "timeframe": "M15"},
    "THREE_STEP_SCALPER": {"name": "3-Step Amapiano Scalper", "timeframe": "M1"},
    "SGIJA_BOUNCE": {"name": "Sgija Momentum Scalper", "timeframe": "M1"},
    "PRIVATE_SCHOOL_TREND": {"name": "Private School Trend Following", "timeframe": "H1"},
    "SUPPORT_RESISTANCE": {"name": "Support & Resistance Rejection", "timeframe": "M15"},
    "MA_CROSSOVER": {"name": "Moving Average Crossover (Fast)", "timeframe": "M30"},
    "BOLLINGER_SQUEEZE": {"name": "Bollinger Band Squeeze Breakout", "timeframe": "M5"},
    "RSI_REVERSAL": {"name": "RSI Overbought/Oversold Reversal", "timeframe": "M15"},
    "MACD_MOMENTUM": {"name": "MACD Histogram Momentum", "timeframe": "M15"},
    "EMA_RIBBON_SCALP": {"name": "EMA Ribbon Scalper", "timeframe": "M1"},
    "LONDON_BREAKOUT": {"name": "London Open Session Breakout", "timeframe": "M5"},
    "NEW_YORK_MOMENTUM": {"name": "New York Session Momentum", "timeframe": "M15"},
    "ASIAN_RANGE": {"name": "Asian Range Box Breakout", "timeframe": "M15"},
    "FIBONACCI_PULLBACK": {"name": "Fibonacci 61.8% Retracement", "timeframe": "H1"},
    "VWAP_BOUNCE": {"name": "VWAP Institutional Bounce", "timeframe": "M5"},
    "SUPERTREND_FOLLOW": {"name": "Supertrend Directional Follow", "timeframe": "H1"},
    "STOCHASTIC_SCALP": {"name": "Stochastic Fast Scalper", "timeframe": "M1"},
    "PINBAR_REVERSAL": {"name": "Price Action Pinbar Reversal", "timeframe": "M30"},
}

default_state = {
    "command": "PAUSE",
    "symbol": "XAUUSD",
    "timeframe": "M15",
    "strategy": "PURE_EXECUTION",
    "lotSize": 0.01,
    "stopLoss": 100.0,
    "maxTrades": 1,
    "account": "DEMO",
    "updatedAt": 0,
}


def load_state():
  if os.path.exists(STATE_FILE):
    try:
      with open(STATE_FILE, "r") as f:
        return json.load(f)
    except:
      pass
  return default_state.copy()


def save_state(state):
  with open(STATE_FILE, "w") as f:
    json.dump(state, f)


if not os.path.exists(STATE_FILE):
  save_state(default_state)

ea_heartbeat = {
    "pair": "DTAY89",
    "symbol": "XAUUSD",
    "timeframe": "M15",
    "strategy": "PURE_EXECUTION",
    "account": "DEMO",
    "enabled": False,
    "lastCommand": "",
    "lastExecuted": "None",
    "lastSeen": "Never",
    "lastSeenEpoch": 0,
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>D'TAY89 | Advanced Strategy Control Panel</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans p-4">
    <div class="max-w-md mx-auto space-y-6">
        
        <!-- Header -->
        <div class="flex justify-between items-center border-b border-slate-800 pb-4">
            <div>
                <h1 class="text-xl font-bold text-emerald-400 tracking-wider">D'TAY89 EXECUTOR</h1>
                <p class="text-xs text-slate-400">18-Strategy Automated Bridge</p>
            </div>
            <div id="status-badge" class="px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">
                OFFLINE
            </div>
        </div>

        <!-- Master Automation Control (Play / Pause) -->
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg space-y-3">
            <h2 class="text-sm font-semibold text-slate-300 uppercase tracking-wide">Master Automation</h2>
            <div class="grid grid-cols-2 gap-3">
                <button onclick="sendCommand('PLAY')" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 px-4 rounded-lg transition shadow-md active:scale-95 flex items-center justify-center space-x-2">
                    <span>▶ PLAY</span>
                </button>
                <button onclick="sendCommand('PAUSE')" class="bg-amber-600 hover:bg-amber-500 text-white font-bold py-3 px-4 rounded-lg transition shadow-md active:scale-95 flex items-center justify-center space-x-2">
                    <span>⏸ PAUSE</span>
                </button>
            </div>
        </div>

        <!-- Strategy & Parameters Form -->
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg space-y-4">
            <h2 class="text-sm font-semibold text-slate-300 uppercase tracking-wide">Strategy & Timeframe</h2>
            
            <div class="space-y-3">
                <div>
                    <label class="block text-xs text-slate-400 mb-1">Select Strategy (Auto-Timeframe Enabled)</label>
                    <select id="strategy" onchange="updateRecommendedTimeframe()" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500">
                        {% for key, val in strategies.items() %}
                        <option value="{{ key }}" {% if state.strategy == key %}selected{% endif %}>{{ val.name }} ({{ val.timeframe }})</option>
                        {% endfor %}
                    </select>
                </div>

                <div class="grid grid-cols-3 gap-2">
                    <div>
                        <label class="block text-xs text-slate-400 mb-1">Symbol</label>
                        <input type="text" id="symbol" value="{{ state.symbol }}" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 uppercase">
                    </div>
                    <div>
                        <label class="block text-xs text-slate-400 mb-1">Timeframe</label>
                        <select id="timeframe" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500">
                            <option value="M1" {% if state.timeframe == 'M1' %}selected{% endif %}>M1</option>
                            <option value="M5" {% if state.timeframe == 'M5' %}selected{% endif %}>M5</option>
                            <option value="M15" {% if state.timeframe == 'M15' %}selected{% endif %}>M15</option>
                            <option value="M30" {% if state.timeframe == 'M30' %}selected{% endif %}>M30</option>
                            <option value="H1" {% if state.timeframe == 'H1' %}selected{% endif %}>H1</option>
                            <option value="H4" {% if state.timeframe == 'H4' %}selected{% endif %}>H4</option>
                            <option value="D1" {% if state.timeframe == 'D1' %}selected{% endif %}>D1</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs text-slate-400 mb-1">Account</label>
                        <select id="account" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500">
                            <option value="DEMO" {% if state.account == 'DEMO' %}selected{% endif %}>DEMO</option>
                            <option value="LIVE" {% if state.account == 'LIVE' %}selected{% endif %}>LIVE</option>
                        </select>
                    </div>
                </div>

                <div class="grid grid-cols-3 gap-2">
                    <div>
                        <label class="block text-xs text-slate-400 mb-1">Lot Size</label>
                        <input type="number" step="0.01" id="lotSize" value="{{ state.lotSize }}" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500">
                    </div>
                    <div>
                        <label class="block text-xs text-slate-400 mb-1">Max Trades</label>
                        <input type="number" id="maxTrades" value="{{ state.maxTrades }}" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500">
                    </div>
                    <div>
                        <label class="block text-xs text-slate-400 mb-1">Stop Loss (Pts)</label>
                        <input type="number" id="stopLoss" value="{{ state.stopLoss }}" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500">
                    </div>
                </div>

                <button onclick="saveConfig()" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2.5 rounded-lg transition text-sm">
                    Update Strategy & Config
                </button>
            </div>
        </div>

        <!-- EA Live Status Telemetry -->
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg space-y-2 text-xs">
            <h2 class="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-2">EA Telemetry</h2>
            <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400">Last Seen:</span>
                <span id="ea-last-seen" class="text-slate-200 font-mono">{{ ea.lastSeen }}</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400">Active Strategy:</span>
                <span id="ea-strategy" class="text-emerald-400 font-mono">{{ ea.strategy }}</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400">Last Executed:</span>
                <span id="ea-last-executed" class="text-slate-200 font-mono">{{ ea.lastExecuted }}</span>
            </div>
        </div>

    </div>

    <script>
        const strategyTimeframes = {
            {% for key, val in strategies.items() %}
            "{{ key }}": "{{ val.timeframe }}",
            {% endfor %}
        };

        function updateRecommendedTimeframe() {
            const strat = document.getElementById('strategy').value;
            if (strategyTimeframes[strat]) {
                document.getElementById('timeframe').value = strategyTimeframes[strat];
            }
        }

        setInterval(() => {
            fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                const badge = document.getElementById('status-badge');
                if (data.online) {
                    badge.className = "px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
                    badge.innerText = "ONLINE";
                } else {
                    badge.className = "px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30";
                    badge.innerText = "OFFLINE";
                }
                document.getElementById('ea-last-seen').innerText = data.ea.lastSeen;
                document.getElementById('ea-strategy').innerText = data.ea.strategy || 'PURE_EXECUTION';
                document.getElementById('ea-last-executed').innerText = data.ea.lastExecuted || 'None';
            }).catch(err => console.error("Telemetry sync error:", err));
        }, 2000);

        function sendCommand(cmd) {
            const data = {
                command: cmd,
                strategy: document.getElementById('strategy').value,
                symbol: document.getElementById('symbol').value.toUpperCase(),
                timeframe: document.getElementById('timeframe').value,
                lotSize: parseFloat(document.getElementById('lotSize').value),
                maxTrades: parseInt(document.getElementById('maxTrades').value),
                stopLoss: parseFloat(document.getElementById('stopLoss').value),
                account: document.getElementById('account').value
            };

            fetch('/api/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(res => res.json())
            .then(response => {
                console.log("Command sent: " + cmd);
            });
        }

        function saveConfig() {
            sendCommand('CONFIG');
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
  state = load_state()
  return render_template_string(
      HTML_TEMPLATE, state=state, ea=ea_heartbeat, strategies=STRATEGIES
  )


@app.route("/api/bridge/command", methods=["GET"])
def get_command():
  return jsonify(load_state())


@app.route("/api/status", methods=["GET"])
def get_status():
  state = load_state()
  current_time = int(datetime.utcnow().timestamp())
  is_online = (current_time - ea_heartbeat.get("lastSeenEpoch", 0)) < 15
  return jsonify({"state": state, "ea": ea_heartbeat, "online": is_online})


@app.route("/api/bridge/heartbeat", methods=["POST"])
def post_heartbeat():
  global ea_heartbeat
  data = request.get_json()
  if data:
    ea_heartbeat.update(data)
    ea_heartbeat["lastSeen"] = datetime.utcnow().strftime("%H:%M:%S UTC")
    ea_heartbeat["lastSeenEpoch"] = int(datetime.utcnow().timestamp())
  return jsonify({"status": "success"})


@app.route("/api/control", methods=["POST"])
def update_control():
  state = load_state()
  data = request.get_json()
  if not data:
    return jsonify({"error": "No data provided"}), 400

  for key in [
      "command",
      "symbol",
      "timeframe",
      "strategy",
      "lotSize",
      "stopLoss",
      "maxTrades",
      "account",
  ]:
    if key in data:
      state[key] = data[key]

  state["updatedAt"] = int(datetime.utcnow().timestamp())
  save_state(state)
  return jsonify(state)


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)
