# ADNRPi Scope — Suivi de projet

Outil de mesure tactile pour SmartPi One (Allwinner H3, 1GB RAM, Armbian Bookworm).  
Écran 5 pouces 800×480, interface Kivy, même socle que HackPad.

**Démarré :** 2026-09-29  
**Dernière mise à jour :** 2026-09-30  
**État :** Fonctionnel — oscilloscope, multimètre, I2C, UART, navigation multi-écrans

---

## Hardware SmartPi One — ce qui existe

| Interface | Disponibilité | Notes |
|-----------|--------------|-------|
| GPIO 40 pins | Numérique uniquement | Pas d'ADC intégré sur H3 |
| I2C-0 (`/dev/i2c-0`) | **Actif** ✓ | Pin 3 (SDA/GPIOA12) + Pin 5 (SCL/GPIOA11) |
| I2C-1 | Disponible via overlay | Pin 27 (SDA/GPIOA19) + Pin 28 (SCL/GPIOA18) |
| SPI-0 | Inactif (overlay absent) | Pin 19/21/23/24 — à activer |
| UART | Disponibles | Pins 8/10 (UART1), 11/22 (UART2), etc. |
| Microphone embarqué | **Actif** ✓ | Codec `sun8i_codec_analog` + overlay activé depuis build |
| Sortie 3.5mm A/V | Sortie seulement | Composite video + audio out |
| USB 2.0 (×3) | Actif | Pour Pi Pico ou USB audio |
| Micro USB OTG | Actif | Gadget NCM (172.22.1.1) |

---

## Pinout GPIO utile pour mesure

```
Pin  3  SDA  / I2C-0 / GPIOA12  ← INA219 SDA, ADS1115 SDA
Pin  5  SCL  / I2C-0 / GPIOA11  ← INA219 SCL, ADS1115 SCL
Pin  1  3.3V                     ← alimentation capteurs I2C
Pin  2  5V                       ← alimentation si besoin
Pin  6  GND
Pin 19  SPI0_MOSI / GPIOC0 (64) ← MCP3208 SI  (quand SPI activé)
Pin 21  SPI0_MISO / GPIOC1 (65) ← MCP3208 SO
Pin 23  SPI0_CLK  / GPIOC2 (66) ← MCP3208 CLK
Pin 24  SPI0_CS   / GPIOC3 (67) ← MCP3208 /CS
```

---

## Backends disponibles (par ordre de priorité automatique)

### 1. Pi Pico USB serial — `/dev/ttyACM0` (prévu)
| Spec | Valeur |
|------|--------|
| Résolution | 12-bit (0–4095) |
| Plage | 0–3.3V DC |
| Fréquence max | ~50kHz pratique via USB serial |
| Canaux | 3 (ADC0=GP26, ADC1=GP27, ADC2=GP28) |
| Protocole | `S,<val12bit>\n` via serial 115200 |

Firmware MicroPython Pico :
```python
from machine import ADC, Pin
import sys, utime
adc = ADC(Pin(26))
while True:
    sys.stdout.write(f"S,{adc.read_u16() >> 4}\n")  # 12-bit
    utime.sleep_us(20)   # ~50kHz max
```

---

### 2. INA219 via I2C-0 — **disponible** ✓ (composant en stock)
| Spec | Valeur |
|------|--------|
| Mesures | Tension bus (0–26V), courant shunt, puissance |
| Résolution | 12-bit, précision ±0.1% |
| Vitesse | 1–2 SPS en mode continu sur I2C |
| Adresse I2C | 0x40 (A0=A1=GND par défaut) |
| Usage | **Mode multimètre** (pas oscilloscope) |

Câblage :
```
INA219 VCC → Pin 1 (3.3V)
INA219 GND → Pin 6
INA219 SDA → Pin 3 (I2C-0 SDA)
INA219 SCL → Pin 5 (I2C-0 SCL)
INA219 IN+ → côté alimentation (+)
INA219 IN- → côté charge (-)
Résistance shunt : 0.1Ω (100mΩ) typique
```

Mode pleine échelle : ±3.2A @ 0.1Ω shunt, tension bus 0–26V.

---

### 3. ADS1115 via I2C-0 (composant à commander — ~2€)
| Spec | Valeur |
|------|--------|
| Résolution | 16-bit |
| Canaux | 4 (AIN0–AIN3) |
| Vitesse max | 860 SPS → fréquence max ~430Hz |
| Plage | Configurable : ±0.256V à ±6.144V |
| Usage | Oscilloscope basse fréquence, capteurs lents |

---

### 4. MCP3208 via SPI-0 (composant à commander — ~2€)
| Spec | Valeur |
|------|--------|
| Résolution | 12-bit |
| Canaux | 8 (single-ended ou 4 différentiels) |
| Vitesse max | 100 ksps @ 3.3V |
| Plage | 0–3.3V |
| Usage | Oscilloscope audio (jusqu'à ~50kHz) |

Nécessite d'activer SPI-0 dans armbianEnv.txt (overlay à créer).

---

### 5. Microphone ALSA — **actif** ✓
| Spec | Valeur |
|------|--------|
| Résolution | 16-bit |
| Vitesse | 44100 SPS → jusqu'à ~22kHz |
| Plage | Signal AC uniquement (couplage capacitif) |
| État | **Actif** — overlay DT `sun8i-h3-analog-codec` ajouté dans build |

---

### 6. DummyCapture — signal synthétique (test UI)
Signal 440Hz + 1320Hz, bruit aléatoire. Utilisé quand aucun backend hardware n'est disponible.

---

## Architecture logicielle

```
/opt/adnrpi-scope/
├── main.py              — Config Kivy (800×480, borderless), ScreenManager
├── scope_screen.py      — Oscilloscope : waveform, mesures, contrôles, FFT, persistence
├── meter_screen.py      — Multimètre INA219 : V/A/W, min/max, compteur Wh
├── i2c_screen.py        — Scanner I2C-0/I2C-1, grille 0x00-0x7F, noms composants
├── uart_screen.py       — Terminal UART : port/baud cycle, hex mode, scroll
├── settings_screen.py   — Réglages : source, shunt, offset, thème, langue
├── nav_menu.py          — Popup navigation partagé entre tous les écrans
├── audio_capture.py     — Backends : Pico, INA219, ADS1115, MIC, Dummy
├── settings_manager.py  — Persistance JSON + palettes couleurs + langue
├── strings.py           — Traductions FR/EN
└── launch.sh            — Xrandr + python3
```

**Navigation :** Bouton `[Menu]` dans chaque écran ouvre une popup modale (ModalView)
avec les 5 destinations. L'écran courant est grisé/désactivé dans le menu.

**Kivy layout 800×480 :**
```
┌──────────────────────────────────────────────────────┬──────────────┐ 46px header
│ [* MIC] AUTO  ^ RISE  5ms/div  1V/div  DC  [mode]  [■ STOP]       │
├──────────────────────────────────────────────────────┤   T/div      │
│                                                      │   V/div      │
│         Waveform + grille 10×8 (Canvas)              │   Trigger    │
│         Ligne trigger jaune (ajustable)              │   Slope      │
│         Zone geste gauche = V-offset                 │   Mode       │
│         Zone geste droite = trigger                  │   Coupling   │
│                                                      │   Options    │
├──────────────────────────────────────────────────────┤  [Menu]      │ 160px panel
│ Vmax  Vmin  Vpp   Vrms  Mean                         │  [< Quit]    │
│ Freq  Period Duty  Trig  SIM/kS/s                    │              │ 54px mesures
└──────────────────────────────────────────────────────┴──────────────┘
```

---

## État d'avancement (2026-09-30)

| Tâche | État |
|-------|------|
| UI Kivy (scope_screen.py) | ✓ **Validé** — layout 800×480 OK |
| Backend DummyCapture | ✓ Codé |
| Backend AudioCapture (ALSA) | ✓ **Validé** — CH: MIC actif |
| Backend ADS1115 (I2C) | ✓ Codé (composant à commander ~2€) |
| Backend PicoCapture (USB) | ✓ Codé (Pico non connecté) |
| Backend MCP3208 (SPI) | ⬜ À coder (SPI à activer + composant ~2€) |
| Mode multimètre INA219 | ✓ **Validé** — V/A/W/Wh, min/max, shunt sélectionnable |
| Compteur Wh INA219 (M3) | ✓ **Codé** — intégration P×dt, reset bouton RST |
| Sélecteur source oscillo | ✓ **Validé** — bouton cycle * MIC/PICO/SIM |
| Source PICO dynamique (B2) | ✓ **Codé** — PICO toujours visible, désactivé si absent |
| Affichage SIM au lieu kS/s (B3) | ✓ **Codé** — barre mesures affiche "SIM" |
| Gestes tactile (T/div, trigger, V-offset) | ✓ **Validé** — direction-lock single-touch |
| Buffer STOP + navigation | ✓ **Validé** — glisser H en mode STOP |
| FFT/Spectre (M1) | ✓ **Codé** — dB scale, barres colorées, fond bleu, marqueur pic |
| Persistance waveform (M2) | ✓ **Codé** — 8 sweeps fondu alpha, fond violet |
| Bouton Vue cycle (NORM/FFT/PST) | ✓ **Codé** — 1 bouton, 3 modes, couleurs distinctes |
| Écran Settings | ✓ **Validé** — source, shunt, offset, thème, langue |
| Langue FR/EN (nouveau) | ✓ **Codé** — strings.py, redémarrage sur changement |
| I2C Scanner (R3) | ✓ **Validé** — scan auto + noms connus + grille 16×8 |
| UART Monitor (M4) | ✓ **Codé** — port/baud cycle, hex mode, scroll, /dev/ttyACM0 |
| Navigation multi-écrans (nav_menu) | ✓ **Validé** — popup [Menu] dans tous les écrans |
| Suppression bouton [S] doublon | ✓ **Nettoyé** — navigation via [Menu] uniquement |
| ADNRPi Scope comme app séparée | ✓ **Validé** — indépendant de HackPad |
| Micro-lanceur boot (Scope/HackPad/Eteindre) | ✓ **Validé** — startup-app sauvegardé |
| Service systemd adnrpi-launcher | ✓ **Validé** — remplace adnrpi-hackpad.service |
| Fix codec audio H3 (overlay DT) | ✓ **Validé** (2026-09-29) |
| Intégration dans build GitHub | ⬜ Après validation complète sur carte |

---

## Backlog restant

### Infrastructure
| # | Tâche | Notes |
|---|-------|-------|
| R1 | **Thèmes Blue/HiContrast** | Palettes codées dans settings_manager mais scope+meter utilisent toujours les couleurs hardcodées |
| R2 | **< Quitter → lanceur** | Écrit `/tmp/adnrpi-next = launcher`, fonctionne si lanceur installé |

### Hardware (nécessite composants)
| # | Tâche | Notes |
|---|-------|-------|
| H1 | **Backend MCP3208 SPI** | ~2€, activer SPI-0 + overlay armbianEnv.txt |
| H2 | **ADS1115 réel** | ~2€, déjà codé, à tester avec composant physique |

### Gros (nécessite Pico)
| # | Tâche | Notes |
|---|-------|-------|
| P1 | **Analyseur logique 8 voies** | Firmware MicroPython Pico + chronogramme UI |
| P2 | **Générateur de signaux** | Pico PWM + filtre RC, freq/forme/amplitude depuis UI |

### Roadmap étendue
| Phase | Mode | Description |
|-------|------|-------------|
| V1 | Oscilloscope + Multimètre | **Fait** |
| V2 | Analyseur logique | Nécessite Pico |
| V3 | Générateur de signaux | Nécessite Pico |
| V4 | Analyseur de puissance | Extension INA219 (Wh déjà codé) |
| V5 | Mode Robot Debug | PWM moteurs + courant + encodeurs + IMU |

---

## Commandes utiles sur le SmartPi

```bash
# Lancer le scope manuellement
rm -f /tmp/.X0-lock; xinit /opt/adnrpi-scope/launch.sh -- :0 vt1 -nolisten tcp

# Logs en direct
tail -f /tmp/scope.log

# Arrêter
killall xinit

# Vérifier I2C
i2cdetect -y 0   # scan I2C-0 (doit voir 0x40 si INA219 branché)

# SSH deploy (depuis Windows)
pscp -pw pi scripts/scope/*.py root@192.168.1.89:/opt/adnrpi-scope/
plink -batch -pw pi root@192.168.1.89 "kill PID; DISPLAY=:0 nohup python3 /opt/adnrpi-scope/main.py > /tmp/scope.log 2>&1 &"
```

---

## Activation micro H3 dans le build GitHub

**✓ Résolu le 2026-09-29** — Le `.dtbo` `sun8i-h3-analog-codec` est déjà fourni par Armbian.

### Ce qui a été ajouté dans `userpatches/customize-image.sh`

```bash
# Dans la fonction installHackPad() — en fin de fonction
if grep -q "^overlay_prefix=sun8i-h3" /boot/armbianEnv.txt; then
    if ! grep -q "analog-codec" /boot/armbianEnv.txt; then
        sed -i '/^overlay_prefix=sun8i-h3/a overlays=analog-codec' /boot/armbianEnv.txt
    fi
fi
amixer -c 0 cset numid=18 1   # Mic1 Capture Switch → on
amixer -c 0 cset numid=8  3   # Mic1 Boost → 27dB
amixer -c 0 cset numid=9  7   # ADC Gain → max
amixer -c 0 cset numid=15 1   # Mixer Capture Switch → on
alsactl store 0                # → /var/lib/alsa/asound.state (persiste au reboot)
```
