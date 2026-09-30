from datetime import datetime
import json
import os
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

STATE_FILE = "bridge_state.json"

default_state = {
    "pair": "DTAY89",
    "command": "PAUSE",
    "symbol": "XAUUSD",
    "timeframe": "M15",
    "strategy": "PURE_EXECUTION",
    "lotSize": 0.01,
    "maxTrades": 2,
    "tpEnabled": True,
    "tp1": 1.0,
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
    "lastExecuted": "Engine Idle / Initialized",
    "lastSeen": "Never",
    "lastSeenEpoch": 0,
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>D'TAY89 | Neural Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-black text-slate-100 min-h-screen font-sans flex flex-col items-center justify-between p-4 selection:bg-emerald-500 selection:text-black">

    <!-- TOP HEADER BAR -->
    <div class="w-full max-w-md flex justify-between items-center px-4 py-3 border-b border-zinc-900 bg-zinc-950/60 backdrop-blur rounded-2xl">
        <div class="flex items-center space-x-2">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <span class="text-xs font-mono tracking-widest text-zinc-400 font-bold">D'TAY89 NEURAL</span>
        </div>
        <div id="status-badge" class="px-3 py-1 rounded-full text-[11px] font-bold bg-rose-500/10 text-rose-500 border border-rose-500/25 tracking-wider font-mono">
            OFFLINE
        </div>
    </div>

    <!-- MAIN INTERFACE BODY -->
    <div class="w-full max-w-md my-auto space-y-6 py-6 flex flex-col items-center">
        
        <!-- GLOWING CENTER EXECUTE / ENGINE BUTTON -->
        <div class="flex flex-col items-center justify-center space-y-3">
            <button id="engine-toggle-btn" onclick="toggleEngine()" class="relative w-44 h-44 rounded-full bg-zinc-950 border-2 border-emerald-500/60 flex flex-col items-center justify-center shadow-[0_0_45px_rgba(16,185,129,0.3)] transition-all duration-300 active:scale-95 group overflow-hidden cursor-pointer">
                <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.15)_0%,transparent_70%)] group-hover:bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.3)_0%,transparent_70%)] transition-all"></div>
                
                <svg id="icon-play" class="w-12 h-12 fill-current text-emerald-400 translate-x-1 drop-shadow-[0_0_12px_rgba(52,211,153,0.8)]" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z"/>
                </svg>
                <svg id="icon-pause" class="w-12 h-12 fill-current text-rose-400 drop-shadow-[0_0_12px_rgba(244,63,94,0.8)]" viewBox="0 0 24 24" style="display:none;">
                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                </svg>
                
                <span id="engine-btn-label" class="mt-2 text-xs font-black tracking-widest text-emerald-400 font-mono">EXECUTE</span>
            </button>
        </div>

        <!-- MANUAL OVERRIDE BUTTONS -->
        <div class="w-full grid grid-cols-2 gap-3 px-2">
            <button onclick="sendManualAction('MANUAL_BUY')" class="bg-emerald-600 hover:bg-emerald-500 text-black font-extrabold py-3.5 rounded-2xl transition text-xs tracking-wider shadow-[0_0_20px_rgba(16,185,129,0.4)] cursor-pointer active:scale-95">
                FORCE BUY 🟢
            </button>
            <button onclick="sendManualAction('MANUAL_SELL')" class="bg-rose-600 hover:bg-rose-500 text-white font-extrabold py-3.5 rounded-2xl transition text-xs tracking-wider shadow-[0_0_20px_rgba(244,63,94,0.4)] cursor-pointer active:scale-95">
                FORCE SELL 🔴
            </button>
        </div>

        <!-- LIVE TELEMETRY & EXECUTION LOG PANEL -->
        <div class="w-full bg-zinc-950 border border-zinc-900 rounded-3xl p-5 shadow-xl space-y-3 font-mono text-xs">
            <div class="flex justify-between items-center border-b border-zinc-900 pb-2">
                <span class="text-zinc-500 uppercase tracking-wider text-[10px]">Live Telemetry Log</span>
                <span id="log-time" class="text-emerald-400 text-[10px]">--:--:--</span>
            </div>
            <div class="space-y-2">
                <div class="flex justify-between">
                    <span class="text-zinc-500">Engine Command:</span>
                    <span id="log-command" class="text-zinc-200 font-bold">PAUSE</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-zinc-500">Active Strategy:</span>
                    <span id="log-strategy" class="text-emerald-400 truncate max-w-[180px]">PURE_EXECUTION</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-zinc-500">Timeframe:</span>
                    <span id="log-timeframe" class="text-zinc-200">M15</span>
                </div>
                <div class="pt-2 border-t border-zinc-900/80">
                    <span class="text-zinc-500 block mb-1 text-[10px]">Execution Status:</span>
                    <div id="log-executed" class="p-2.5 rounded-xl bg-black border border-zinc-800 text-emerald-400 text-[11px] truncate shadow-inner">
                        Engine Idle / Initialized
                    </div>
                </div>
            </div>
        </div>

    </div>

    <!-- BOTTOM MIDDLE FLOATING PLUS BUTTON -->
    <div class="w-full max-w-md flex justify-center py-2">
        <button onclick="openConfigModal()" class="w-14 h-14 rounded-full bg-emerald-500 hover:bg-emerald-400 text-black font-black text-2xl flex items-center justify-center shadow-[0_0_25px_rgba(16,185,129,0.5)] transition-all active:scale-90 cursor-pointer border-2 border-zinc-900">
            +
        </button>
    </div>

    <!-- CONFIGURATION MODAL -->
    <div id="config-modal" class="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4" style="display:none;">
        <div class="w-full max-w-sm bg-zinc-950 border border-emerald-500/30 rounded-3xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div class="flex justify-between items-center border-b border-zinc-900 pb-3">
                <h3 class="text-sm font-black text-emerald-400 uppercase tracking-widest">Neural Configuration</h3>
                <button onclick="closeConfigModal()" class="text-zinc-400 hover:text-white text-lg font-bold cursor-pointer px-2">✕</button>
            </div>

            <div class="space-y-3 font-sans text-xs">
                <!-- PAIR INPUT ADDED HERE -->
                <div>
                    <label class="block text-[11px] text-zinc-400 mb-1 font-mono">Pair Code</label>
                    <input type="text" id="pair" value="{{ state.pair }}" class="w-full bg-black border border-zinc-800 rounded-xl p-3 text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono">
                </div>

                <div>
                    <label class="block text-[11px] text-zinc-400 mb-1 font-mono">Strategy Matrix</label>
                    <select id="strategy" class="w-full bg-black border border-zinc-800 rounded-xl p-3 text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono">
                        <option value="PURE_EXECUTION">Pure Price Action Rejection & Engulfing</option>
                        <option value="SUPPORT_RESISTANCE">Support & Resistance Zone Reversal</option>
                        <option value="EMA_CROSSOVER">Exponential Moving Average Trend Crossover</option>
                        <option value="RSI_EXTREME">Relative Strength Index Mean Reversion</option>
                        <option value="MACD_MOMENTUM">MACD Momentum Breakout</option>
                        <option value="ATR_BREAKOUT">Average True Range Volatility Breakout</option>
                    </select>
                </div>

                <div>
                    <label class="block text-[11px] text-zinc-400 mb-1 font-mono">Timeframe Selector</label>
                    <select id="timeframe" class="w-full bg-black border border-zinc-800 rounded-xl p-3 text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono">
                        <option value="M1">M1</option>
                        <option value="M5">M5</option>
                        <option value="M15">M15</option>
                        <option value="M30">M30</option>
                        <option value="H1">H1</option>
                        <option value="H4">H4</option>
                        <option value="D1">D1</option>
                    </select>
                </div>

                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-[10px] text-zinc-400 mb-1 font-mono">Lot Size</label>
                        <input type="number" step="0.01" id="lotSize" value="{{ state.lotSize }}" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
                    </div>
                    <div>
                        <label class="block text-[10px] text-zinc-400 mb-1 font-mono">Max Trades</label>
                        <input type="number" id="maxTrades" value="{{ state.maxTrades }}" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-[10px] text-zinc-400 mb-1 font-mono">Take Profit Mode</label>
                        <select id="tpEnabled" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-zinc-200 focus:outline-none focus:border-emerald-500 font-mono text-center">
                            <option value="true">ENABLED</option>
                            <option value="false">DISABLED</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-[10px] text-zinc-400 mb-1 font-mono">TP Multiplier (R)</label>
                        <input type="number" step="0.5" id="tp1" value="{{ state.tp1 }}" class="w-full bg-black border border-zinc-800 rounded-xl p-2.5 text-emerald-400 focus:outline-none focus:border-emerald-500 font-mono text-center">
                    </div>
                </div>

                <button onclick="saveConfig()" class="w-full bg-emerald-500 hover:bg-emerald-400 text-black font-extrabold py-3.5 rounded-xl transition text-xs tracking-wider shadow-[0_0_20px_rgba(16,185,129,0.4)] cursor-pointer mt-2">
                    APPLY CONFIGURATION
                </button>
            </div>
        </div>
    </div>

    <script>
        let currentCommand = "{{ state.command }}";
        let lastUserActionTime = 0;

        document.getElementById('pair').value = "{{ state.pair }}";
        document.getElementById('strategy').value = "{{ state.strategy }}";
        document.getElementById('timeframe').value = "{{ state.timeframe }}";
        document.getElementById('tpEnabled').value = "{{ 'true' if state.tpEnabled else 'false' }}";

        function updateButtonUI(cmd) {
            const iconPlay = document.getElementById('icon-play');
            const iconPause = document.getElementById('icon-pause');
            const btnLabel = document.getElementById('engine-btn-label');
            const toggleBtn = document.getElementById('engine-toggle-btn');

            currentCommand = cmd;
            document.getElementById('log-command').innerText = cmd;

            if (cmd === 'PLAY') {
                iconPlay.style.display = 'block';
                iconPause.style.display = 'none';
                btnLabel.innerText = 'RUNNING';
                btnLabel.className = "mt-2 text-xs font-black tracking-widest text-emerald-400 font-mono drop-shadow-[0_0_8px_rgba(52,211,153,0.8)]";
                toggleBtn.className = "relative w-44 h-44 rounded-full bg-zinc-950 border-2 border-emerald-500 flex flex-col items-center justify-center shadow-[0_0_55px_rgba(16,185,129,0.5)] transition-all duration-300 active:scale-95 group overflow-hidden cursor-pointer";
            } else {
                iconPlay.style.display = 'none';
                iconPause.style.display = 'block';
                btnLabel.innerText = 'PAUSED';
                btnLabel.className = "mt-2 text-xs font-black tracking-widest text-rose-400 font-mono drop-shadow-[0_0_8px_rgba(244,63,94,0.8)]";
                toggleBtn.className = "relative w-44 h-44 rounded-full bg-zinc-950 border-2 border-rose-500/60 flex flex-col items-center justify-center shadow-[0_0_45px_rgba(244,63,94,0.3)] transition-all duration-300 active:scale-95 group overflow-hidden cursor-pointer";
            }
        }

        updateButtonUI(currentCommand);

        function toggleEngine() {
            const nextCmd = (currentCommand === 'PLAY') ? 'PAUSE' : 'PLAY';
            lastUserActionTime = Date.now();
            updateButtonUI(nextCmd);
            sendCommand(nextCmd);
        }

        function openConfigModal() {
            document.getElementById('config-modal').style.display = 'flex';
        }

        function closeConfigModal() {
            document.getElementById('config-modal').style.display = 'none';
        }

        setInterval(() => {
            if (Date.now() - lastUserActionTime < 3000) return;

            fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                const badge = document.getElementById('status-badge');
                if (data.online) {
                    badge.className = "px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 tracking-wider font-mono";
                    badge.innerText = "ONLINE";
                } else {
                    badge.className = "px-3 py-1 rounded-full text-[11px] font-bold bg-rose-500/10 text-rose-500 border border-rose-500/25 tracking-wider font-mono";
                    badge.innerText = "OFFLINE";
                }

                document.getElementById('log-time').innerText = data.ea.lastSeen || '--:--:--';
                document.getElementById('log-strategy').innerText = data.ea.strategy || data.state.strategy;
                document.getElementById('log-timeframe').innerText = data.state.timeframe || 'M15';
                
                const executedLog = document.getElementById('log-executed');
                const lastExec = data.ea.lastExecuted || 'Engine Idle';
                executedLog.innerText = lastExec;

                if (lastExec.includes('FAILED') || lastExec.includes('ERROR')) {
                    executedLog.className = "p-2.5 rounded-xl bg-black border border-rose-800 text-rose-400 text-[11px] truncate shadow-inner";
                } else if (lastExec.includes('SUCCESS') || lastExec.includes('EXECUTED')) {
                    executedLog.className = "p-2.5 rounded-xl bg-black border border-emerald-800 text-emerald-400 text-[11px] truncate shadow-inner";
                } else {
                    executedLog.className = "p-2.5 rounded-xl bg-black border border-zinc-800 text-zinc-300 text-[11px] truncate shadow-inner";
                }
                
                if (data.state.command && data.state.command !== currentCommand && data.state.command !== 'MANUAL_BUY' && data.state.command !== 'MANUAL_SELL') {
                    updateButtonUI(data.state.command);
                }
            }).catch(err => console.error("Telemetry sync error:", err));
        }, 2000);

        function sendCommand(cmd) {
            const data = {
                pair: document.getElementById('pair').value,
                command: cmd,
                strategy: document.getElementById('strategy').value,
                timeframe: document.getElementById('timeframe').value,
                lotSize: parseFloat(document.getElementById('lotSize').value),
                maxTrades: parseInt(document.getElementById('maxTrades').value),
                tpEnabled: document.getElementById('tpEnabled').value === 'true',
                tp1: parseFloat(document.getElementById('tp1').value)
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
            closeConfigModal();
            sendCommand(currentCommand);
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
  state = load_state()
  return render_template_string(HTML_TEMPLATE, state=state)


@app.route("/api/bridge/command", methods=["GET"])
def get_command():
  state = load_state()
  response_data = state.copy()
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
      "pair",
      "command",
      "timeframe",
      "strategy",
      "lotSize",
      "maxTrades",
      "tpEnabled",
      "tp1",
  ]:
    if key in data:
      state[key] = data[key]

  state["updatedAt"] = int(datetime.utcnow().timestamp())
  save_state(state)
  return jsonify(state)


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)
