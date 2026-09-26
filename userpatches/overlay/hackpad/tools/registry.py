"""
Central tool registry. Each tool defines:
  name       display name
  desc       one-line description
  params     list of {key, label, default, hint, password}
  build_cmd  function(params) -> list[str]  (the command to run)
"""

# ── Network Scan ──────────────────────────────────────────────────────────────

NETWORK_TOOLS = [
    {
        "name": "Nmap Quick",
        "desc": "Fast TCP port scan",
        "params": [
            {"key": "target", "label": "Target IP/range", "default": "192.168.1.0/24", "hint": "e.g. 192.168.1.1"},
        ],
        "build_cmd": lambda p: ["nmap", "-T4", "-F", p["target"]],
    },
    {
        "name": "Nmap Full",
        "desc": "All ports + service version",
        "params": [
            {"key": "target", "label": "Target IP", "default": "", "hint": "e.g. 192.168.1.1"},
        ],
        "build_cmd": lambda p: ["nmap", "-sV", "-p-", "--open", p["target"]],
    },
    {
        "name": "Nmap OS Detect",
        "desc": "OS fingerprinting (root)",
        "params": [
            {"key": "target", "label": "Target IP", "default": "", "hint": ""},
        ],
        "build_cmd": lambda p: ["nmap", "-O", "-sV", p["target"]],
    },
    {
        "name": "Nmap Vuln",
        "desc": "Run vuln NSE scripts",
        "params": [
            {"key": "target", "label": "Target IP", "default": "", "hint": ""},
        ],
        "build_cmd": lambda p: ["nmap", "--script=vuln", p["target"]],
    },
    {
        "name": "Masscan",
        "desc": "Ultra-fast port scan",
        "params": [
            {"key": "target", "label": "Target range", "default": "192.168.1.0/24", "hint": ""},
            {"key": "ports",  "label": "Ports",         "default": "1-65535",         "hint": ""},
            {"key": "rate",   "label": "Rate (pkt/s)",  "default": "1000",            "hint": ""},
        ],
        "build_cmd": lambda p: ["masscan", p["target"], "-p", p["ports"], "--rate", p["rate"]],
    },
    {
        "name": "Netdiscover",
        "desc": "ARP host discovery",
        "params": [
            {"key": "range", "label": "IP range", "default": "192.168.1.0/24", "hint": ""},
        ],
        "build_cmd": lambda p: ["netdiscover", "-r", p["range"], "-P"],
    },
    {
        "name": "ARP-Scan",
        "desc": "LAN ARP scan",
        "params": [
            {"key": "iface", "label": "Interface", "default": "eth0", "hint": "eth0 / wlan0"},
        ],
        "build_cmd": lambda p: ["arp-scan", "--interface", p["iface"], "--localnet"],
    },
    {
        "name": "Traceroute",
        "desc": "Trace route to host",
        "params": [
            {"key": "target", "label": "Target", "default": "", "hint": "host or IP"},
        ],
        "build_cmd": lambda p: ["traceroute", p["target"]],
    },
]

# ── WiFi Attack ───────────────────────────────────────────────────────────────

WIFI_TOOLS = [
    {
        "name": "Airmon-ng Start",
        "desc": "Enable monitor mode",
        "params": [
            {"key": "iface", "label": "Interface", "default": "wlan0", "hint": ""},
        ],
        "build_cmd": lambda p: ["airmon-ng", "start", p["iface"]],
    },
    {
        "name": "Airmon-ng Stop",
        "desc": "Disable monitor mode",
        "params": [
            {"key": "iface", "label": "Interface", "default": "wlan0mon", "hint": ""},
        ],
        "build_cmd": lambda p: ["airmon-ng", "stop", p["iface"]],
    },
    {
        "name": "Airodump-ng",
        "desc": "Scan WiFi networks",
        "params": [
            {"key": "iface",   "label": "Interface",  "default": "wlan0mon", "hint": ""},
            {"key": "channel", "label": "Channel",    "default": "",         "hint": "blank = all"},
        ],
        "build_cmd": lambda p: (
            ["airodump-ng", p["iface"], "--channel", p["channel"]]
            if p["channel"] else ["airodump-ng", p["iface"]]
        ),
    },
    {
        "name": "Airodump Capture",
        "desc": "Capture handshake to file",
        "params": [
            {"key": "iface",   "label": "Interface",  "default": "wlan0mon", "hint": ""},
            {"key": "bssid",   "label": "BSSID",      "default": "",         "hint": "AP MAC address"},
            {"key": "channel", "label": "Channel",    "default": "6",        "hint": ""},
            {"key": "output",  "label": "Output file","default": "/tmp/cap",  "hint": "prefix only"},
        ],
        "build_cmd": lambda p: [
            "airodump-ng", p["iface"],
            "--bssid", p["bssid"],
            "--channel", p["channel"],
            "--write", p["output"],
        ],
    },
    {
        "name": "Aireplay Deauth",
        "desc": "Deauth clients (force handshake)",
        "params": [
            {"key": "iface",  "label": "Interface", "default": "wlan0mon", "hint": ""},
            {"key": "bssid",  "label": "AP BSSID",  "default": "",         "hint": ""},
            {"key": "client", "label": "Client MAC", "default": "FF:FF:FF:FF:FF:FF", "hint": "FF:FF = broadcast"},
            {"key": "count",  "label": "Packets",   "default": "10",       "hint": "0 = infinite"},
        ],
        "build_cmd": lambda p: [
            "aireplay-ng", "--deauth", p["count"],
            "-a", p["bssid"], "-c", p["client"], p["iface"]
        ],
    },
    {
        "name": "Aircrack WPA",
        "desc": "Crack WPA handshake",
        "params": [
            {"key": "cap",      "label": "Cap file",   "default": "/tmp/cap-01.cap", "hint": ""},
            {"key": "wordlist", "label": "Wordlist",   "default": "/usr/share/wordlists/rockyou.txt", "hint": ""},
            {"key": "bssid",    "label": "AP BSSID",   "default": "",                "hint": ""},
        ],
        "build_cmd": lambda p: [
            "aircrack-ng", p["cap"], "-w", p["wordlist"], "-b", p["bssid"]
        ],
    },
    {
        "name": "Wifite",
        "desc": "Automated WiFi attack",
        "params": [
            {"key": "iface", "label": "Interface", "default": "wlan0", "hint": ""},
        ],
        "build_cmd": lambda p: ["wifite", "--interface", p["iface"], "--kill"],
    },
]

# ── Web Audit ─────────────────────────────────────────────────────────────────

WEB_TOOLS = [
    {
        "name": "Nikto",
        "desc": "Web server vulnerability scan",
        "params": [
            {"key": "url", "label": "Target URL", "default": "http://", "hint": "http://192.168.1.1"},
        ],
        "build_cmd": lambda p: ["nikto", "-h", p["url"]],
    },
    {
        "name": "SQLMap",
        "desc": "SQL injection detection",
        "params": [
            {"key": "url",    "label": "URL",    "default": "http://", "hint": "URL with ?param=value"},
            {"key": "level",  "label": "Level",  "default": "1",      "hint": "1-5"},
            {"key": "risk",   "label": "Risk",   "default": "1",      "hint": "1-3"},
        ],
        "build_cmd": lambda p: [
            "sqlmap", "-u", p["url"], "--level", p["level"], "--risk", p["risk"], "--batch"
        ],
    },
    {
        "name": "Gobuster Dir",
        "desc": "Directory brute-force",
        "params": [
            {"key": "url",      "label": "Target URL", "default": "http://", "hint": ""},
            {"key": "wordlist", "label": "Wordlist",   "default": "/usr/share/wordlists/dirb/common.txt", "hint": ""},
            {"key": "threads",  "label": "Threads",    "default": "10",  "hint": ""},
        ],
        "build_cmd": lambda p: [
            "gobuster", "dir", "-u", p["url"], "-w", p["wordlist"], "-t", p["threads"]
        ],
    },
    {
        "name": "Gobuster DNS",
        "desc": "DNS subdomain brute-force",
        "params": [
            {"key": "domain",   "label": "Domain",   "default": "", "hint": "example.com"},
            {"key": "wordlist", "label": "Wordlist",  "default": "/usr/share/wordlists/dirb/common.txt", "hint": ""},
        ],
        "build_cmd": lambda p: [
            "gobuster", "dns", "-d", p["domain"], "-w", p["wordlist"]
        ],
    },
    {
        "name": "WhatWeb",
        "desc": "Identify web technologies",
        "params": [
            {"key": "url", "label": "Target URL", "default": "http://", "hint": ""},
        ],
        "build_cmd": lambda p: ["whatweb", "-a", "3", p["url"]],
    },
    {
        "name": "Curl Headers",
        "desc": "Show HTTP response headers",
        "params": [
            {"key": "url", "label": "Target URL", "default": "http://", "hint": ""},
        ],
        "build_cmd": lambda p: ["curl", "-I", "-L", "--max-time", "10", p["url"]],
    },
]

# ── Passwords & Hashes ────────────────────────────────────────────────────────

PASSWORD_TOOLS = [
    {
        "name": "Hydra SSH",
        "desc": "Brute-force SSH login",
        "params": [
            {"key": "target",   "label": "Target IP", "default": "",     "hint": ""},
            {"key": "user",     "label": "Username",  "default": "root", "hint": ""},
            {"key": "wordlist", "label": "Wordlist",  "default": "/usr/share/wordlists/rockyou.txt", "hint": ""},
            {"key": "threads",  "label": "Threads",   "default": "4",    "hint": ""},
        ],
        "build_cmd": lambda p: [
            "hydra", "-l", p["user"], "-P", p["wordlist"],
            "-t", p["threads"], p["target"], "ssh"
        ],
    },
    {
        "name": "Hydra HTTP",
        "desc": "Brute-force HTTP form",
        "params": [
            {"key": "target",   "label": "Target IP",    "default": "",        "hint": ""},
            {"key": "path",     "label": "Login path",   "default": "/login",  "hint": ""},
            {"key": "user",     "label": "Username",     "default": "admin",   "hint": ""},
            {"key": "wordlist", "label": "Wordlist",     "default": "/usr/share/wordlists/rockyou.txt", "hint": ""},
            {"key": "params",   "label": "POST params",  "default": "user=^USER^&pass=^PASS^:F=incorrect", "hint": ""},
        ],
        "build_cmd": lambda p: [
            "hydra", "-l", p["user"], "-P", p["wordlist"],
            p["target"], "http-post-form", f"{p['path']}:{p['params']}"
        ],
    },
    {
        "name": "John the Ripper",
        "desc": "Crack password hash file",
        "params": [
            {"key": "hashfile", "label": "Hash file",  "default": "/tmp/hash.txt", "hint": ""},
            {"key": "wordlist", "label": "Wordlist",   "default": "/usr/share/wordlists/rockyou.txt", "hint": "blank = incremental"},
            {"key": "format",   "label": "Format",     "default": "",              "hint": "md5crypt, sha512crypt…"},
        ],
        "build_cmd": lambda p: (
            ["john", p["hashfile"]]
            + (["--wordlist", p["wordlist"]] if p["wordlist"] else [])
            + (["--format", p["format"]] if p["format"] else [])
        ),
    },
    {
        "name": "Hashcat Wordlist",
        "desc": "GPU/CPU hash cracking",
        "params": [
            {"key": "hashfile", "label": "Hash file", "default": "/tmp/hash.txt", "hint": ""},
            {"key": "mode",     "label": "Hash mode",  "default": "0",   "hint": "0=MD5 1800=sha512crypt"},
            {"key": "wordlist", "label": "Wordlist",   "default": "/usr/share/wordlists/rockyou.txt", "hint": ""},
        ],
        "build_cmd": lambda p: [
            "hashcat", "-m", p["mode"], p["hashfile"], p["wordlist"],
            "--force", "--status"
        ],
    },
    {
        "name": "Crunch",
        "desc": "Generate custom wordlist",
        "params": [
            {"key": "min",    "label": "Min length", "default": "6",  "hint": ""},
            {"key": "max",    "label": "Max length", "default": "8",  "hint": ""},
            {"key": "chars",  "label": "Charset",    "default": "abcdefghijklmnopqrstuvwxyz0123456789", "hint": ""},
            {"key": "output", "label": "Output file","default": "/tmp/wordlist.txt", "hint": ""},
        ],
        "build_cmd": lambda p: [
            "crunch", p["min"], p["max"], p["chars"], "-o", p["output"]
        ],
    },
    {
        "name": "Medusa",
        "desc": "Network login brute-force",
        "params": [
            {"key": "target",   "label": "Target IP",  "default": "",      "hint": ""},
            {"key": "user",     "label": "Username",   "default": "admin", "hint": ""},
            {"key": "wordlist", "label": "Wordlist",   "default": "/usr/share/wordlists/rockyou.txt", "hint": ""},
            {"key": "module",   "label": "Module",     "default": "ssh",   "hint": "ssh ftp http smb"},
        ],
        "build_cmd": lambda p: [
            "medusa", "-h", p["target"], "-u", p["user"],
            "-P", p["wordlist"], "-M", p["module"]
        ],
    },
]

# ── Recon & OSINT ─────────────────────────────────────────────────────────────

RECON_TOOLS = [
    {
        "name": "Whois",
        "desc": "Domain registration info",
        "params": [
            {"key": "domain", "label": "Domain", "default": "", "hint": "example.com"},
        ],
        "build_cmd": lambda p: ["whois", p["domain"]],
    },
    {
        "name": "DNS Lookup",
        "desc": "DNS record query",
        "params": [
            {"key": "domain", "label": "Domain",      "default": "",   "hint": "example.com"},
            {"key": "type",   "label": "Record type", "default": "ANY","hint": "A MX NS TXT"},
        ],
        "build_cmd": lambda p: ["dig", p["type"], p["domain"]],
    },
    {
        "name": "DNSRecon",
        "desc": "DNS enumeration",
        "params": [
            {"key": "domain", "label": "Domain", "default": "", "hint": "example.com"},
        ],
        "build_cmd": lambda p: ["dnsrecon", "-d", p["domain"]],
    },
    {
        "name": "Fierce",
        "desc": "DNS subdomain scanner",
        "params": [
            {"key": "domain", "label": "Domain", "default": "", "hint": "example.com"},
        ],
        "build_cmd": lambda p: ["fierce", "--domain", p["domain"]],
    },
    {
        "name": "theHarvester",
        "desc": "Email & subdomain OSINT",
        "params": [
            {"key": "domain", "label": "Domain",  "default": "", "hint": "example.com"},
            {"key": "source", "label": "Source",  "default": "bing", "hint": "bing google duckduckgo"},
            {"key": "limit",  "label": "Limit",   "default": "100",  "hint": ""},
        ],
        "build_cmd": lambda p: [
            "theHarvester", "-d", p["domain"], "-b", p["source"], "-l", p["limit"]
        ],
    },
    {
        "name": "Nmap Script",
        "desc": "Run specific NSE script",
        "params": [
            {"key": "target", "label": "Target",  "default": "",               "hint": ""},
            {"key": "script", "label": "Script",  "default": "http-title",     "hint": ""},
        ],
        "build_cmd": lambda p: ["nmap", f"--script={p['script']}", p["target"]],
    },
]

# ── Capture & Analysis ────────────────────────────────────────────────────────

CAPTURE_TOOLS = [
    {
        "name": "TCPDump",
        "desc": "Live packet capture",
        "params": [
            {"key": "iface",  "label": "Interface", "default": "eth0",  "hint": "eth0 wlan0"},
            {"key": "filter", "label": "Filter",    "default": "",      "hint": "port 80 / host x.x.x.x"},
            {"key": "count",  "label": "Count",     "default": "100",   "hint": "packets (0=infinite)"},
        ],
        "build_cmd": lambda p: (
            ["tcpdump", "-i", p["iface"], "-c", p["count"], "-nn"]
            + ([p["filter"]] if p["filter"] else [])
        ),
    },
    {
        "name": "Tshark Capture",
        "desc": "Wireshark CLI capture",
        "params": [
            {"key": "iface",  "label": "Interface", "default": "eth0", "hint": ""},
            {"key": "count",  "label": "Count",     "default": "50",   "hint": ""},
            {"key": "output", "label": "PCAP file", "default": "/tmp/capture.pcap", "hint": ""},
        ],
        "build_cmd": lambda p: [
            "tshark", "-i", p["iface"], "-c", p["count"], "-w", p["output"]
        ],
    },
    {
        "name": "Tshark Read",
        "desc": "Read & filter PCAP file",
        "params": [
            {"key": "file",   "label": "PCAP file", "default": "/tmp/capture.pcap", "hint": ""},
            {"key": "filter", "label": "Filter",    "default": "",                  "hint": "http / dns / tcp"},
        ],
        "build_cmd": lambda p: (
            ["tshark", "-r", p["file"]]
            + (["-Y", p["filter"]] if p["filter"] else [])
        ),
    },
    {
        "name": "Ngrep",
        "desc": "Grep on network packets",
        "params": [
            {"key": "pattern", "label": "Pattern",   "default": "GET",  "hint": "regex"},
            {"key": "iface",   "label": "Interface", "default": "eth0", "hint": ""},
        ],
        "build_cmd": lambda p: ["ngrep", "-d", p["iface"], p["pattern"]],
    },
    {
        "name": "Responder",
        "desc": "LLMNR/NBT-NS poisoner",
        "params": [
            {"key": "iface", "label": "Interface", "default": "eth0", "hint": ""},
        ],
        "build_cmd": lambda p: ["responder", "-I", p["iface"], "-rdw"],
    },
    {
        "name": "Netcat Listen",
        "desc": "Open listening port",
        "params": [
            {"key": "port", "label": "Port", "default": "4444", "hint": ""},
        ],
        "build_cmd": lambda p: ["nc", "-lvnp", p["port"]],
    },
    {
        "name": "Netcat Connect",
        "desc": "Connect to remote host",
        "params": [
            {"key": "host", "label": "Host", "default": "", "hint": ""},
            {"key": "port", "label": "Port", "default": "",  "hint": ""},
        ],
        "build_cmd": lambda p: ["nc", "-v", p["host"], p["port"]],
    },
]

# ── Registry ──────────────────────────────────────────────────────────────────

TOOLS = {
    "network":   NETWORK_TOOLS,
    "wifi":      WIFI_TOOLS,
    "web":       WEB_TOOLS,
    "passwords": PASSWORD_TOOLS,
    "recon":     RECON_TOOLS,
    "capture":   CAPTURE_TOOLS,
}
