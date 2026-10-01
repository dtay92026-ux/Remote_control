from flask import Flask, jsonify, request, render_template_string
import os
import datetime

app = Flask(__name__)

# Bridge state shared between MT5 EA and Web Dashboard
bridge_state = {
    "enabled": True,
    "strategy": "PURE_EXECUTION",
    "symbol": "XAUUSD",
    "timeframe": "M5",
    "command": "NONE",
    "lotSize": 0.01,
    "riskPerTrade": "$125.00",
    "maxTrades": 2,
    "lastHeartbeat": "Never",
    "lastExecuted": "PLAY ACTIVE",
    "isOnline": False
}

# All 17 Professional Strategies
SUPPORTED_STRATEGIES = [
    "PURE_EXECUTION", "TREND_BREAKOUT", "RANGE_REVERSAL", "SUPPORT_RESISTANCE",
    "EMA_CROSSOVER", "RSI_EXTREME", "MACD_MOMENTUM", "ATR_BREAKOUT",
    "BOLLINGER_BOUNCE", "STOCHASTIC_EXTREME", "PARABOLIC_SAR", "CCI_EXTREME",
    "WILLIAMS_R", "MOMENTUM_OSCILLATOR", "SUPER_TREND", "VWAP_BOUNCE", "ICHIMOKU_BREAKOUT"
]

# Exact D'TAY89 Neural UI Template Matching Your Design
HTML_TEMPLATE = '''
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
        
        .strategy-select { background: #050805; border: 1px solid #1a2e20; color: #00ff66; padding: 4px 8px; border-radius: 6px; font-size: 12px; outline: none; }
        
        .execution-status-box { margin-top: 15px; border: 1px solid #1a2e20; border-radius: 10px; padding: 12px; background: #050805; font-size: 11px; color: #6b7280; }
        .execution-status-text { margin-top: 4px; color: #00ff66; font-weight: bold; font-size: 12px; letter-spacing: 0.5px; }

        /* Floating Add Button */
        .fab-container { display: flex; justify-content: center; margin-top: 10px; }
        .fab-btn { width: 44px; height: 44px; border-radius: 50%; background: #0b2214; border: 1px solid #00ff66; color: #00ff66; font-size: 20px; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 0 15px rgba(0, 255, 102, 0.3); }
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
                <div id="playIcon" class="play-icon">▶</div>
                <div id="runText" class="run-text">RUNNING</div>
            </div>
        </div>

        <!-- Force Buy / Sell -->
        <div class="action-buttons">
            <button class="btn-action btn-force-buy" onclick="sendControl('MANUAL_BUY')">
                FORCE BUY <span class="dot dot-green"></span>
            </button>
            <button class="btn-action btn-force-sell" onclick="sendControl('MANUAL_SELL')">
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
                    <option value="{{ strat }}" {% if strat == state.strategy %}selected{% endif %}>{{ strat }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Timeframe:</span>
                <span id="lblTf" class="telemetry-value">M5</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Risk per Trade:</span>
                <span id="lblRisk" class="telemetry-value">$125.00</span>
            </div>

            <div class="execution-status-box">
                <div>Execution Status:</div>
                <div id="lblExec" class="execution-status-text">PLAY ACTIVE</div>
            </div>
        </div>

        <!-- Floating Action Button -->
        <div class="fab-container">
            <div class="fab-btn" onclick="alert('Strategy Config Active')">+</div>
        </div>
    </div>

    <script>
        function updateUtcClock() {
            const now = new Date();
            document.getElementById('utcTime').innerText = now.toUTCString().split(' ')[4] + ' UTC';
        }
        setInterval(updateUtcClock, 1000);
        updateUtcClock();

        function togglePlayPause() {
            const isRunning = document.getElementById('runText').innerText === 'RUNNING';
            const action = isRunning ? 'PAUSE' : 'PLAY';
            sendControl(action);
        }

        function sendControl(action) {
            fetch('/api/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: action})
            }).then(res => res.json()).then(data => {
                fetchStatus();
            });
        }

        function updateStrategy() {
            const strat = document.getElementById('strategySelect').value;
            fetch('/api/set_strategy', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({strategy: strat})
            }).then(res => res.json()).then(data => console.log('Strategy updated'));
        }

        function fetchStatus() {
            fetch('/api/status')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('lblCommand').innerText = data.command !== 'NONE' ? data.command : (data.enabled ? 'PLAY' : 'PAUSED');
                    document.getElementById('lblSymbol').innerText = data.symbol;
                    document.getElementById('lblTf').innerText = data.timeframe;
                    document.getElementById('lblRisk').innerText = data.riskPerTrade || '$125.00';
                    document.getElementById('lblExec').innerText = data.lastExecuted;
                    
                    if(document.getElementById('strategySelect').value !== data.strategy) {
                        document.getElementById('strategySelect').value = data.strategy;
                    }

                    const circle = document.getElementById('runCircle');
                    const playIcon = document.getElementById('playIcon');
                    const runText = document.getElementById('runText');
                    
                    if(data.enabled) {
                        circle.className = 'run-circle';
                        playIcon.innerText = '▶';
                        runText.innerText = 'RUNNING';
                    } else {
                        circle.className = 'run-circle paused';
                        playIcon.innerText = '⏸';
                        runText.innerText = 'PAUSED';
                    }

                    const badge = document.getElementById('connectionBadge');
                    if(data.isOnline) {
                        badge.className = 'status-badge';
                        badge.innerText = 'ONLINE';
                    } else {
                        badge.className = 'status-badge status-offline';
                        badge.innerText = 'OFFLINE';
                    }
                });
        }

        setInterval(fetchStatus, 3000);
        fetchStatus();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, strategies=SUPPORTED_STRATEGIES, state=bridge_state)

@app.route('/api/bridge/command', methods=['GET'])
def get_command():
    cmd = bridge_state["command"]
    bridge_state["command"] = "NONE"
    return jsonify({
        "enabled": bridge_state["enabled"],
        "strategy": bridge_state["strategy"],
        "symbol": bridge_state["symbol"],
        "timeframe": bridge_state["timeframe"],
        "command": cmd,
        "lotSize": bridge_state["lotSize"],
        "maxTrades": bridge_state["maxTrades"]
    })

@app.route('/api/bridge/heartbeat', methods=['POST'])
def receive_heartbeat():
    data = request.json or {}
    bridge_state["enabled"] = data.get("enabled", bridge_state["enabled"])
    bridge_state["symbol"] = data.get("symbol", bridge_state["symbol"])
    bridge_state["strategy"] = data.get("strategy", bridge_state["strategy"])
    bridge_state["lastExecuted"] = data.get("lastExecuted", "PLAY ACTIVE")
    bridge_state["lastHeartbeat"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"status": "received"})

@app.route('/api/set_strategy', methods=['POST'])
def set_strategy():
    data = request.json or {}
    strat = data.get("strategy")
    if strat in SUPPORTED_STRATEGIES:
        bridge_state["strategy"] = strat
        return jsonify({"success": True, "strategy": strat})
    return jsonify({"success": False, "error": "Invalid strategy"}), 400

@app.route('/api/control', methods=['POST'])
def control_ea():
    data = request.json or {}
    action = data.get("action")
    if action in ["PLAY", "PAUSE", "MANUAL_BUY", "MANUAL_SELL"]:
        bridge_state["command"] = action
        if action == "PLAY":
            bridge_state["enabled"] = True
            bridge_state["lastExecuted"] = "PLAY ACTIVE"
        elif action == "PAUSE":
            bridge_state["enabled"] = False
            bridge_state["lastExecuted"] = "PAUSED BY USER"
        elif action == "MANUAL_BUY":
            bridge_state["lastExecuted"] = "FORCE BUY EXECUTED"
        elif action == "MANUAL_SELL":
            bridge_state["lastExecuted"] = "FORCE SELL EXECUTED"
        return jsonify({"success": True, "action": action})
    return jsonify({"success": False, "error": "Invalid action"}), 400

@app.route('/api/status', methods=['GET'])
def get_status():
    is_online = False
    if bridge_state["lastHeartbeat"] != "Never":
        try:
            last_hb_time = datetime.datetime.strptime(bridge_state["lastHeartbeat"], "%Y-%m-%d %H:%M:%S")
            diff = (datetime.datetime.now() - last_hb_time).total_seconds()
            if diff < 15:
                is_online = True
        except:
            pass

    return jsonify({
        **bridge_state,
        "isOnline": is_online,
        "available_strategies": SUPPORTED_STRATEGIES
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
