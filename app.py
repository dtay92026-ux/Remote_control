from datetime import datetime
import json
import os
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

STATE_FILE = "bridge_state.json"

STRATEGIES = {
    "PURE_EXECUTION": {
        "name": "Pure M15 Rejection/Engulfing Scalper",
        "timeframe": "M15",
    },
    "THREE_STEP_SCALPER": {
        "name": "Micro-Momentum Scalper",
        "timeframe": "M1",
    },
    "SGIJA_BOUNCE": {"name": "Volatility Breakout Scalper", "timeframe": "M1"},
    "PRIVATE_SCHOOL_TREND": {"name": "Macro Trend Follower", "timeframe": "H1"},
    "SUPPORT_RESISTANCE": {
        "name": "Support & Resistance Reversal",
        "timeframe": "M15",
    },
    "MA_CROSSOVER": {"name": "Dual Moving Average Crossover", "timeframe": "M30"},
    "BOLLINGER_SQUEEZE": {
        "name": "Bollinger Band Volatility Squeeze",
        "timeframe": "M5",
    },
    "RSI_REVERSAL": {"name": "RSI Mean Reversion", "timeframe": "M15"},
    "MACD_MOMENTUM": {"name": "MACD Histogram Momentum", "timeframe": "M15"},
    "EMA_RIBBON_SCALP": {"name": "EMA Ribbon Trend Scalp", "timeframe": "M1"},
    "LONDON_BREAKOUT": {"name": "London Open Session Breakout", "timeframe": "M5"},
    "NEW_YORK_MOMENTUM": {
        "name": "New York Session Momentum",
        "timeframe": "M15",
    },
    "ASIAN_RANGE": {"name": "Asian Range Breakout", "timeframe": "M15"},
    "FIBONACCI_PULLBACK": {
        "name": "Fibonacci 61.8% Retracement",
        "timeframe": "H1",
    },
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
    "maxTrades": 2,
    "tpEnabled": True,
    "tp1": 1.0,
    "tp2": 2.0,
    "tp3": 3.0,
    "tp4": 4.0,
    "telegramToken": "",
    "telegramChatId": "",
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
    "strategy": "PURE_EXECUTION",
    "enabled": False,
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
    <title>D'TAY89 | Neural Executor</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-black text-slate-100 min-h-screen font-sans p-4 flex justify-center">
    <div class="w-full max-w-sm space-y-4 pb-10">
        
        <div class="flex justify-between items-center px-2 py-3 border-b border-zinc-900">
            <span class="text-xs text-zinc-500 font-mono">LIVE SYSTEM</span>
            <div id="status-badge" class="px-3 py-1 rounded-full text-xs font-bold bg-rose-500/10 text-rose-500 border border-rose-500/25 tracking-wider">
                OFFLINE
            </div>
        </div>

        <div class="flex flex-col items-center justify-center pt-2 pb-1 space-y-3">
            <div class="relative w-40 h-40 rounded-full bg-zinc-950 border-2 border-emerald-500/60 flex items-center justify-center shadow-[0_0_35px_rgba(16,185,129,0.35)] overflow-hidden">
                <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.1)_0%,transparent_70%)]"></div>
                <span class="text-xl font-black tracking-widest text-emerald-400 font-mono drop-shadow-[0_0_12px_rgba(52,211,153,0.8)]">D'TAY89</span>
            </div>
            <h1 class="text-lg font-black tracking-widest text-emerald-400 uppercase">NEURAL EA</h1>
        </div>

        <div class="grid grid-cols-3 gap-2 bg-zinc-950 border border-zinc-900 rounded-2xl p-3 text-center shadow-lg">
            <div>
                <span class="block text-[10px] text-zinc-500 uppercase">Symbol</span>
                <span id="stat-symbol" class="text-xs font-bold text-zinc-200 font-mono">{{ state.symbol }}</span>
            </div>
            <div class="border-x border-zinc-900">
                <span class="block text-[10px] text-zinc-500 uppercase">Engine</span>
                <span id="engine-status-text" class="text-xs font-bold text-emerald-400 font-mono">{{ state.command }}</span>
            </div>
            <div>
                <span class="block text-[10px] text-zinc-500 uppercase">Max Trades</span>
                <span id="stat-max-trades" class="text-xs font-bold text-zinc-200 font-mono">{{ state.maxTrades }}</span>
            </div>
        </div>

        <div class="bg-zinc-950 border border-zinc-900 rounded-2xl p-4 shadow-lg flex flex-col items-center justify-center space-y-2">
            <button id="engine-toggle-btn" onclick="toggleEngine()" class="w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-[0_0_20px_rgba(16,185,129,0.2)] active:scale-95 border-2 border-zinc-800 bg-zinc-900 text-emerald-400">
                <svg id="icon-play" class="w-8 h-8 fill-current translate-x-0.5 text-emerald-400" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z"/>
                </svg>
                <svg id="icon-pause" class="w-8 h-8 fill-current text-zinc-200" viewBox="0 0 24 24" style="display:none;">
                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                </svg>
            </button>
        </div>

        <div id="manual-execution-panel" class="bg-zinc-950 border border-emerald-500/30 rounded-2xl p-4 shadow-lg space-y-2">
            <div class="text-xs font-semibold text-emerald-400 uppercase tracking-wider text-center mb-2">Pure M15 Rejection / Engulfing Controls</div>
            <div class="grid grid-cols-2 gap-3">
                <button onclick="sendManualAction('MANUAL_BUY')" class="w-full bg-emerald-600 hover:bg-emerald-500 text-black font-extrabold py-3 rounded-xl transition text-xs tracking-wider shadow-[0_0_15px_rgba(16,185,129,0.4)]">
                    FORCE BUY 🟢
                </button>
                <button onclick="sendManualAction('MANUAL_SELL')" class="w-full bg-rose-600 hover:bg-rose-500 text-white font-extrabold py-3 rounded-xl transition text-xs tracking-wider shadow-[0_0_15px_rgba(244,63,94,0.4)]">
                    FORCE SELL 🔴
                </button>
            </div>
        </div>

        <div class="bg-zinc-950 border border-zinc-900 rounded-2xl p-4 shadow-lg space-y-3">
            <div class="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Strategy Matrix & Risk Configuration</div>
            
            <div class="space-y-3">
                <div>
                    <label class="block text-[11px] text-zinc-500 mb-1">Active Neural Strategy</label>
                    <select id="strategy" onchange="handleStrategyChange()" class="w-full bg-black border border-zinc-800 rounded-xl p-3 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono">
                        {% for key, val in strategies.items() %}
                        <option value="{{ key }}" {% if state.strategy == key %}selected{% endif %}>{{ val.name }} ({{ val.timeframe }})</option>
                        {% endfor %}
                    </select>
                </div>

                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-[10px] text-zinc-500 mb-1">Symbol</label>
                        <input type="text" id="symbol" value="{{ state.symbol }}" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono uppercase text-center">
                    </div>
                    <div>
                        <label class="block text-[10px] text-zinc-500 mb-1">Lot Size</label>
                        <input type="number" step="0.01" id="lotSize" value="{{ state.lotSize }}" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-[10px] text-zinc-500 mb-1">Max Trades (Scaling)</label>
                        <input type="number" id="maxTrades" value="{{ state.maxTrades }}" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
                    </div>
                    <div>
                        <label class="block text-[10px] text-zinc-500 mb-1">Take Profit Mode</label>
                        <select id="tpEnabled" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
                            <option value="true" {% if state.tpEnabled %}selected{% endif %}>ENABLED (Multi-TP)</option>
                            <option value="false" {% if not state.tpEnabled %}selected{% endif %}>DISABLED</option>
                        </select>
                    </div>
                </div>

                <div class="grid grid-cols-4 gap-1.5">
                    <div>
                        <label class="block text-[9px] text-zinc-500 mb-1 text-center">TP 1</label>
                        <input type="number" step="0.5" id="tp1" value="{{ state.tp1 }}" class="w-full bg-black border border-zinc-800 rounded-lg p-2 text-xs text-emerald-400 font-mono text-center">
                    </div>
                    <div>
                        <label class="block text-[9px] text-zinc-500 mb-1 text-center">TP 2</label>
                        <input type="number" step="0.5" id="tp2" value="{{ state.tp2 }}" class="w-full bg-black border border-zinc-800 rounded-lg p-2 text-xs text-emerald-400 font-mono text-center">
                    </div>
                    <div>
                        <label class="block text-[9px] text-zinc-500 mb-1 text-center">TP 3</label>
                        <input type="number" step="0.5" id="tp3" value="{{ state.tp3 }}" class="w-full bg-black border border-zinc-800 rounded-lg p-2 text-xs text-emerald-400 font-mono text-center">
                    </div>
                    <div>
                        <label class="block text-[9px] text-zinc-500 mb-1 text-center">TP 4</label>
                        <input type="number" step="0.5" id="tp4" value="{{ state.tp4 }}" class="w-full bg-black border border-zinc-800 rounded-lg p-2 text-xs text-emerald-400 font-mono text-center">
                    </div>
                </div>

                <button onclick="saveConfig()" class="w-full bg-zinc-900 hover:bg-zinc-800 text-emerald-400 font-bold py-3 rounded-xl border border-emerald-500/30 transition text-xs tracking-wider shadow-sm">
                    UPDATE CONFIGURATION
                </button>
            </div>
        </div>

        <div class="bg-zinc-950 border border-zinc-900 rounded-2xl p-4 shadow-lg space-y-2 text-xs">
            <div class="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Telemetry Log</div>
            <div class="flex justify-between py-1 border-b border-zinc-900/50">
                <span class="text-zinc-500">Last Seen:</span>
                <span id="ea-last-seen" class="text-zinc-300 font-mono">{{ ea.lastSeen }}</span>
            </div>
            <div class="flex justify-between py-1 border-b border-zinc-900/50">
                <span class="text-zinc-500">Active Strategy:</span>
                <span id="ea-strategy" class="text-emerald-400 font-mono">{{ ea.strategy }}</span>
            </div>
            <div class="flex justify-between py-1">
                <span class="text-zinc-500">Last Executed:</span>
                <span id="ea-last-executed" class="text-zinc-300 font-mono">{{ ea.lastExecuted }}</span>
            </div>
        </div>

    </div>

    <script>
        let currentCommand = "{{ state.command }}";
        let lastUserActionTime = 0;

        function updateButtonUI(cmd) {
            const iconPlay = document.getElementById('icon-play');
            const iconPause = document.getElementById('icon-pause');
            const statusText = document.getElementById('engine-status-text');

            currentCommand = cmd;
            statusText.innerText = cmd;

            if (cmd === 'PLAY') {
                iconPlay.style.display = 'none';
                iconPause.style.display = 'block';
            } else {
                iconPlay.style.display = 'block';
                iconPause.style.display = 'none';
            }
        }

        updateButtonUI(currentCommand);

        function toggleEngine() {
            const nextCmd = (currentCommand === 'PLAY') ? 'PAUSE' : 'PLAY';
            lastUserActionTime = Date.now();
            updateButtonUI(nextCmd);
            sendCommand(nextCmd);
        }

        function handleStrategyChange() {
            const strat = document.getElementById('strategy').value;
            const manualPanel = document.getElementById('manual-execution-panel');
            if (strat === 'PURE_EXECUTION') {
                manualPanel.style.display = 'block';
            } else {
                manualPanel.style.display = 'none';
            }
        }

        handleStrategyChange();

        setInterval(() => {
            if (Date.now() - lastUserActionTime < 3000) return;

            fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                const badge = document.getElementById('status-badge');
                if (data.online) {
                    badge.className = "px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 tracking-wider";
                    badge.innerText = "ONLINE";
                } else {
                    badge.className = "px-3 py-1 rounded-full text-xs font-bold bg-rose-500/10 text-rose-500 border border-rose-500/25 tracking-wider";
                    badge.innerText = "OFFLINE";
                }
                document.getElementById('ea-last-seen').innerText = data.ea.lastSeen;
                document.getElementById('ea-strategy').innerText = data.ea.strategy || 'PURE_EXECUTION';
                document.getElementById('ea-last-executed').innerText = data.ea.lastExecuted || 'None';
                
                document.getElementById('stat-symbol').innerText = data.state.symbol || 'XAUUSD';
                document.getElementById('stat-max-trades').innerText = data.state.maxTrades || 2;
                
                if (data.state.command && data.state.command !== currentCommand && data.state.command !== 'MANUAL_BUY' && data.state.command !== 'MANUAL_SELL') {
                    updateButtonUI(data.state.command);
                }
            }).catch(err => console.error("Telemetry sync error:", err));
        }, 2000);

        function sendCommand(cmd) {
            const sym = document.getElementById('symbol').value.toUpperCase();
            const maxT = document.getElementById('maxTrades').value;

            document.getElementById('stat-symbol').innerText = sym;
            document.getElementById('stat-max-trades').innerText = maxT;

            const data = {
                command: cmd,
                strategy: document.getElementById('strategy').value,
                symbol: sym,
                lotSize: parseFloat(document.getElementById('lotSize').value),
                maxTrades: parseInt(maxT),
                tpEnabled: document.getElementById('tpEnabled').value === 'true',
                tp1: parseFloat(document.getElementById('tp1').value),
                tp2: parseFloat(document.getElementById('tp2').value),
                tp3: parseFloat(document.getElementById('tp3').value),
                tp4: parseFloat(document.getElementById('tp4').value)
            };

            fetch('/api/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }

        function sendManualAction(actionCmd) {
            lastUserActionTime = Date.now();
            sendCommand(actionCmd);
        }

        function saveConfig() {
            lastUserActionTime = Date.now();
            sendCommand(currentCommand);
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
  state = load_state()
  response_data = state.copy()
  # ONE-SHOT CONSUMER: Clear manual triggers so they never loop continuously on polls
  if state["command"] in ["MANUAL_BUY", "MANUAL_SELL"]:
    state["command"] = "PLAY"
    save_state(state)
  return jsonify(response_data)


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
      "strategy",
      "lotSize",
      "maxTrades",
      "tpEnabled",
      "tp1",
      "tp2",
      "tp3",
      "tp4",
  ]:
    if key in data:
      state[key] = data[key]

  state["updatedAt"] = int(datetime.utcnow().timestamp())
  save_state(state)
  return jsonify(state)


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)
