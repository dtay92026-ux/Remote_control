"""
AlgoD Control Panel
-------------------
Flask bridge between the AlgoD.mq5 Expert Advisor and a black, mobile-first
control panel.

EA setup (AlgoD inputs):
    InpWebUrl     = https://<your-app>/api/bridge/heartbeat
    InpWebMethod  = WEB_POST_JSON
    InpWebApiKey  = <same value as EA_API_KEY, if you set one>
Also add the URL to MT5: Tools > Options > Expert Advisors > Allow WebRequest.

Environment variables (all optional, all recommended):
    PANEL_PIN    PIN required to open the panel / send commands
    EA_API_KEY   key the EA must send (X-API-Key or Bearer)
    STATE_FILE   where the last command is stored (default algod_state.json)
    PORT         listen port (default 5000)

Run with ONE worker (state lives in memory):
    gunicorn -w 1 --threads 4 -b 0.0.0.0:$PORT app:app
"""
import hmac
import json
import math
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from flask import Flask, Response, jsonify, request

app = Flask(__name__)

SAST = timezone(timedelta(hours=2))
PANEL_PIN = os.environ.get("PANEL_PIN", "").strip()
EA_API_KEY = os.environ.get("EA_API_KEY", "").strip()
STATE_FILE = os.environ.get("STATE_FILE", "algod_state.json")
OFFLINE_AFTER = 20  # seconds without a heartbeat before the EA shows as offline

_lock = threading.RLock()
state = {"desired": None, "desiredAt": None}   # desired: "start" | "stop" | None
ea = {}                                         # last accepted EA payload
presence = {"lastSeen": None, "online": False, "lastEnabled": None}
events = deque(maxlen=60)
_fails = {}                                     # panel PIN failures per IP

# Fields the EA is allowed to report (anything else is ignored)
FIELDS = {
    "ea": "s", "version": "s", "symbol": "s", "currency": "s",
    "nyStart": "s", "nyEnd": "s", "asiaStart": "s", "asiaEnd": "s",
    "serverTime": "s",
    "account": "i", "magic": "i", "digits": "i", "openTrades": "i",
    "sessionTrades": "i", "maxTradesPerSession": "i", "maxOpenTrades": "i",
    "maxSpreadPts": "i", "sweepPts": "i", "slBufferPts": "i", "sessionGmt": "i",
    "balance": "f", "equity": "f", "nyHigh": "f", "nyLow": "f",
    "riskPercent": "f", "spreadPts": "f", "unit": "f",
    "enabled": "b", "levelsComplete": "b", "inAsia": "b",
}


# ----------------------------------------------------------------- helpers
def add_event(msg, kind="info"):
    events.appendleft({"t": int(time.time()), "msg": msg, "kind": kind})


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("desired") in ("start", "stop"):
            state["desired"] = data["desired"]
            state["desiredAt"] = data.get("desiredAt")
    except Exception:
        pass


def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception:
        pass


def _same(a, b):
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def client_ip():
    fwd = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return fwd or request.remote_addr or "?"


def panel_gate():
    """None if the request may use the panel API, otherwise an error response."""
    if not PANEL_PIN:
        return None
    ip = client_ip()
    t = time.time()
    recent = [x for x in _fails.get(ip, []) if t - x < 300]
    if len(recent) >= 8:
        _fails[ip] = recent
        return jsonify({"ok": False, "error": "too many attempts"}), 429
    given = request.headers.get("X-Panel-Pin", "")
    if given and _same(given, PANEL_PIN):
        return None
    if given:
        recent.append(t)
    _fails[ip] = recent
    return jsonify({"ok": False, "error": "locked"}), 401


def ea_authorized():
    if not EA_API_KEY:
        return True
    key = request.headers.get("X-API-Key", "").strip()
    if not key:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            key = auth[7:].strip()
    return bool(key) and _same(key, EA_API_KEY)


def _coerce(kind, value):
    if kind == "s":
        return str(value)[:40]
    if kind == "b":
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("not finite")
    return int(number) if kind == "i" else number


def clean_payload(raw):
    out = {}
    if not isinstance(raw, dict):
        return out
    for key, kind in FIELDS.items():
        if key in raw and raw[key] not in (None, ""):
            try:
                out[key] = _coerce(kind, raw[key])
            except (TypeError, ValueError):
                continue
    return out


def refresh_presence():
    last = presence["lastSeen"]
    if presence["online"] and last is not None and time.time() - last > OFFLINE_AFTER:
        presence["online"] = False
        add_event("EA offline \u00b7 no heartbeat", "warn")


def record_heartbeat(payload):
    t = time.time()
    was_online = presence["online"]
    ea.clear()
    ea.update(payload)
    presence["lastSeen"] = t
    presence["online"] = True

    if not was_online:
        label = payload.get("symbol", "EA")
        acct = payload.get("account")
        add_event("EA connected \u00b7 %s%s" % (label, " \u00b7 #%s" % acct if acct else ""), "ok")

    if "enabled" in payload:
        enabled = payload["enabled"]
        if state["desired"] is None:        # adopt the EA's own state on first contact
            state["desired"] = "start" if enabled else "stop"
            state["desiredAt"] = int(t)
            save_state()
        last = presence["lastEnabled"]
        if last is not None and enabled != last:
            add_event("EA is now %s" % ("RUNNING" if enabled else "STOPPED"), "ok")
        presence["lastEnabled"] = enabled


def no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ------------------------------------------------------------ EA endpoints
@app.route("/api/bridge/heartbeat", methods=["GET", "POST"])
@app.route("/api/bridge/command", methods=["GET", "POST"])
def ea_endpoint():
    """The EA posts its status here and reads the command from the reply."""
    if not ea_authorized():
        return no_store(jsonify({"ok": False, "error": "unauthorized"})), 401

    raw = request.get_json(force=True, silent=True) if request.method == "POST" else None
    if not isinstance(raw, dict):
        raw = request.args.to_dict()
    payload = clean_payload(raw)

    with _lock:
        if payload:
            record_heartbeat(payload)
        desired = state["desired"]

    # Keep this reply minimal: the EA scans it for "command" / "enabled" only.
    reply = {"ok": True, "serverTime": datetime.now(SAST).strftime("%Y-%m-%d %H:%M:%S")}
    if desired == "start":
        reply.update({"command": "start", "enabled": True})
    elif desired == "stop":
        reply.update({"command": "stop", "enabled": False})
    return no_store(jsonify(reply))


# ---------------------------------------------------------- panel endpoints
@app.route("/api/status", methods=["GET"])
def api_status():
    blocked = panel_gate()
    if blocked:
        return blocked
    with _lock:
        refresh_presence()
        last = presence["lastSeen"]
        body = {
            "desired": state["desired"],
            "online": presence["online"],
            "lastSeenAgo": None if last is None else max(0, int(time.time() - last)),
            "ea": dict(ea),
            "log": list(events),
            "secured": bool(PANEL_PIN),
        }
    return no_store(jsonify(body))


@app.route("/api/control", methods=["POST"])
def api_control():
    blocked = panel_gate()
    if blocked:
        return blocked
    data = request.get_json(force=True, silent=True) or {}
    cmd = str(data.get("command", "")).strip().lower()
    mapping = {
        "start": "start", "play": "start", "run": "start", "resume": "start",
        "stop": "stop", "pause": "stop", "halt": "stop",
    }
    if cmd not in mapping:
        return jsonify({"ok": False, "error": "command must be start or stop"}), 400
    with _lock:
        state["desired"] = mapping[cmd]
        state["desiredAt"] = int(time.time())
        save_state()
        add_event("%s command issued" % mapping[cmd].upper(), "info")
    return no_store(jsonify({"ok": True, "desired": mapping[cmd]}))


@app.route("/healthz")
def healthz():
    return "ok"


@app.route("/")
def index():
    return no_store(Response(INDEX_HTML, mimetype="text/html"))


load_state()

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#000000">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<title>AlgoD &middot; Control</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23000'/%3E%3Cpath d='M16 6v14' stroke='%23fff' stroke-width='2'/%3E%3Crect x='13' y='12' width='6' height='8' fill='%23d4af37'/%3E%3Cpath d='M7 22h18' stroke='%23d4af37' stroke-width='1.5' stroke-dasharray='3 2'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#000;--s1:#08080b;--s2:#0e0e12;--line:#18181e;--line2:#24242c;
  --tx:#f5f5f6;--mut:#8d8d97;--dim:#585862;
  --gold:#d4af37;--ok:#34d399;--warn:#f5a524;--bad:#ff5d5d;
  --mono:"JetBrains Mono","SF Mono",ui-monospace,Menlo,Consolas,monospace;
  --sans:Inter,-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
[hidden]{display:none!important}
html{background:#000;color-scheme:dark}
body{background:#000;color:var(--tx);font:14px/1.5 var(--sans);-webkit-font-smoothing:antialiased;min-height:100vh;
  padding:calc(14px + env(safe-area-inset-top)) 16px calc(28px + env(safe-area-inset-bottom));font-feature-settings:"tnum" 1}
.wrap{max-width:1040px;margin:0 auto;display:flex;flex-direction:column;gap:16px}

/* top bar */
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:2px 2px 14px;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:12px}
.mark{width:34px;height:34px;flex:none}
.wm{font:600 17px var(--sans);letter-spacing:.3em}
.wm b{color:var(--gold);font-weight:600}
.tag{font:500 9.5px var(--sans);letter-spacing:.26em;color:var(--dim);margin-top:2px}
.top-r{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.conn{display:flex;align-items:center;gap:8px;font:600 10.5px var(--sans);letter-spacing:.12em;color:var(--mut);padding:6px 12px;border:1px solid var(--line2);border-radius:999px;background:var(--s1)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--dim);display:inline-block;flex:none}
.conn.ok{color:var(--ok);border-color:rgba(52,211,153,.35)}
.conn.ok .dot{background:var(--ok);animation:ping 2s infinite}
.conn.bad{color:var(--bad);border-color:rgba(255,93,93,.35)}
.conn.bad .dot{background:var(--bad)}
.clock{font:500 13px var(--mono);color:var(--tx);display:flex;align-items:baseline;gap:6px}
.clock em{font:600 9.5px var(--sans);font-style:normal;letter-spacing:.14em;color:var(--dim)}
@media(max-width:600px){.top-r{width:100%;justify-content:space-between}}
@keyframes ping{0%{box-shadow:0 0 0 0 rgba(52,211,153,.55)}70%{box-shadow:0 0 0 7px rgba(52,211,153,0)}100%{box-shadow:0 0 0 0 rgba(52,211,153,0)}}

/* layout */
.grid{display:grid;gap:16px;grid-template-columns:minmax(0,1fr);grid-template-areas:"hero" "levels" "account" "session" "params" "log"}
@media(min-width:880px){.grid{grid-template-columns:minmax(0,340px) minmax(0,1fr);grid-template-areas:"hero levels" "hero account" "session session" "params log"}}
.a-hero{grid-area:hero}.a-levels{grid-area:levels}.a-account{grid-area:account}.a-session{grid-area:session}.a-params{grid-area:params}.a-log{grid-area:log}

.card{background:linear-gradient(180deg,var(--s2),var(--s1));border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:inset 0 1px 0 rgba(255,255,255,.035)}
.row-h{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px}
.lbl{font:600 10.5px var(--sans);letter-spacing:.18em;color:var(--dim);text-transform:uppercase}
.lbl em{font-style:normal;color:var(--mut);margin-left:6px;letter-spacing:.1em}

.chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border:1px solid var(--line2);border-radius:999px;font:600 10px var(--sans);letter-spacing:.12em;color:var(--mut);white-space:nowrap}
.chip.ok{color:var(--ok);border-color:rgba(52,211,153,.35);background:rgba(52,211,153,.06)}
.chip.warn{color:var(--warn);border-color:rgba(245,165,36,.35);background:rgba(245,165,36,.06)}
.chip.bad{color:var(--bad);border-color:rgba(255,93,93,.35);background:rgba(255,93,93,.06)}

/* engine */
.hero{display:flex;flex-direction:column;align-items:stretch;justify-content:center}
.hero .lbl{align-self:flex-start}
.power-wrap{position:relative;width:184px;height:184px;margin:10px auto 6px}
.power{position:absolute;inset:0;width:100%;height:100%;border-radius:50%;border:0;background:radial-gradient(circle at 50% 30%,#13131a,#050507 70%);
  display:grid;place-items:center;cursor:pointer;outline:none;color:var(--dim);transition:transform .15s,box-shadow .4s,color .3s;-webkit-tap-highlight-color:transparent}
.power:active{transform:scale(.97)}
.power:focus-visible{outline:2px solid var(--gold);outline-offset:4px}
.power .ico{width:48px;height:48px;stroke:currentColor;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.power.on{color:var(--ok);box-shadow:0 0 70px -22px currentColor}
.power.off{color:var(--warn);box-shadow:0 0 70px -26px currentColor}
.ring,.spinner{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible}
.ring circle{fill:none;stroke-width:1.5}
.ring .track{stroke:var(--line2)}
.ring .arc{stroke:currentColor;opacity:.9;color:inherit}
.power-wrap.on{color:var(--ok)}.power-wrap.off{color:var(--warn)}.power-wrap.na{color:var(--dim)}
.spinner{display:none}
.spinner circle{fill:none;stroke:currentColor;stroke-width:3;stroke-linecap:round;stroke-dasharray:64 465}
.power-wrap.pending .spinner{display:block;animation:rot 1.1s linear infinite}
.power-wrap.pending .ring .arc{opacity:.25}
@keyframes rot{to{transform:rotate(360deg)}}
.state{text-align:center;font:600 20px var(--sans);letter-spacing:.2em;margin-top:10px}
.sub{text-align:center;color:var(--mut);font-size:12.5px;min-height:20px;margin-top:4px;padding:0 6px}
.sync{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-top:18px}
.sync div{background:var(--s1);padding:10px 12px;display:flex;flex-direction:column;gap:2px}
.sync span{font:600 9.5px var(--sans);letter-spacing:.16em;color:var(--dim)}
.sync b{font:500 13px var(--mono)}
.hint{text-align:center;font:600 9.5px var(--sans);letter-spacing:.2em;color:var(--dim);margin-top:14px}

/* levels */
.lv-row{display:flex;justify-content:space-between;align-items:flex-end;gap:12px}
.k{font:600 10px var(--sans);letter-spacing:.16em;color:var(--dim)}
.v{font:500 30px/1.15 var(--mono);letter-spacing:-.01em;margin-top:4px}
.trg{text-align:right;display:flex;flex-direction:column;gap:2px}
.trg span{font:600 9.5px var(--sans);letter-spacing:.14em;color:var(--dim)}
.trg b{font:500 13px var(--mono);color:var(--mut)}
.trg.sell b{color:var(--bad)}.trg.buy b{color:var(--ok)}
.lv-mid{display:flex;align-items:center;gap:12px;margin:14px 0;color:var(--dim);font:500 11px var(--mono)}
.lv-mid::before,.lv-mid::after{content:"";flex:1;border-top:1px dashed var(--line2)}

/* account */
.tiles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden}
@media(min-width:560px){.tiles{grid-template-columns:repeat(4,minmax(0,1fr))}}
.tile{background:var(--s1);padding:14px}
.tile .tv{font:500 19px var(--mono);margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pos{color:var(--ok)}.neg{color:var(--bad)}

/* session clock */
.ph{font:500 13px var(--sans);color:var(--mut);margin-bottom:6px}
.tl{position:relative;height:62px;margin-top:6px}
.tl-track{position:absolute;left:0;right:0;top:22px;height:2px;background:var(--line2);border-radius:2px}
.seg{position:absolute;top:15px;height:16px;border-radius:4px}
.seg.ny{background:rgba(255,93,93,.18);border:1px solid rgba(255,93,93,.55)}
.seg.asia{background:rgba(212,175,55,.16);border:1px solid rgba(212,175,55,.6)}
.now{position:absolute;top:6px;height:34px;width:2px;background:#fff;box-shadow:0 0 10px rgba(255,255,255,.7);border-radius:1px;transition:left .9s linear}
.now::after{content:"";position:absolute;top:-4px;left:-3px;width:8px;height:8px;border-radius:50%;background:#fff}
.tick{position:absolute;top:44px;font:500 10px var(--mono);color:var(--dim);transform:translateX(-50%)}
.tick.first{transform:none}.tick.last{transform:translateX(-100%)}
.legend{display:flex;gap:18px;flex-wrap:wrap;margin-top:6px;font:600 10px var(--sans);letter-spacing:.12em;color:var(--mut)}
.legend em{font:500 11px var(--mono);font-style:normal;color:var(--dim);margin-left:6px;letter-spacing:0}
.lg{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:8px;vertical-align:-1px}
.lg.ny{background:rgba(255,93,93,.3);border:1px solid rgba(255,93,93,.7)}
.lg.asia{background:rgba(212,175,55,.3);border:1px solid rgba(212,175,55,.8)}

/* parameters */
.kv{display:flex;justify-content:space-between;align-items:baseline;gap:14px;padding:10px 0;border-bottom:1px solid var(--line)}
.kv:last-child{border-bottom:0;padding-bottom:0}
.kv:first-child{padding-top:0}
.kv span{color:var(--mut);font-size:13px;white-space:nowrap}
.kv b{font:500 12.5px var(--mono);text-align:right}

/* activity */
.log{list-style:none;max-height:300px;overflow:auto;margin:-4px 0}
.ev{display:flex;gap:12px;align-items:baseline;padding:9px 0;border-bottom:1px solid var(--line);font-size:13px}
.ev:last-child{border-bottom:0}
.ev time{font:500 11px var(--mono);color:var(--dim);flex:none}
.ev i{width:6px;height:6px;border-radius:50%;background:var(--dim);flex:none;align-self:center}
.ev.ok i{background:var(--ok)}.ev.warn i{background:var(--warn)}.ev.info i{background:var(--gold)}
.ev.empty{color:var(--dim)}
.log::-webkit-scrollbar{width:6px}.log::-webkit-scrollbar-thumb{background:var(--line2);border-radius:3px}

.foot{text-align:center;color:var(--dim);font-size:11.5px;line-height:1.6;padding:6px 8px 0}
.foot b{color:var(--mut);font-weight:500}

/* PIN gate */
.gate{position:fixed;inset:0;background:#000;z-index:50;display:none;place-items:center;padding:20px}
.gate-card{width:100%;max-width:340px;display:flex;flex-direction:column;gap:14px;align-items:stretch;text-align:center}
.gate-card .brand{justify-content:center;margin-bottom:6px}
.gate-t{color:var(--mut);font-size:13px}
.gate input{background:var(--s1);border:1px solid var(--line2);border-radius:12px;color:var(--tx);padding:14px;font:500 18px var(--mono);letter-spacing:.4em;text-align:center;outline:none}
.gate input:focus{border-color:var(--gold)}
.btn{background:var(--gold);color:#000;border:0;border-radius:12px;padding:14px;font:600 12px var(--sans);letter-spacing:.2em;cursor:pointer}
.gate-err{min-height:18px;color:var(--bad);font-size:12.5px}

@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>
</head>
<body>

<div class="gate" id="gate">
  <form class="gate-card" id="gateForm" autocomplete="off">
    <div class="brand"><div><div class="wm">ALGO<b>D</b></div><div class="tag">RESTRICTED ACCESS</div></div></div>
    <p class="gate-t">Enter your access PIN</p>
    <input id="pin" type="password" inputmode="numeric" autocomplete="current-password" placeholder="&bull;&bull;&bull;&bull;">
    <button class="btn" type="submit">UNLOCK</button>
    <div class="gate-err" id="gateErr"></div>
  </form>
</div>

<div class="wrap">
  <header class="top">
    <div class="brand">
      <svg class="mark" viewBox="0 0 32 32" aria-hidden="true">
        <rect x="1" y="1" width="30" height="30" rx="9" fill="#050507" stroke="#24242c"/>
        <path d="M8 22h16" stroke="#d4af37" stroke-width="1.4" stroke-dasharray="3 2.4"/>
        <path d="M16 6.5v15" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>
        <rect x="13" y="12" width="6" height="8" rx="1" fill="#d4af37"/>
      </svg>
      <div><div class="wm">ALGO<b>D</b></div><div class="tag">ASIA SWEEP ENGINE</div></div>
    </div>
    <div class="top-r">
      <span class="chip warn" id="secChip" hidden>UNSECURED</span>
      <div class="conn" id="conn"><i class="dot"></i><span id="connTxt">CONNECTING</span></div>
      <div class="clock"><span id="clk">--:--:--</span><em id="clkTz">GMT+2</em></div>
    </div>
  </header>

  <main class="grid">
    <section class="card hero a-hero">
      <div class="lbl">Engine</div>
      <div class="power-wrap na" id="pw">
        <svg class="ring" viewBox="0 0 184 184" aria-hidden="true"><circle class="track" cx="92" cy="92" r="88"/><circle class="arc" cx="92" cy="92" r="88"/></svg>
        <button class="power na" id="power" type="button" aria-label="Start or stop the engine">
          <svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2v10"/><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/></svg>
        </button>
        <svg class="spinner" viewBox="0 0 184 184" aria-hidden="true"><circle cx="92" cy="92" r="88"/></svg>
      </div>
      <div class="state" id="state">AWAITING EA</div>
      <div class="sub" id="stateSub">Connect the EA to begin</div>
      <div class="sync">
        <div><span>COMMANDED</span><b id="syCmd">&mdash;</b></div>
        <div><span>EA STATE</span><b id="syEa">&mdash;</b></div>
      </div>
      <div class="hint" id="hint">TAP TO START</div>
    </section>

    <section class="card a-levels">
      <div class="row-h"><div class="lbl">NY liquidity levels</div><span class="chip" id="lvChip">NO DATA</span></div>
      <div class="lv-row">
        <div><div class="k">NY HIGH</div><div class="v" id="nyH">&mdash;</div></div>
        <div class="trg sell"><span>SELL ABOVE</span><b id="trgS">&mdash;</b></div>
      </div>
      <div class="lv-mid"><span id="rng">&mdash;</span></div>
      <div class="lv-row">
        <div><div class="k">NY LOW</div><div class="v" id="nyL">&mdash;</div></div>
        <div class="trg buy"><span>BUY BELOW</span><b id="trgB">&mdash;</b></div>
      </div>
    </section>

    <section class="card a-account">
      <div class="row-h"><div class="lbl">Account<em id="cur"></em></div></div>
      <div class="tiles">
        <div class="tile"><div class="k">BALANCE</div><div class="tv" id="bal">&mdash;</div></div>
        <div class="tile"><div class="k">EQUITY</div><div class="tv" id="eq">&mdash;</div></div>
        <div class="tile"><div class="k">FLOATING P/L</div><div class="tv" id="fl">&mdash;</div></div>
        <div class="tile"><div class="k">OPEN TRADES</div><div class="tv" id="ot">&mdash;</div></div>
      </div>
    </section>

    <section class="card a-session">
      <div class="row-h"><div class="lbl">Session clock</div><span class="chip" id="phChip">STANDBY</span></div>
      <div class="ph" id="phTxt">&mdash;</div>
      <div class="tl" id="tl"><div class="tl-track"></div><div id="segs"></div><div class="now" id="nowm"></div><div id="ticks"></div></div>
      <div class="legend">
        <span><i class="lg ny"></i>NY WINDOW<em id="lgNy">&mdash;</em></span>
        <span><i class="lg asia"></i>ASIA SESSION<em id="lgAs">&mdash;</em></span>
      </div>
    </section>

    <section class="card a-params">
      <div class="row-h"><div class="lbl">Strategy parameters</div></div>
      <div id="kvs"></div>
    </section>

    <section class="card a-log">
      <div class="row-h"><div class="lbl">Activity</div></div>
      <ul class="log" id="log"></ul>
    </section>
  </main>

  <p class="foot"><b>Entries and stop-outs</b> are delivered to Telegram by the EA.<br>Strategy parameters are set in the EA inputs and shown here as reported.</p>
</div>

<script>
(function(){
'use strict';
var $=function(id){return document.getElementById(id);};
var isNum=function(v){return typeof v==='number'&&isFinite(v);};
var DASH='\u2014';
var DEF={nyStart:'20:00',nyEnd:'23:00',asiaStart:'00:00',asiaEnd:'07:00',sessionGmt:2};
var S=null, fetchedAt=0, pin=sessionStorage.getItem('algod_pin')||'', gated=false, lastLog='';

function fmt(n,d){return Number(n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});}
function pad(n){return (n<10?'0':'')+n;}
function ago(s){s=Math.max(0,Math.floor(s));return s<60?s+'s':s<3600?Math.floor(s/60)+'m':Math.floor(s/3600)+'h';}
function dur(m){m=Math.max(0,Math.round(m));var h=Math.floor(m/60),r=m%60;return h?h+'h '+pad(r)+'m':r+'m';}
function mins(hhmm){var p=String(hhmm).split(':');return (parseInt(p[0],10)||0)*60+(parseInt(p[1],10)||0);}
function inWin(m,s,e){if(s===e)return true;return s<e?(m>=s&&m<e):(m>=s||m<e);}
function untilMin(m,t){var d=t-m;return d<=0?d+1440:d;}
function set(id,t){var el=$(id);if(el)el.textContent=t;}
function ea(){return (S&&S.ea)||{};}
function cfg(k){var e=ea();return (e[k]!==undefined&&e[k]!==null)?e[k]:DEF[k];}

/* ---------- network ---------- */
function showGate(msg){gated=true;$('gate').style.display='grid';set('gateErr',msg||'');setTimeout(function(){$('pin').focus();},50);}
function api(path,opts){
  opts=opts||{};
  var h={'Content-Type':'application/json'};
  if(pin)h['X-Panel-Pin']=pin;
  return fetch(path,{method:opts.method||'GET',headers:h,body:opts.body,cache:'no-store'}).then(function(r){
    if(r.status===401){var had=!!pin;pin='';sessionStorage.removeItem('algod_pin');showGate(had?'Incorrect PIN.':'');throw new Error('auth');}
    if(r.status===429){showGate('Too many attempts. Try again in a few minutes.');throw new Error('auth');}
    if(!r.ok)throw new Error('http '+r.status);
    return r.json();
  });
}
function refresh(){
  if(gated)return Promise.resolve();
  return api('/api/status').then(function(d){S=d;fetchedAt=Date.now();render();}).catch(function(err){
    if(err.message!=='auth'){S=null;}
    render();
  });
}
function isRunning(){
  if(!S)return false;
  if(S.desired)return S.desired==='start';
  return !!(S.ea&&S.ea.enabled);
}
function toggle(){
  if(!S)return;
  var next=isRunning()?'stop':'start';
  S.desired=next;render();
  api('/api/control',{method:'POST',body:JSON.stringify({command:next})}).then(refresh).catch(function(){});
}

/* ---------- static builders ---------- */
var kvRefs={};
var KV=[
  ['symbol','Instrument'],['risk','Risk per trade'],['maxopen','Max open trades'],['persess','Max per session'],
  ['spread','Spread / max'],['sweep','Sweep trigger'],['sl','Stop loss'],['tp','Take profit'],
  ['acct','Account'],['magic','Magic'],['ver','EA version'],['hb','Last heartbeat']
];
function buildKv(){
  var box=$('kvs');
  KV.forEach(function(k){
    var row=document.createElement('div');row.className='kv';
    var a=document.createElement('span');a.textContent=k[1];
    var b=document.createElement('b');b.textContent=DASH;
    row.appendChild(a);row.appendChild(b);box.appendChild(row);kvRefs[k[0]]=b;
  });
}
function buildTicks(){
  var box=$('ticks');
  for(var h=0;h<=24;h+=3){
    var t=document.createElement('span');
    t.className='tick'+(h===0?' first':h===24?' last':'');
    t.style.left=(h/24*100)+'%';
    t.textContent=pad(h%24);
    box.appendChild(t);
  }
}
function drawSegs(){
  var box=$('segs');box.textContent='';
  function add(cls,s,e){
    var parts=[];
    if(s===e)parts.push([0,1440]);
    else if(s<e)parts.push([s,e]);
    else{parts.push([s,1440]);parts.push([0,e]);}
    parts.forEach(function(p){
      var d=document.createElement('div');d.className='seg '+cls;
      d.style.left=(p[0]/1440*100)+'%';d.style.width=((p[1]-p[0])/1440*100)+'%';
      box.appendChild(d);
    });
  }
  add('ny',mins(cfg('nyStart')),mins(cfg('nyEnd')));
  add('asia',mins(cfg('asiaStart')),mins(cfg('asiaEnd')));
  set('lgNy',cfg('nyStart')+'\u2013'+cfg('nyEnd'));
  set('lgAs',cfg('asiaStart')+'\u2013'+cfg('asiaEnd'));
}

/* ---------- render ---------- */
var segKey='';
function render(){
  var e=ea(), gmt=cfg('sessionGmt');
  var loc=new Date(Date.now()+gmt*3600000);
  set('clk',loc.toISOString().slice(11,19));
  set('clkTz','GMT'+(gmt>=0?'+':'')+gmt);
  var nowMin=loc.getUTCHours()*60+loc.getUTCMinutes()+loc.getUTCSeconds()/60;

  /* connection pill + security chip */
  var online=!!(S&&S.online), seen=S?S.lastSeenAgo:null;
  var age=(seen===null||seen===undefined)?null:seen+(Date.now()-fetchedAt)/1000;
  var cls='',txt='NO LINK';
  if(S){
    if(online){cls='ok';txt='EA ONLINE \u00b7 '+ago(age);}
    else if(age===null){cls='';txt='AWAITING EA';}
    else{cls='bad';txt='EA OFFLINE \u00b7 '+ago(age);}
  }else{cls='bad';}
  $('conn').className='conn '+cls;set('connTxt',txt);
  $('secChip').hidden=!(S&&S.secured===false);

  /* engine */
  var hasState=!!(S&&(S.desired||(online&&e.enabled!==undefined)));
  var running=isRunning();
  var desired=S?S.desired:null;
  var pending=!!(S&&online&&desired&&e.enabled!==undefined&&e.enabled!==(desired==='start'));
  var c=!hasState?'na':running?'on':'off';
  $('pw').className='power-wrap '+c+(pending?' pending':'');
  $('power').className='power '+c;
  set('state',!hasState?'AWAITING EA':running?'RUNNING':'STOPPED');
  var asiaNow=inWin(nowMin,mins(cfg('asiaStart')),mins(cfg('asiaEnd')));
  var sub;
  if(!S)sub='Cannot reach the control server';
  else if(!hasState)sub='Connect the EA to begin';
  else if(!online)sub=desired?'EA offline \u00b7 command queued':'EA offline';
  else if(pending)sub='Awaiting EA acknowledgement\u2026';
  else if(running)sub=asiaNow?'Armed \u00b7 scanning for NY level sweeps':'Armed \u00b7 waiting for the Asia session';
  else sub='Entries disabled \u00b7 open trades keep their SL / TP';
  set('stateSub',sub);
  set('syCmd',desired?(desired==='start'?'START':'STOP'):DASH);
  set('syEa',!S?DASH:online?(e.enabled===undefined?DASH:(e.enabled?'RUNNING':'STOPPED')):'OFFLINE');
  $('syEa').style.color=(online&&desired&&e.enabled!==undefined)?((e.enabled===(desired==='start'))?'var(--ok)':'var(--warn)'):'';
  set('hint',running?'TAP TO STOP':'TAP TO START');

  /* levels */
  var d=isNum(e.digits)?e.digits:2, unit=isNum(e.unit)&&e.unit>0?e.unit:0;
  var hi=isNum(e.nyHigh)?e.nyHigh:null, lo=isNum(e.nyLow)?e.nyLow:null;
  set('nyH',hi===null?DASH:fmt(hi,d));
  set('nyL',lo===null?DASH:fmt(lo,d));
  var lc='chip',lt='NO DATA';
  if(hi!==null&&lo!==null){if(e.levelsComplete){lc='chip ok';lt='LOCKED';}else{lc='chip warn';lt='BUILDING';}}
  $('lvChip').className=lc;set('lvChip',lt);
  if(hi!==null&&lo!==null){
    var rg=fmt(hi-lo,d)+(unit?'  \u00b7  '+fmt((hi-lo)/unit,0)+' pts':'');
    set('rng','RANGE '+rg);
  }else set('rng','RANGE');
  var sw=isNum(e.sweepPts)?e.sweepPts:null;
  set('trgS',(hi!==null&&unit&&sw!==null)?fmt(hi+sw*unit,d):DASH);
  set('trgB',(lo!==null&&unit&&sw!==null)?fmt(lo-sw*unit,d):DASH);

  /* account */
  set('cur',e.currency?e.currency:'');
  set('bal',isNum(e.balance)?fmt(e.balance,2):DASH);
  set('eq',isNum(e.equity)?fmt(e.equity,2):DASH);
  var fl=$('fl');
  if(isNum(e.balance)&&isNum(e.equity)){
    var f=e.equity-e.balance;fl.textContent=(f>0?'+':'')+fmt(f,2);
    fl.className='tv '+(f>0.005?'pos':f<-0.005?'neg':'');
  }else{fl.textContent=DASH;fl.className='tv';}
  set('ot',isNum(e.openTrades)?String(e.openTrades):DASH);

  /* session clock */
  var key=[cfg('nyStart'),cfg('nyEnd'),cfg('asiaStart'),cfg('asiaEnd')].join('|');
  if(key!==segKey){segKey=key;drawSegs();}
  $('nowm').style.left=(nowMin/1440*100)+'%';
  var nyS=mins(cfg('nyStart')),nyE=mins(cfg('nyEnd')),asS=mins(cfg('asiaStart')),asE=mins(cfg('asiaEnd'));
  var pc='chip',pt='STANDBY',tx;
  if(inWin(nowMin,asS,asE)){
    pc='chip ok';pt='ASIA ACTIVE';
    var st=(online&&e.inAsia&&isNum(e.sessionTrades))?e.sessionTrades:null;
    var mx=isNum(e.maxTradesPerSession)?e.maxTradesPerSession:null;
    tx='Sweep watch live \u00b7 closes in '+dur(untilMin(nowMin,asE))+(st!==null&&mx!==null?' \u00b7 trades '+st+'/'+mx:'');
  }else if(inWin(nowMin,nyS,nyE)){
    pc='chip warn';pt='NY WINDOW';tx='Building NY levels \u00b7 locks in '+dur(untilMin(nowMin,nyE));
  }else{
    tx='Asia session opens in '+dur(untilMin(nowMin,asS));
  }
  $('phChip').className=pc;set('phChip',pt);set('phTxt',tx);

  /* parameters */
  var K=kvRefs;
  function v(x,f){return isNum(x)?f(x):DASH;}
  K.symbol.textContent=e.symbol||DASH;
  K.risk.textContent=v(e.riskPercent,function(x){return fmt(x,2)+'%';});
  K.maxopen.textContent=v(e.maxOpenTrades,String);
  K.persess.textContent=v(e.maxTradesPerSession,String);
  K.spread.textContent=(isNum(e.spreadPts)?fmt(e.spreadPts,1):DASH)+' / '+(isNum(e.maxSpreadPts)?e.maxSpreadPts+' pts':DASH);
  K.spread.style.color=(isNum(e.spreadPts)&&isNum(e.maxSpreadPts)&&e.spreadPts>e.maxSpreadPts)?'var(--bad)':'';
  K.sweep.textContent=v(e.sweepPts,function(x){return '\u2265 '+x+' pts beyond level';});
  K.sl.textContent=v(e.slBufferPts,function(x){return 'Wick extreme + '+x+' pts';});
  K.tp.textContent='Opposite NY level \u00b7 3:1 fallback';
  K.acct.textContent=v(e.account,function(x){return '#'+x;});
  K.magic.textContent=v(e.magic,String);
  K.ver.textContent=e.version?'AlgoD v'+e.version:DASH;
  K.hb.textContent=age===null?DASH:ago(age)+' ago';

  /* activity */
  var lg=(S&&S.log)||[];
  var sig=JSON.stringify(lg)+'|'+gmt;
  if(sig!==lastLog){
    lastLog=sig;
    var ul=$('log');ul.textContent='';
    if(!lg.length){var li=document.createElement('li');li.className='ev empty';li.textContent='No activity yet';ul.appendChild(li);}
    lg.forEach(function(ev){
      var li=document.createElement('li');li.className='ev '+(ev.kind||'info');
      var tm=document.createElement('time');tm.textContent=new Date(ev.t*1000+gmt*3600000).toISOString().slice(11,19);
      var dt=document.createElement('i');
      var ms=document.createElement('span');ms.textContent=ev.msg;
      li.appendChild(tm);li.appendChild(dt);li.appendChild(ms);ul.appendChild(li);
    });
  }
}

/* ---------- init ---------- */
$('power').addEventListener('click',toggle);
$('gateForm').addEventListener('submit',function(ev){
  ev.preventDefault();
  pin=$('pin').value;sessionStorage.setItem('algod_pin',pin);$('pin').value='';
  gated=false;$('gate').style.display='none';refresh();
});
buildKv();buildTicks();render();refresh();
setInterval(refresh,2000);
setInterval(render,1000);
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
