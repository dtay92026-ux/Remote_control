from flask import Flask, jsonify, request, render_template_string
import os
import datetime

app = Flask(__name__)

# Bridge state shared between MT5 EA and Web Dashboard
bridge_state = {
    "enabled": False,
    "strategy": "TREND_BREAKOUT",
    "symbol": "XAUUSDm",
    "timeframe": "M15",
    "command": "NONE",
    "lotSize": 0.01,
    "maxTrades": 2,
    "lastHeartbeat": "Never",
    "lastExecuted": "None"
}

# All 17 Professional Strategies
SUPPORTED_STRATEGIES = [
    "TREND_BREAKOUT", "RANGE_REVERSAL", "PURE_EXECUTION", "SUPPORT_RESISTANCE",
    "EMA_CROSSOVER", "RSI_EXTREME", "MACD_MOMENTUM", "ATR_BREAKOUT",
    "BOLLINGER_BOUNCE", "STOCHASTIC_EXTREME", "PARABOLIC_SAR", "CCI_EXTREME",
    "WILLIAMS_R", "MOMENTUM_OSCILLATOR", "SUPER_TREND", "VWAP_BOUNCE", "ICHIMOKU_BREAKOUT"
]

# Embedded Web Dashboard UI
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>D'TAY89 Trading Bridge & Control Center</title>
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }
        h1 { color: #38bdf8; margin-top: 0; font-size: 24px; border-bottom: 2px solid #334155; padding-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }
        .status-badge { font-size: 14px; padding: 5px 12px; border-radius: 20px; font-weight: bold; }
        .status-online { background: #065f46; color: #34d399; }
        .status-offline { background: #7f1d1d; color: #f87171; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
        .card { background: #0f172a; padding: 20px; border-radius: 8px; border: 1px solid #334155; }
        .card h3 { margin-top: 0; color: #cbd5e1; font-size: 16px; border-bottom: 1px solid #1e293b; padding-bottom: 8px; }
        label { display: block; margin-bottom: 8px; font-size: 13px; color: #94a3b8; }
        select, button { width: 100%; padding: 12px; border-radius: 6px; border: 1px solid #475569; background: #1e293b; color: #fff; font-size: 14px; margin-bottom: 15px; cursor: pointer; }
        select:focus, button:focus { outline: none; border-color: #38bdf8; }
        .btn-group { display: flex; gap: 10px; }
        button.btn-play { background: #059669; border-color: #059669; font-weight: bold; }
        button.btn-play:hover { background: #047857; }
        button.btn-pause { background: #d97706; border-color: #d97706; font-weight: bold; }
        button.btn-pause:hover { background: #b45309; }
        button.btn-buy { background: #2563eb; border-color: #2563eb; font-weight: bold; }
        button.btn-buy:hover { background: #1d4ed8; }
        button.btn-sell { background: #dc2626; border-color: #dc2626; font-weight: bold; }
        button.btn-sell:hover { background: #b91c1c; }
        .stat-row { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; }
        .stat-label { color: #94a3b8; }
        .stat-value { font-weight: bold; color: #e2e8f0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>
            <span>D'TAY89 Bridge Dashboard</span>
            <span id="connectionStatus" class="status-badge status-offline">OFFLINE</span>
        </h1>
        
        <div class="grid">
            <div class="card">
                <h3>Strategy & Execution</h3>
                <label for="strategySelect">Select Strategy (17 Available):</label>
                <select id="strategySelect" onchange="updateStrategy()">
                    {% for strat in strategies %}
                    <option value="{{ strat }}" {% if strat == state.strategy %}selected{% endif %}>{{ strat }}</option>
                    {% endfor %}
                </select>

                <label>Master Control:</label>
                <div class="btn-group">
                    <button class="btn-play" onclick="sendControl('PLAY')">▶ START EA</button>
                    <button class="btn-pause" onclick="sendControl('PAUSE')">⏸ PAUSE EA</button>
                </div>

                <label>Manual Override:</label>
                <div class="btn-group">
                    <button class="btn-buy" onclick="sendControl('MANUAL_BUY')">🟢 BUY</button>
                    <button class="btn-sell" onclick="sendControl('MANUAL_SELL')">🔴 SELL</button>
                </div>
            </div>

            <div class="card">
                <h3>Live Telemetry</h3>
                <div class="stat-row"><span class="stat-label">Symbol:</span><span class="stat-value" id="lblSymbol">{{ state.symbol }}</span></div>
                <div class="stat-row"><span class="stat-label">Timeframe:</span><span class="stat-value" id="lblTf">{{ state.timeframe }}</span></div>
                <div class="stat-row"><span class="stat-label">Lot Size:</span><span class="stat-value" id="lblLot">{{ state.lotSize }}</span></div>
                <div class="stat-row"><span class="stat-label">Max Trades:</span><span class="stat-value" id="lblMax">{{ state.maxTrades }}</span></div>
                <div class="stat-row"><span class="stat-label">EA State:</span><span class="stat-value" id="lblState">{% if state.enabled %}ACTIVE{% else %}PAUSED{% endif %}</span></div>
                <div class="stat-row"><span class="stat-label">Last Heartbeat:</span><span class="stat-value" id="lblHb">{{ state.lastHeartbeat }}</span></div>
                <div class="stat-row"><span class="stat-label">Last Executed:</span><span class="stat-value" id="lblExec">{{ state.lastExecuted }}</span></div>
            </div>
        </div>
    </div>

    <script>
        function updateStrategy() {
            const strat = document.getElementById('strategySelect').value;
            fetch('/api/set_strategy', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({strategy: strat})
            }).then(res => res.json()).then(data => console.log('Strategy updated:', data));
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

        function fetchStatus() {
            fetch('/api/status')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('lblSymbol').innerText = data.symbol;
                    document.getElementById('lblTf').innerText = data.timeframe;
                    document.getElementById('lblLot').innerText = data.lotSize;
                    document.getElementById('lblMax').innerText = data.maxTrades;
                    document.getElementById('lblState').innerText = data.enabled ? 'ACTIVE' : 'PAUSED';
                    document.getElementById('lblHb').innerText = data.lastHeartbeat;
                    document.getElementById('lblExec').innerText = data.lastExecuted;
                    
                    const badge = document.getElementById('connectionStatus');
                    if(data.isOnline) {
                        badge.className = 'status-badge status-online';
                        badge.innerText = 'ONLINE';
                    } else {
                        badge.className = 'status-badge status-offline';
                        badge.innerText = 'OFFLINE';
                    }
                });
        }

        setInterval(fetchStatus, 3000);
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
    bridge_state["command"] = "NONE" # Reset command after pickup to prevent loops
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
    bridge_state["lastExecuted"] = data.get("lastExecuted", "None")
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
        if action == "PLAY": bridge_state["enabled"] = True
        elif action == "PAUSE": bridge_state["enabled"] = False
        return jsonify({"success": True, "action": action})
    return jsonify({"success": False, "error": "Invalid action"}), 400

@app.route('/api/status', methods=['GET'])
def get_status():
    is_online = False
    if bridge_state["lastHeartbeat"] != "Never":
        try:
            last_hb_time = datetime.datetime.strptime(bridge_state["lastHeartbeat"], "%Y-%m-%d %H:%M:%S")
            diff = (datetime.datetime.now() - last_hb_time).total_seconds()
            if diff < 15: # Considered online if heartbeat received in last 15 seconds
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
