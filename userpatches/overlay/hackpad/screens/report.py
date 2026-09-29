"""
Analyse les résultats d'un outil et affiche un rapport clair pour débutants.
Chaque finding est : (niveau, message)  niveau = "ok" | "warn" | "crit"
"""
import re
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

# ── Descriptions de ports courants ───────────────────────────────────────────

_PORTS = {
    "21":   ("FTP",        "transfert de fichiers non chiffré",  "warn"),
    "22":   ("SSH",        "accès console à distance",           "warn"),
    "23":   ("Telnet",     "accès console NON chiffré",          "crit"),
    "25":   ("SMTP",       "serveur mail",                       "warn"),
    "53":   ("DNS",        "résolution de noms",                 "ok"),
    "80":   ("HTTP",       "site web non chiffré",               "warn"),
    "110":  ("POP3",       "messagerie non chiffrée",            "crit"),
    "135":  ("RPC",        "service Windows RPC",                "warn"),
    "139":  ("NetBIOS",    "partage réseau Windows",             "warn"),
    "143":  ("IMAP",       "messagerie non chiffrée",            "crit"),
    "443":  ("HTTPS",      "site web chiffré (SSL/TLS)",         "ok"),
    "445":  ("SMB",        "partage de fichiers Windows",        "warn"),
    "3306": ("MySQL",      "base de données exposée",            "crit"),
    "3389": ("RDP",        "bureau à distance Windows",          "warn"),
    "5900": ("VNC",        "bureau à distance VNC",              "warn"),
    "8080": ("HTTP-Alt",   "serveur web alternatif",             "warn"),
    "8443": ("HTTPS-Alt",  "HTTPS alternatif",                   "ok"),
}

_SAFE_PORTS = {"53", "443", "8443"}


# ── Analyseurs par outil ──────────────────────────────────────────────────────

def _analyze_nmap(output):
    findings = []
    ports_found = []
    for line in output.splitlines():
        m = re.match(r"\s*(\d+)/tcp\s+open\s+(\S+)", line)
        if m:
            port, svc = m.group(1), m.group(2)
            ports_found.append(port)
            info = _PORTS.get(port)
            if info:
                name, desc, lvl = info
                findings.append((lvl, f"Port {port} ({name}) ouvert — {desc}"))
            else:
                findings.append(("warn", f"Port {port} ({svc}) ouvert — service inconnu"))
    if not findings:
        findings.append(("ok", "Aucun port ouvert trouvé — cible bien filtrée"))
    else:
        crit = [p for p in ports_found if p not in _SAFE_PORTS]
        if crit:
            findings.append(("crit",
                f"⚠ Ports sensibles ouverts : {', '.join(crit)} — vérifier si intentionnel"))
    return findings


def _analyze_hydra(output):
    findings = []
    for line in output.splitlines():
        if "login:" in line and "password:" in line:
            findings.append(("crit", f"Credential trouvé ! → {line.strip()}"))
    if not findings:
        findings.append(("ok", "Aucun credential trouvé — mots de passe dans la liste non valides"))
    return findings


def _analyze_aircrack(output):
    findings = []
    for line in output.splitlines():
        if "KEY FOUND" in line:
            m = re.search(r"KEY FOUND.*?\[\s*(.+?)\s*\]", line)
            key = m.group(1) if m else "?"
            findings.append(("crit", f"Mot de passe WiFi trouvé : {key}"))
        elif "failed" in line.lower() or "not in" in line.lower():
            findings.append(("ok", "Mot de passe non trouvé dans cette liste — réseau protégé"))
    if not findings:
        findings.append(("ok", "Analyse terminée — aucun résultat notable"))
    return findings


def _analyze_gobuster(output):
    findings = []
    for line in output.splitlines():
        m = re.search(r"/([\w./\-]+)\s+\(Status:\s*(\d+)\)", line)
        if m:
            path, code = m.group(1), m.group(2)
            lvl = "crit" if code in ("200", "301", "302") else "ok"
            findings.append((lvl, f"/{path} → HTTP {code}"))
    if not findings:
        findings.append(("ok", "Aucun répertoire/fichier caché trouvé"))
    else:
        findings.insert(0, ("warn",
            f"{len(findings)} chemins trouvés — analyser les codes 200/301"))
    return findings


def _analyze_nikto(output):
    findings = []
    for line in output.splitlines():
        if line.startswith("+ ") and ("OSVDB" in line or "CVE" in line or "vuln" in line.lower()):
            findings.append(("crit", line[2:].strip()))
        elif line.startswith("+ "):
            findings.append(("warn", line[2:].strip()))
    if not findings:
        findings.append(("ok", "Aucune vulnérabilité évidente détectée par Nikto"))
    return findings


def _analyze_hashid(output):
    findings = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("[+]"):
            findings.append(("warn", f"Hash identifié : {line[3:].strip()}"))
    if not findings:
        findings.append(("ok", "Type de hash non reconnu"))
    return findings


def _analyze_arp(output):
    findings = []
    count = 0
    for line in output.splitlines():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
        if m and "Address" not in line:
            count += 1
            findings.append(("warn", f"Hôte actif : {m.group(1)}"))
    if count == 0:
        findings.append(("ok", "Aucun hôte trouvé sur le réseau local"))
    else:
        findings.insert(0, ("warn", f"{count} appareil(s) détecté(s) sur le réseau"))
    return findings


def _analyze_john(output):
    findings = []
    for line in output.splitlines():
        if "(" in line and ")" in line and not line.startswith("#"):
            m = re.search(r"(.+?)\s+\((.+?)\)", line)
            if m:
                pwd, user = m.group(1).strip(), m.group(2).strip()
                findings.append(("crit", f"Mot de passe cassé — {user} : {pwd}"))
    if not findings:
        findings.append(("ok", "Aucun mot de passe cassé avec cette liste"))
    return findings


def _analyze_sqlmap(output):
    findings = []
    for line in output.splitlines():
        if "injectable" in line.lower() and "parameter" in line.lower():
            findings.append(("crit", f"Injection SQL possible ! → {line.strip()}"))
        elif "database" in line.lower() and ":" in line:
            findings.append(("warn", line.strip()))
    if not findings:
        findings.append(("ok", "Aucune injection SQL détectée sur cette cible"))
    return findings


# Mapping tool name → analyzer function
ANALYZERS = {
    "nmap quick":    _analyze_nmap,
    "nmap full":     _analyze_nmap,
    "nmap os":       _analyze_nmap,
    "nmap vuln":     _analyze_nmap,
    "nmap script":   _analyze_nmap,
    "masscan":       _analyze_nmap,
    "hydra ssh":     _analyze_hydra,
    "hydra ftp":     _analyze_hydra,
    "hydra http":    _analyze_hydra,
    "john":          _analyze_john,
    "aircrack-ng":   _analyze_aircrack,
    "gobuster dir":  _analyze_gobuster,
    "gobuster dns":  _analyze_gobuster,
    "nikto":         _analyze_nikto,
    "hashid":        _analyze_hashid,
    "arp-scan":      _analyze_arp,
    "netdiscover":   _analyze_arp,
    "sqlmap":        _analyze_sqlmap,
}


# ── Popup Rapport ─────────────────────────────────────────────────────────────

_COLORS = {
    "ok":   (0.20, 0.75, 0.20, 1),
    "warn": (0.95, 0.75, 0.10, 1),
    "crit": (0.95, 0.25, 0.10, 1),
}
_ICONS = {"ok": "✓", "warn": "⚠", "crit": "✗"}


class ReportPopup(Popup):
    def __init__(self, tool_name, output_text, **kwargs):
        super().__init__(
            title=f"Rapport — {tool_name}",
            size_hint=(0.97, 0.88),
            auto_dismiss=False,
            **kwargs
        )

        analyzer = ANALYZERS.get(tool_name.lower())
        if analyzer:
            try:
                findings = analyzer(output_text)
            except Exception as e:
                findings = [("warn", f"Erreur d'analyse : {e}")]
        else:
            findings = [("ok", "Outil exécuté — consulter la sortie brute ci-dessus")]

        root = BoxLayout(orientation="vertical", spacing=6, padding=8)

        # ── Liste des findings ────────────────────────────────────────────────
        grid = GridLayout(cols=1, spacing=4, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        for lvl, msg in findings:
            color = _COLORS.get(lvl, _COLORS["ok"])
            icon = _ICONS.get(lvl, "•")
            row = BoxLayout(
                size_hint_y=None, height=52, spacing=6,
                padding=(6, 4)
            )
            from kivy.graphics import Color, RoundedRectangle
            bg_col = (color[0]*0.15, color[1]*0.15, color[2]*0.15, 1)
            with row.canvas.before:
                Color(*bg_col)
                rr = RoundedRectangle(pos=row.pos, size=row.size, radius=[6])
            row.bind(pos=lambda w, v, r=rr: setattr(r, "pos", v),
                     size=lambda w, v, r=rr: setattr(r, "size", v))

            row.add_widget(Label(
                text=f"[b]{icon}[/b]", markup=True,
                color=color, size_hint=(None, 1), width=28, halign="center"
            ))
            lbl = Label(
                text=msg, font_size="12sp", color=(0.9, 0.9, 0.9, 1),
                halign="left", valign="middle", text_size=(None, None)
            )
            lbl.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
            row.add_widget(lbl)
            grid.add_widget(row)

        sv = ScrollView()
        sv.add_widget(grid)

        btn_close = Button(
            text="Fermer", font_size="15sp",
            size_hint_y=None, height=44,
            background_color=(0.25, 0.25, 0.25, 1), background_normal=""
        )
        btn_close.bind(on_press=self.dismiss)

        root.add_widget(sv)
        root.add_widget(btn_close)
        self.content = root
