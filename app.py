from datetime import datetime, timezone
from flask import Flask, jsonify, render_template_string, request
import os

app = Flask(__name__)

# Bridge Configuration state (TP and SL completely removed)
bridge_state = {
    "symbol": "XAUUSD",
    "strategy": "PURE_EXECUTION",
    "timeframe": "M5",
    "lotSize": 0.01,
    "maxTrades": 2,
    "command": "PLAY",
}

ea_heartbeat = {
    "pair": "DTAY89",
    "symbol": "XAUUSD",
    "strategy": "PURE_EXECUTION",
    "enabled": True,
    "lastExecuted": "PLAY ACTIVE",
    "lastSeen": "Never",
}

# All 17 Professional Strategies
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

# Your exact original UI template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>D'TAY89 NEURAL</title>
    <style>
        body { background-color: #050805; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 15px; display: flex; justify-content: center; }
        .app-container { width: 100%; max-width: 480px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
        
        /* Header */
        .header { display: flex; justify-content: space-between; align-items: center; padding: 10px 5px; font-size: 14px; font-weight: bold; letter-spacing: 0.5px; }
        .header-title { color: #00ff66; display: flex; align-items: center; gap: 8px; }
        .status-badge { font-size: 11px; padding: 4px 12px; border-radius: 12px; font-weight: bold; background: #0b1f13; border: 1px solid #00ff66; color: #00ff66; }
        .status-offline { background: #1f0b0b; border-color: #ff3333; color: #ff3333; }

        /* Main Run Circle Button */
        .circle-container { display: flex; justify-content: center; margin: 10px 0; }
        .run-circle { width: 180px; height: 180px; border-radius: 50%; background: #0c140e; border: 2px solid #00ff66; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 0 25px rgba(0, 255, 102, 0.2); transition: all 0.2s ease; }
        .run-circle.paused { border-color: #ffaa00; box-shadow: 0 0 25px rgba(255, 170, 0, 0.2); }
        .play-icon { font-size: 36px; color: #00ff66; margin-bottom: 5px; }
        .paused .play-icon { color: #ffaa00; }
        .run-text { font-size: 14px; font-weight: bold; color: #00ff66; letter-spacing: 1px; }
        .paused .run-text { color: #ffaa00; }

        /* Force Buy / Sell Buttons */
        .action-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .btn-action { padding: 16px; border-radius: 12px; font-weight: bold; font-size: 13px; letter-spacing: 0.5px; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .btn-force-buy { background: #0b2214; border: 1px solid #00ff66; color: #00ff66; }
        .btn-force-buy:active { background: #123820; }
        .btn-force-sell { background: #220b0b; border: 1px solid #ff3333; color: #ff3333; }
        .btn-force-sell:active { background: #381212; }
        .dot { width: 8px; height: 8px; border-radius: 50%; }
        .dot-green { background: #00ff66; box-shadow: 0 0 8px #00ff66; }
        .dot-red { background: #ff3333; box-shadow: 0 0 8px #ff3333; }

        /* Telemetry Log Card */
        .telemetry-card { background: #0c110e; border: 1px solid #1a2e20; border-radius: 16px; padding: 20px; box-shadow: 0 8px 20px rgba(0,0,0,0.5); }
        .telemetry-header { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #6b7280; letter-spacing: 1px; margin-bottom: 15px; border-bottom: 1px solid #142217; padding-bottom: 8px; }
        
        .telemetry-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 13px; }
        .telemetry-label { color: #8892b0; }
        .telemetry-value { font-weight: bold; color: #00ff66; font-family: monospace; }
        
        .strategy-select { background: #050805; border: 1px solid #1a2e20; color: #00ff66; padding: 4px 8px; border-radius: 6px; font-size: 12px; outline: none; max-width: 200px; }
        
        .execution-status-box { margin-top: 15px; border: 1px solid #1a2e20; border-radius: 10px; padding: 12px; background: #050805; font-size: 11px; color: #6b7280; }
        .execution-status-text { margin-top: 4px; color: #00ff66; font-weight: bold; font-size: 12px; letter-spacing: 0.5px; }

        /* Floating Action Button (+) Opens Config Settings */
        .fab-container { display: flex; justify-content: center; margin-top: 10px; }
        .fab-btn { width: 44px; height: 44px; border-radius: 50%; background: #0b2214; border: 1px solid #00ff66; color: #00ff66; font-size: 20px; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 0 15px rgba(0, 255, 102, 0.3); }

        /* Configuration Modal */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 100; justify-content: center; align-items: center; }
        .modal-content { background: #0c110e; border: 1px solid #00ff66; border-radius: 16px; padding: 25px; width: 90%; max-width: 400px; display: flex; flex-direction: column; gap: 15px; }
        .modal-title { color: #00ff66; font-size: 16px; font-weight: bold; border-bottom: 1px solid #1a2e20; padding-bottom: 8px; }
        .form-group { display: flex; flex-direction: column; gap: 5px; font-size: 13px; }
        .form-group label { color: #8892b0; }
        .form-control { background: #050805; border: 1px solid #1a2e20; color: #00ff66; padding: 10px; border-radius: 8px; font-size: 14px; outline: none; }
        .modal-buttons { display: flex; gap: 10px; margin-top: 10px; }
        .btn-modal { flex: 1; padding: 12px; border-radius: 8px; font-weight: bold; cursor: pointer; border: none; }
        .btn-save { background: #0b2214; border: 1px solid #00ff66; color: #00ff66; }
        .btn-close { background: #220b0b; border: 1px solid #ff3333; color: #ff3333; }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Header -->
        <div class="header">
            <div class="header-title">🟢 D'TAY89 NEURAL</div>
            <div id="connectionBadge" class="status-badge status-offline">OFFLINE</div>
        </div>

        <!-- Center Running Circle -->
        <div class="circle-container">
            <div id="runCircle" class="run-circle" onclick="togglePlayPause()">
                <div id="playIcon" class="play-icon">&#9658;</div>
                <div id="runText" class="run-text">RUNNING</div>
            </div>
        </div>

        <!-- Force Buy / Sell -->
        <div class="action-buttons">
            <button class="btn-action btn-force-buy" onclick="sendAction('MANUAL_BUY')">
                FORCE BUY <span class="dot dot-green"></span>
            </button>
            <button class="btn-action btn-force-sell" onclick="sendAction('MANUAL_SELL')">
                FORCE SELL <span class="dot dot-red"></span>
            </button>
        </div>

        <!-- Telemetry Log Card -->
        <div class="telemetry-card">
            <div class="telemetry-header">
                <span>LIVE TELEMETRY LOG</span>
                <span id="utcTime">--:--:-- UTC</span>
            </div>

            <div class="telemetry-row">
                <span class="telemetry-label">Engine Command:</span>
                <span id="lblCommand" class="telemetry-value">PLAY</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Active Symbol:</span>
                <span id="lblSymbol" class="telemetry-value">XAUUSD</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Active Strategy:</span>
                <select id="strategySelect" class="strategy-select" onchange="updateStrategy()">
                    {% for strat in strategies %}
                    <option value="{{ strat }}">{{ strat }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Timeframe:</span>
                <span id="lblTf" class="telemetry-value">M5</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Lot Size:</span>
                <span id="lblLot" class="telemetry-value">0.01</span>
            </div>

            <div class="execution-status-box">
                <div>Execution Status:</div>
                <div id="lblExec" class="execution-status-text">PLAY ACTIVE</div>
            </div>
        </div>

        <!-- Floating Action Button (+) Opens Config Settings -->
        <div class="fab-container">
            <div class="fab-btn" onclick="openConfigModal()">+</div>
        </div>
    </div>

    <!-- Configuration Settings Modal -->
    <div id="configModal" class="modal">
        <div class="modal-content">
            <div class="modal-title">&#9881; Configuration Settings</div>
            <div class="form-group">
                <label>Symbol:</label>
                <input type="text" id="cfgSymbol" class="form-control" value="XAUUSD">
            </div>
            <div class="form-group">
                <label>Timeframe:</label>
                <select id="cfgTimeframe" class="form-control">
                    <option value="M1">M1</option>
                    <option value="M5">M5</option>
                    <option value="M15">M15</option>
                    <option value="H1">H1</option>
                    <option value="H4">H4</option>
                    <option value="D1">D1</option>
                </select>
            </div>
            <div class="form-group">
                <label>Lot Size:</label>
                <input type="number" step="0.01" id="cfgLotSize" class="form-control" value="0.01">
            </div>
            <div class="form-group">
                <label>Max Simultaneous Trades:</label>
                <input type="number" id="cfgMaxTrades" class="form-control" value="2">
            </div>
            <div class="modal-buttons">
                <button class="btn-modal btn-close" onclick="closeConfigModal()">Cancel</button>
                <button class="btn-modal btn-save" onclick="saveConfig()">Save Settings</button>
            </div>
        </div>
    </div>

    <script>
        function updateUtcClock() {
            const now = new Date();
            document.getElementById('utcTime').innerText = now.toUTCString().split(' ')[4] + ' UTC';
        }
        setInterval(updateUtcClock, 1000);
        updateUtcClock();

        function openConfigModal() {
            document.getElementById('configModal').style.display = 'flex';
        }

        function closeConfigModal() {
            document.getElementById('configModal').style.display = 'none';
        }

        function togglePlayPause() {
            const currentCmd = document.getElementById('lblCommand').innerText;
            const newCmd = (currentCmd === 'PLAY' || currentCmd === 'RUNNING') ? 'PAUSE' : 'PLAY';
            sendPost({ command: newCmd });
        }

        function sendAction(action) {
            sendPost({ command: action });
        }

        function updateStrategy() {
            const strat = document.getElementById('strategySelect').value;
            sendPost({ strategy: strat });
        }

        function saveConfig() {
            const sym = document.getElementById('cfgSymbol').value;
            const tf = document.getElementById('cfgTimeframe').value;
            const lot = parseFloat(document.getElementById('cfgLotSize').value);
            const maxT = parseInt(document.getElementById('cfgMaxTrades').value);
            
            sendPost({
                symbol: sym,
                timeframe: tf,
                lotSize: lot,
                maxTrades: maxT
            });
            closeConfigModal();
        }

        function sendPost(payload) {
            fetch('/api/bridge/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            }).then(res => res.json()).then(data => {
                updateUI(data.bridge, data.heartbeat);
            });
        }

        function fetchStatus() {
            fetch('/api/status')
                .then(res => res.json())
                .then(data => {
                    updateUI(data.bridge, data.heartbeat);
                });
        }

        function updateUI(bridge, hb) {
            document.getElementById('lblCommand').innerText = bridge.command;
            document.getElementById('lblSymbol').innerText = bridge.symbol;
            document.getElementById('lblTf').innerText = bridge.timeframe;
            document.getElementById('lblLot').innerText = bridge.lotSize;
            
            const stratSelect = document.getElementById('strategySelect');
            if(stratSelect.value !== bridge.strategy) {
                stratSelect.value = bridge.strategy;
            }

            document.getElementById('lblExec').innerText = hb.lastExecuted || 'None';

            const circle = document.getElementById('runCircle');
            const playIcon = document.getElementById('playIcon');
            const runText = document.getElementById('runText');
            
            if(bridge.command === 'PLAY') {
                circle.className = 'run-circle';
                playIcon.innerHTML = '&#9658;';
                runText.innerText = 'RUNNING';
            } else {
                circle.className = 'run-circle paused';
                playIcon.innerHTML = '&#10074;&#10074;';
                runText.innerText = 'PAUSED';
            }

            const badge = document.getElementById('connectionBadge');
            if(hb.lastSeen !== 'Never') {
                badge.className = 'status-badge';
                badge.innerText = 'ONLINE';
            } else {
                badge.className = 'status-badge status-offline';
                badge.innerText = 'OFFLINE';
            }
        }

        setInterval(fetchStatus, 3000);
        fetchStatus();
    </script>
</body>
</html>
"""


@app.route("/")
def index():
  return render_template_string(HTML_TEMPLATE, strategies=SUPPORTED_STRATEGIES)


@app.route("/api/bridge/command", methods=["GET"])
def get_command():
  return jsonify({"bridge": bridge_state, "heartbeat": ea_heartbeat})


@app.route("/api/bridge/command", methods=["POST"])
def post_command():
  global bridge_state
  data = request.get_json() or {}
  for key in bridge_state:
    if key in data:
      bridge_state[key] = data[key]
  return jsonify({"bridge": bridge_state, "heartbeat": ea_heartbeat})


@app.route("/api/bridge/heartbeat", methods=["POST"])
def post_heartbeat():
  global ea_heartbeat
  data = request.get_json() or {}
  ea_heartbeat.update(data)
  ea_heartbeat["lastSeen"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
  return jsonify(
      {"status": "success", "bridge": bridge_state, "heartbeat": ea_heartbeat}
  )


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
