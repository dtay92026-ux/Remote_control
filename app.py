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
    <title>D'TAY89 | Neural Executor</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-black text-slate-100 min-h-screen font-sans p-4 flex justify-center">
    <div class="w-full max-w-sm space-y-4 pb-10">
        
        <!-- Top Navigation Bar -->
        <div class="flex justify-between items-center px-2 py-3 border-b border-zinc-900">
            <span class="text-xs text-zinc-500 font-mono">LIVE SYSTEM</span>
            <div id="status-badge" class="px-3 py-1 rounded-full text-xs font-bold bg-rose-500/10 text-rose-500 border border-rose-500/20 tracking-wider shadow-[0_0_10px_rgba(244,63,94,0.2)]">
                OFFLINE
            </div>
        </div>

        <!-- Larger Custom Robot Head Logo Circle with Fallback -->
        <div class="flex flex-col items-center justify-center pt-2 pb-1 space-y-3">
            <div class="relative w-40 h-40 rounded-full bg-zinc-950 border-2 border-emerald-500/60 flex items-center justify-center shadow-[0_0_35px_rgba(16,185,129,0.35)] overflow-hidden">
                <!-- User Image -->
                <img src="/static/logo.png" alt="Neural Bot" class="w-full h-full object-cover object-[center_32%] scale-125" onerror="this.style.display='none'; document.getElementById('fallback-robot').style.display='flex';">
                
                <!-- Fallback Neon Icon if image is missing -->
                <div id="fallback-robot" style="display:none;" class="absolute inset-0 bg-zinc-950 flex items-center justify-center">
                    <svg class="w-20 h-20 text-emerald-400 drop-shadow-[0_0_10px_rgba(52,211,153,0.9)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 3v2m6-2v2M4.5 9h15M6 9l1.5 9h9L18 9M9 13h1m4 0h1m-7 3h6" />
                        <circle cx="10" cy="11" r="1" fill="currentColor"/>
                        <circle cx="14" cy="11" r="1" fill="currentColor"/>
                    </svg>
                </div>
            </div>
            <h1 class="text-lg font-black tracking-widest text-emerald-400 uppercase">D'TAY89 NEURAL EA</h1>
        </div>

        <!-- Quick Status Grid Panel -->
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
                <span class="block text-[10px] text-zinc-500 uppercase">Trades</span>
                <span class="text-xs font-bold text-zinc-200 font-mono">{{ state.maxTrades }}</span>
            </div>
        </div>

        <!-- Sleek Single Morphing Play/Pause Button (No Words, No Emojis) -->
        <div class="bg-zinc-950 border border-zinc-900 rounded-2xl p-4 shadow-lg flex flex-col items-center justify-center space-y-2">
            <button id="engine-toggle-btn" onclick="toggleEngine()" class="w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-[0_0_25px_rgba(16,185,129,0.3)] active:scale-95 border-2">
                <!-- Play Icon (Triangle) -->
                <svg id="icon-play" class="w-8 h-8 fill-current translate-x-0.5" viewBox="0 0 24 24" style="display:none;">
                    <path d="M8 5v14l11-7z"/>
                </svg>
                <!-- Pause Icon (Bars) -->
                <svg id="icon-pause" class="w-8 h-8 fill-current" viewBox="0 0 24 24" style="display:none;">
                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                </svg>
            </button>
        </div>

        <!-- Strategy & Parameters Settings Panel -->
        <div class="bg-zinc-950 border border-zinc-900 rounded-2xl p-4 shadow-lg space-y-3">
            <div class="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Strategy Matrix</div>
            
            <div class="space-y-3">
                <div>
                    <label class="block text-[11px] text-zinc-500 mb-1">Active Neural Strategy</label>
                    <select id="strategy" onchange="updateRecommendedTimeframe()" class="w-full bg-black border border-zinc-800 rounded-xl p-3 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono">
                        {% for key, val in strategies.items() %}
                        <option value="{{ key }}" {% if state.strategy == key %}selected{% endif %}>{{ val.name }} ({{ val.timeframe }})</option>
                        {% endfor %}
                    </select>
                </div>

                <div class="grid grid-cols-3 gap-2">
                    <div>
                        <label class="block text-[10px] text-zinc-500 mb-1">Symbol</label>
                        <input type="text" id="symbol" value="{{ state.symbol }}" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono uppercase text-center">
                    </div>
                    <div>
                        <label class="block text-[10px] text-zinc-500 mb-1">Timeframe</label>
                        <select id="timeframe" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
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
                        <label class="block text-[10px] text-zinc-500 mb-1">Account</label>
                        <select id="account" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
                            <option value="DEMO" {% if state.account == 'DEMO' %}selected{% endif %}>DEMO</option>
                            <option value="LIVE" {% if state.account == 'LIVE' %}selected{% endif %}>LIVE</option>
                        </select>
                    </div>
                </div>

                <div class="grid grid-cols-3 gap-2">
                    <div>
                        <label class="block text-[10px] text-zinc-500 mb-1">Lot Size</label>
                        <input type="number" step="0.01" id="lotSize" value="{{ state.lotSize }}" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
                    </div>
                    <div>
                        <label class="block text-[10px] text-zinc-500 mb-1">Max Trades</label>
                        <input type="number" id="maxTrades" value="{{ state.maxTrades }}" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
                    </div>
                    <div>
                        <label class="block text-[10px] text-zinc-500 mb-1">Stop Loss</label>
                        <input type="number" id="stopLoss" value="{{ state.stopLoss }}" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
                    </div>
                </div>

                <button onclick="saveConfig()" class="w-full bg-zinc-900 hover:bg-zinc-800 text-emerald-400 font-bold py-3 rounded-xl border border-emerald-500/30 transition text-xs tracking-wider shadow-sm">
                    UPDATE CONFIGURATION
                </button>
            </div>
        </div>

        <!-- Telemetry Panel -->
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

        function updateButtonUI(cmd) {
            const btn = document.getElementById('engine-toggle-btn');
            const iconPlay = document.getElementById('icon-play');
            const iconPause = document.getElementById('icon-pause');
            const statusText = document.getElementById('engine-status-text');

            currentCommand = cmd;
            statusText.innerText = cmd;

            if (cmd === 'PLAY') {
                btn.className = "w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-[0_0_30px_rgba(16,185,129,0.6)] active:scale-95 border-2 border-emerald-400 bg-emerald-500 text-black";
                iconPlay.style.display = 'none';
                iconPause.style.display = 'block';
            } else {
                btn.className = "w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-[0_0_20px_rgba(244,63,94,0.3)] active:scale-95 border-2 border-zinc-700 bg-zinc-900 text-zinc-400";
                iconPlay.style.display = 'block';
                iconPause.style.display = 'none';
            }
        }

        updateButtonUI(currentCommand);

        function toggleEngine() {
            const nextCmd = (currentCommand === 'PLAY') ? 'PAUSE' : 'PLAY';
            sendCommand(nextCmd);
        }

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
                    badge.className = "px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 tracking-wider shadow-[0_0_10px_rgba(16,185,129,0.3)]";
                    badge.innerText = "ONLINE";
                } else {
                    badge.className = "px-3 py-1 rounded-full text-xs font-bold bg-rose-500/10 text-rose-500 border border-rose-500/20 tracking-wider shadow-[0_0_10px_rgba(244,63,94,0.2)]";
                    badge.innerText = "OFFLINE";
                }
                document.getElementById('ea-last-seen').innerText = data.ea.lastSeen;
                document.getElementById('ea-strategy').innerText = data.ea.strategy || 'PURE_EXECUTION';
                document.getElementById('ea-last-executed').innerText = data.ea.lastExecuted || 'None';
                document.getElementById('stat-symbol').innerText = data.state.symbol || 'XAUUSD';
                
                if (data.state.command && data.state.command !== currentCommand) {
                    updateButtonUI(data.state.command);
                }
            }).catch(err => console.error("Telemetry sync error:", err));
        }, 2000);

        function sendCommand(cmd) {
            updateButtonUI(cmd);
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
