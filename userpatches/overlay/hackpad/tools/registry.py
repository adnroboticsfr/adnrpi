"""
Central tool registry.
Each tool:
  name       display name
  desc       one-line description shown in tool header
  params     list of {key, label, default, hint, password}
  build_cmd  function(params) -> list[str]

Params with empty default get pre-filled from /etc/adnrpi-hackpad/settings.conf:
  key "target" / "host"  <- target_ip
  key "iface"            <- interface
  key "wordlist"         <- wordlist
  key "output"           <- output_dir/<toolname>
"""

# ── Network Scan ──────────────────────────────────────────────────────────────

NETWORK_TOOLS = [
    {
        "name": "Ping",
        "desc": "Test connectivity to host",
        "params": [
            {"key": "target", "label": "Target IP/host", "default": "192.168.1.1", "hint": "192.168.1.1"},
            {"key": "count",  "label": "Count",          "default": "4",           "hint": "paquets"},
        ],
        "build_cmd": lambda p: ["ping", "-c", p["count"], p["target"]],
    },
    {
        "name": "ARP-Scan LAN",
        "desc": "Discover all devices on LAN",
        "params": [
            {"key": "iface", "label": "Interface", "default": "", "hint": "eth0 / wlan0"},
        ],
        "build_cmd": lambda p: ["arp-scan", "--interface", p["iface"], "--localnet"],
    },
    {
        "name": "ARP Table",
        "desc": "Show known hosts (arp -a)",
        "params": [],
        "build_cmd": lambda p: ["arp", "-a"],
    },
    {
        "name": "Nmap Quick",
        "desc": "Scan rapide TCP (top 100 ports)",
        "params": [
            {"key": "target", "label": "Target IP/range", "default": "", "hint": "192.168.1.0/24"},
        ],
        "build_cmd": lambda p: ["nmap", "-T4", "-F", p["target"]],
    },
    {
        "name": "Nmap Full",
        "desc": "All ports + service/version detection",
        "params": [
            {"key": "target", "label": "Target IP", "default": "", "hint": "192.168.1.1"},
        ],
        "build_cmd": lambda p: ["nmap", "-sV", "-p-", "--open", p["target"]],
    },
    {
        "name": "Nmap OS Detect",
        "desc": "OS fingerprinting (root requis)",
        "params": [
            {"key": "target", "label": "Target IP", "default": "", "hint": ""},
        ],
        "build_cmd": lambda p: ["nmap", "-O", "-sV", p["target"]],
    },
    {
        "name": "Nmap Vuln",
        "desc": "Scripts NSE de détection de vulnérabilités",
        "params": [
            {"key": "target", "label": "Target IP", "default": "", "hint": ""},
        ],
        "build_cmd": lambda p: ["nmap", "--script=vuln", p["target"]],
    },
    {
        "name": "Nmap Script",
        "desc": "Lancer un script NSE spécifique",
        "params": [
            {"key": "target", "label": "Target",  "default": "", "hint": ""},
            {"key": "script", "label": "Script",  "default": "http-title", "hint": "smb-vuln-ms17-010"},
        ],
        "build_cmd": lambda p: ["nmap", f"--script={p['script']}", p["target"]],
    },
    {
        "name": "Masscan",
        "desc": "Scan ultra-rapide (tous ports)",
        "params": [
            {"key": "target", "label": "Target range", "default": "", "hint": "192.168.1.0/24"},
            {"key": "ports",  "label": "Ports",        "default": "1-65535", "hint": ""},
            {"key": "rate",   "label": "Rate (pkt/s)", "default": "500",     "hint": ""},
        ],
        "build_cmd": lambda p: ["masscan", p["target"], "-p", p["ports"], "--rate", p["rate"]],
    },
    {
        "name": "Traceroute",
        "desc": "Chemin réseau vers la cible",
        "params": [
            {"key": "target", "label": "Target", "default": "", "hint": "host or IP"},
        ],
        "build_cmd": lambda p: ["traceroute", p["target"]],
    },
    {
        "name": "Netdiscover",
        "desc": "ARP host discovery (passif possible)",
        "params": [
            {"key": "range", "label": "IP range", "default": "", "hint": "192.168.1.0/24"},
        ],
        "build_cmd": lambda p: ["netdiscover", "-r", p["range"], "-P"],
    },
    {
        "name": "Port Check",
        "desc": "Vérifier si un port est ouvert",
        "params": [
            {"key": "target", "label": "Target IP", "default": "", "hint": ""},
            {"key": "port",   "label": "Port",      "default": "80", "hint": "22 80 443"},
        ],
        "build_cmd": lambda p: ["nc", "-zv", "-w", "3", p["target"], p["port"]],
    },
]

# ── WiFi Attack ───────────────────────────────────────────────────────────────
# Workflow: 1) Airmon Start → 2) Airodump scan → 3) Airodump capture →
#           4) Aireplay deauth → 5) Aircrack → 6) Airmon Stop

WIFI_TOOLS = [
    {
        "name": "1. Airmon Start",
        "desc": "Tuer processus conflictuels + activer monitor",
        "params": [
            {"key": "iface", "label": "Interface WiFi", "default": "wlx40a5ef1333f3", "hint": "wlan0 / wlx..."},
        ],
        "build_cmd": lambda p: [
            "bash", "-c",
            f"airmon-ng check kill && airmon-ng start {p['iface']}"
        ],
    },
    {
        "name": "2. Airodump Scan",
        "desc": "Scanner les réseaux WiFi visibles",
        "params": [
            {"key": "iface",   "label": "Interface monitor", "default": "wlx40a5ef1333f3", "hint": "wlan0mon"},
            {"key": "channel", "label": "Channel",           "default": "",                   "hint": "vide = tous"},
        ],
        "build_cmd": lambda p: (
            ["airodump-ng", p["iface"], "--channel", p["channel"]]
            if p["channel"] else ["airodump-ng", p["iface"]]
        ),
    },
    {
        "name": "3. Airodump Capture",
        "desc": "Capturer le handshake WPA",
        "params": [
            {"key": "iface",   "label": "Interface monitor",  "default": "wlx40a5ef1333f3", "hint": ""},
            {"key": "bssid",   "label": "BSSID (AP)",         "default": "",                   "hint": "AA:BB:CC:DD:EE:FF"},
            {"key": "channel", "label": "Channel",            "default": "6",                  "hint": ""},
            {"key": "output",  "label": "Fichier sortie",     "default": "/tmp/cap",           "hint": "/tmp/cap"},
        ],
        "build_cmd": lambda p: [
            "airodump-ng", p["iface"],
            "--bssid", p["bssid"],
            "--channel", p["channel"],
            "--write", p["output"],
        ],
    },
    {
        "name": "4. Aireplay Deauth",
        "desc": "Forcer reconnexion client (handshake)",
        "params": [
            {"key": "iface",  "label": "Interface monitor", "default": "wlx40a5ef1333f3",  "hint": ""},
            {"key": "bssid",  "label": "AP BSSID",          "default": "",                     "hint": ""},
            {"key": "client", "label": "Client MAC",        "default": "FF:FF:FF:FF:FF:FF",    "hint": "FF:FF = broadcast"},
            {"key": "count",  "label": "Paquets",           "default": "10",                   "hint": "0 = infini"},
        ],
        "build_cmd": lambda p: [
            "aireplay-ng", "--deauth", p["count"],
            "-a", p["bssid"], "-c", p["client"], p["iface"]
        ],
    },
    {
        "name": "5. Aircrack WPA",
        "desc": "Cracker le handshake avec wordlist",
        "params": [
            {"key": "cap",      "label": "Fichier .cap", "default": "/tmp/cap-01.cap",               "hint": ""},
            {"key": "wordlist", "label": "Wordlist",     "default": "/usr/share/wordlists/rockyou.txt", "hint": ""},
            {"key": "bssid",    "label": "AP BSSID",     "default": "",                "hint": ""},
        ],
        "build_cmd": lambda p: [
            "aircrack-ng", p["cap"], "-w", p["wordlist"], "-b", p["bssid"]
        ],
    },
    {
        "name": "6. Airmon Stop",
        "desc": "Désactiver le mode monitor",
        "params": [
            {"key": "iface", "label": "Interface monitor", "default": "wlx40a5ef1333f3", "hint": "wlan0mon"},
        ],
        "build_cmd": lambda p: ["airmon-ng", "stop", p["iface"]],
    },
]

# ── Web Audit ─────────────────────────────────────────────────────────────────

WEB_TOOLS = [
    {
        "name": "Curl Headers",
        "desc": "Headers HTTP de la cible (rapide)",
        "params": [
            {"key": "url", "label": "Target URL", "default": "http://", "hint": "http://192.168.1.1"},
        ],
        "build_cmd": lambda p: ["curl", "-I", "-L", "--max-time", "10", p["url"]],
    },
    {
        "name": "Nikto",
        "desc": "Scan de vulnérabilités web",
        "params": [
            {"key": "url", "label": "Target URL", "default": "http://", "hint": ""},
        ],
        "build_cmd": lambda p: ["nikto", "-h", p["url"]],
    },
    {
        "name": "Gobuster Dir",
        "desc": "Brute-force de répertoires",
        "params": [
            {"key": "url",      "label": "Target URL", "default": "http://", "hint": ""},
            {"key": "wordlist", "label": "Wordlist",   "default": "/usr/share/dirb/wordlists/common.txt", "hint": ""},
            {"key": "threads",  "label": "Threads",    "default": "10",  "hint": ""},
        ],
        "build_cmd": lambda p: [
            "gobuster", "dir", "-u", p["url"], "-w", p["wordlist"], "-t", p["threads"]
        ],
    },
    {
        "name": "Gobuster DNS",
        "desc": "Brute-force sous-domaines DNS",
        "params": [
            {"key": "domain",   "label": "Domain",   "default": "", "hint": "example.com"},
            {"key": "wordlist", "label": "Wordlist",  "default": "/usr/share/dirb/wordlists/common.txt", "hint": ""},
        ],
        "build_cmd": lambda p: [
            "gobuster", "dns", "-d", p["domain"], "-w", p["wordlist"]
        ],
    },
    {
        "name": "SQLMap",
        "desc": "Détection injection SQL",
        "params": [
            {"key": "url",   "label": "URL",   "default": "http://", "hint": "URL?param=val"},
            {"key": "level", "label": "Level", "default": "1",      "hint": "1-5"},
            {"key": "risk",  "label": "Risk",  "default": "1",      "hint": "1-3"},
        ],
        "build_cmd": lambda p: [
            "sqlmap", "-u", p["url"], "--level", p["level"], "--risk", p["risk"], "--batch"
        ],
    },
]

# ── Passwords & Hashes ────────────────────────────────────────────────────────

PASSWORD_TOOLS = [
    {
        "name": "HashID",
        "desc": "Identifier le type de hash",
        "params": [
            {"key": "hash", "label": "Hash", "default": "", "hint": "coller le hash ici"},
        ],
        "build_cmd": lambda p: ["hashid", p["hash"]],
    },
    {
        "name": "John the Ripper",
        "desc": "Cracker un fichier de hash",
        "params": [
            {"key": "hashfile", "label": "Fichier hash", "default": "/tmp/hash.txt", "hint": ""},
            {"key": "wordlist", "label": "Wordlist",     "default": "/usr/share/wordlists/rockyou.txt", "hint": "vide = incremental"},
            {"key": "format",   "label": "Format",       "default": "",              "hint": "md5crypt sha512crypt"},
        ],
        "build_cmd": lambda p: (
            ["john", p["hashfile"]]
            + (["--wordlist", p["wordlist"]] if p["wordlist"] else [])
            + (["--format", p["format"]] if p["format"] else [])
        ),
    },
    {
        "name": "Hydra SSH",
        "desc": "Brute-force login SSH",
        "params": [
            {"key": "target",   "label": "Target IP", "default": "",                              "hint": ""},
            {"key": "user",     "label": "Username",  "default": "root",                           "hint": ""},
            {"key": "wordlist", "label": "Wordlist",  "default": "/usr/share/wordlists/rockyou.txt","hint": ""},
            {"key": "threads",  "label": "Threads",   "default": "4",                              "hint": ""},
        ],
        "build_cmd": lambda p: [
            "hydra", "-l", p["user"], "-P", p["wordlist"],
            "-t", p["threads"], p["target"], "ssh"
        ],
    },
    {
        "name": "Hydra FTP",
        "desc": "Brute-force login FTP",
        "params": [
            {"key": "target",   "label": "Target IP", "default": "",                               "hint": ""},
            {"key": "user",     "label": "Username",  "default": "admin",                          "hint": ""},
            {"key": "wordlist", "label": "Wordlist",  "default": "/usr/share/wordlists/rockyou.txt","hint": ""},
        ],
        "build_cmd": lambda p: [
            "hydra", "-l", p["user"], "-P", p["wordlist"], p["target"], "ftp"
        ],
    },
    {
        "name": "Hydra HTTP",
        "desc": "Brute-force formulaire HTTP POST",
        "params": [
            {"key": "target",   "label": "Target IP",   "default": "",                               "hint": ""},
            {"key": "path",     "label": "Login path",  "default": "/login",                         "hint": ""},
            {"key": "user",     "label": "Username",    "default": "admin",                          "hint": ""},
            {"key": "wordlist", "label": "Wordlist",    "default": "/usr/share/wordlists/rockyou.txt","hint": ""},
            {"key": "params",   "label": "POST params", "default": "user=^USER^&pass=^PASS^:F=incorrect", "hint": ""},
        ],
        "build_cmd": lambda p: [
            "hydra", "-l", p["user"], "-P", p["wordlist"],
            p["target"], "http-post-form", f"{p['path']}:{p['params']}"
        ],
    },
    {
        "name": "SMBClient",
        "desc": "Lister les partages SMB",
        "params": [
            {"key": "target", "label": "Target IP", "default": "",    "hint": ""},
            {"key": "user",   "label": "Username",  "default": "guest","hint": ""},
        ],
        "build_cmd": lambda p: [
            "smbclient", "-L", f"//{p['target']}", "-U", p["user"], "-N"
        ],
    },
    {
        "name": "Crunch Wordlist",
        "desc": "Générer une wordlist personnalisée",
        "params": [
            {"key": "min",    "label": "Long. min", "default": "6",    "hint": ""},
            {"key": "max",    "label": "Long. max", "default": "8",    "hint": ""},
            {"key": "chars",  "label": "Charset",   "default": "abcdefghijklmnopqrstuvwxyz0123456789", "hint": ""},
            {"key": "output", "label": "Fichier",   "default": "/tmp/wordlist.txt", "hint": ""},
        ],
        "build_cmd": lambda p: [
            "crunch", p["min"], p["max"], p["chars"], "-o", p["output"]
        ],
    },
]

# ── Recon & OSINT ─────────────────────────────────────────────────────────────

RECON_TOOLS = [
    {
        "name": "Whois",
        "desc": "Infos d'enregistrement domaine",
        "params": [
            {"key": "domain", "label": "Domain", "default": "", "hint": "example.com"},
        ],
        "build_cmd": lambda p: ["whois", p["domain"]],
    },
    {
        "name": "DNS Lookup",
        "desc": "Requête enregistrement DNS",
        "params": [
            {"key": "domain", "label": "Domain",      "default": "",    "hint": "example.com"},
            {"key": "type",   "label": "Record type", "default": "ANY", "hint": "A MX NS TXT"},
        ],
        "build_cmd": lambda p: ["dig", p["type"], p["domain"]],
    },
    {
        "name": "DNSRecon",
        "desc": "Enumération DNS complète",
        "params": [
            {"key": "domain", "label": "Domain", "default": "", "hint": "example.com"},
        ],
        "build_cmd": lambda p: ["dnsrecon", "-d", p["domain"]],
    },
    {
        "name": "Host Lookup",
        "desc": "Résolution DNS inverse d'une IP",
        "params": [
            {"key": "ip", "label": "IP", "default": "", "hint": "192.168.1.1"},
        ],
        "build_cmd": lambda p: ["dig", "-x", p["ip"]],
    },
]

# ── Capture & Analysis ────────────────────────────────────────────────────────

CAPTURE_TOOLS = [
    {
        "name": "TCPDump",
        "desc": "Capture paquets en live",
        "params": [
            {"key": "iface",  "label": "Interface", "default": "", "hint": "eth0 wlan0"},
            {"key": "filter", "label": "Filtre",    "default": "", "hint": "port 80 / host x.x.x.x"},
            {"key": "count",  "label": "Count",     "default": "100", "hint": "0 = infini"},
        ],
        "build_cmd": lambda p: (
            ["tcpdump", "-i", p["iface"], "-c", p["count"], "-nn"]
            + ([p["filter"]] if p["filter"] else [])
        ),
    },
    {
        "name": "Tshark Capture",
        "desc": "Capture vers fichier PCAP",
        "params": [
            {"key": "iface",  "label": "Interface", "default": "", "hint": "eth0"},
            {"key": "count",  "label": "Count",     "default": "100", "hint": ""},
            {"key": "output", "label": "PCAP file", "default": "", "hint": "/tmp/capture.pcap"},
        ],
        "build_cmd": lambda p: [
            "tshark", "-i", p["iface"], "-c", p["count"], "-w", p["output"]
        ],
    },
    {
        "name": "Tshark Read",
        "desc": "Lire et filtrer un fichier PCAP",
        "params": [
            {"key": "file",   "label": "PCAP file", "default": "/tmp/capture.pcap", "hint": ""},
            {"key": "filter", "label": "Filtre",    "default": "",                  "hint": "http dns tcp"},
        ],
        "build_cmd": lambda p: (
            ["tshark", "-r", p["file"]]
            + (["-Y", p["filter"]] if p["filter"] else [])
        ),
    },
    {
        "name": "Netstat Ports",
        "desc": "Ports ouverts locaux",
        "params": [],
        "build_cmd": lambda p: ["ss", "-tulpn"],
    },
    {
        "name": "Ngrep",
        "desc": "Grep sur paquets réseau",
        "params": [
            {"key": "pattern", "label": "Pattern",   "default": "GET",  "hint": "regex"},
            {"key": "iface",   "label": "Interface", "default": "",     "hint": "eth0"},
        ],
        "build_cmd": lambda p: ["ngrep", "-d", p["iface"], p["pattern"]],
    },
    {
        "name": "Netcat Listen",
        "desc": "Ouvrir un port en écoute (reverse shell)",
        "params": [
            {"key": "port", "label": "Port", "default": "4444", "hint": ""},
        ],
        "build_cmd": lambda p: ["nc", "-lvnp", p["port"]],
    },
    {
        "name": "Netcat Connect",
        "desc": "Connexion TCP vers hôte distant",
        "params": [
            {"key": "host", "label": "Host", "default": "", "hint": ""},
            {"key": "port", "label": "Port", "default": "", "hint": ""},
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
