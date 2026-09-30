#!/usr/bin/env python3
"""
ADNRPi — Mini API stats système (JSON)
Endpoint : GET /api/stats
Utilisé par hub.html pour afficher CPU/RAM/disque/uptime en temps réel.
Port : 8079 (derrière nginx /api/stats)
"""
import json
import subprocess
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler


def _cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except Exception:
        return ""


def get_stats():
    # IP locale
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = _cmd("hostname -I | awk '{print $1}'")

    # Charge CPU (1min)
    load = _cmd("cat /proc/loadavg | awk '{print $1}'")
    try:
        load = f"{float(load):.2f}"
    except Exception:
        load = "—"

    # RAM libre
    mem_line = _cmd("free -m | awk 'NR==2{print $4\" MB libre / \"$2\" MB\"}'")

    # Disque / (et /mnt/gitea-usb si monté)
    disk_sd  = _cmd("df -h / | awk 'NR==2{print $4\" libre \"$5\" utilisé\"}'")
    usb_mount = _cmd("mountpoint -q /mnt/gitea-usb && df -h /mnt/gitea-usb | awk 'NR==2{print $4}' || echo ''")
    disk = disk_sd + (f" | USB {usb_mount} libre" if usb_mount else "")

    # Uptime
    uptime_s = _cmd("cat /proc/uptime | awk '{print int($1)}'")
    try:
        s = int(uptime_s)
        h, m = divmod(s // 60, 60)
        d, h = divmod(h, 24)
        uptime = f"{d}j {h:02d}h {m:02d}m" if d else f"{h:02d}h {m:02d}m"
    except Exception:
        uptime = "—"

    # Température CPU (H3)
    temp = _cmd("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try:
        temp = f"{int(temp)//1000}°C"
    except Exception:
        temp = "—"

    return {
        "ip":     ip,
        "load":   f"{load} (temp: {temp})",
        "mem":    mem_line,
        "disk":   disk,
        "uptime": uptime,
    }


class StatsHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass   # silencieux

    def do_GET(self):
        data = json.dumps(get_stats()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", 8079), StatsHandler)
    print("Stats API → http://127.0.0.1:8079")
    srv.serve_forever()
