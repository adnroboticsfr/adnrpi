# ADNRPi Scope — Suivi de projet

Outil de mesure tactile pour SmartPi One (Allwinner H3, 1GB RAM, Armbian Bookworm).  
Écran 5 pouces 800×480, interface Kivy, même socle que HackPad.

**Démarré :** 2026-09-29  
**État :** test UI en cours (DummyCapture)

---

## Hardware SmartPi One — ce qui existe

| Interface | Disponibilité | Notes |
|-----------|--------------|-------|
| GPIO 40 pins | Numérique uniquement | Pas d'ADC intégré sur H3 |
| I2C-0 (`/dev/i2c-0`) | **Actif** ✓ | Pin 3 (SDA/GPIOA12) + Pin 5 (SCL/GPIOA11) |
| I2C-1 | Disponible via overlay | Pin 27 (SDA/GPIOA19) + Pin 28 (SCL/GPIOA18) |
| SPI-0 | Inactif (overlay absent) | Pin 19/21/23/24 — à activer |
| UART | Disponibles | Pins 8/10 (UART1), 11/22 (UART2), etc. |
| Microphone embarqué | **Inactif** | Codec `sun8i_codec_analog` builtin mais overlay DT absent |
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

### 5. Microphone ALSA (en attente — fix codec nécessaire)
| Spec | Valeur |
|------|--------|
| Résolution | 16-bit |
| Vitesse | 44100 SPS → jusqu'à ~22kHz |
| Plage | Signal AC uniquement (couplage capacitif) |
| État | Codec `sun8i_codec_analog` builtin mais overlay DT absent |
| Fix | Créer overlay DT pour sun8i-h3 + activer dans armbianEnv.txt |

---

### 6. DummyCapture — signal synthétique (test UI)
Signal 440Hz + 1320Hz, bruit aléatoire. Utilisé quand aucun backend hardware n'est disponible.

---

## Architecture logicielle

```
/opt/adnrpi-scope/
├── main.py             — Config Kivy (800×480, borderless, cursor)
├── scope_screen.py     — UI : header / waveform / mesures / contrôles
├── audio_capture.py    — Backends : Pico, INA219, ADS1115, MIC, Dummy
└── launch.sh           — Xrandr + python3 (même logique que HackPad)
```

**Kivy layout 800×480 :**
```
┌────────────────────────────────────────────────────┐ 52px
│ [<]  ADNRPi SCOPE          CH: SIM    [■ STOP]    │
├────────────────────────────────────────────────────┤
│                                                    │
│         Grille 10×8 + waveform (Canvas)            │ 320px
│         Ligne trigger jaune (ajustable)            │
│                                                    │
├─────────┬──────────┬──────────┬────────────────────┤ 44px
│Vpp:---  │Vrms:---  │Freq:---  │T:---               │
├─────────┴──────────┴──────────┴────────────────────┤ 60px
│[T/div: – 5ms +]  [V/div: – 1.00 +]  [Trig: – 0.00 +]│
└────────────────────────────────────────────────────┘
```

**Détection fréquence :** passages à zéro (montants) → médiane des périodes.  
**Défilement :** 25 FPS, buffer limité à 3 secondes.

---

## Modes prévus

| Mode | Backend | Affichage |
|------|---------|-----------|
| Oscilloscope | Pico / ADS1115 / MCP3208 / MIC | Waveform + Vpp/Vrms/Freq |
| Multimètre | INA219 | Tension (V) + Courant (A) + Puissance (W) |
| Analyseur FFT | Pico / MIC | Spectre fréquence en barres |

Le mode multimètre INA219 sera un écran séparé (`meter_screen.py`), accessible depuis le menu principal de l'app.

---

## État d'avancement

| Tâche | État |
|-------|------|
| UI Kivy (scope_screen.py) | ✓ Codé |
| Backend DummyCapture | ✓ Codé |
| Backend AudioCapture (ALSA) | ✓ Codé (inactif — codec absent) |
| Backend ADS1115 (I2C) | ✓ Codé (composant non disponible) |
| Backend PicoCapture (USB) | ✓ Codé (Pico non connecté) |
| Backend INA219 (multimètre) | ⬜ À coder (`meter_screen.py`) |
| Backend MCP3208 (SPI) | ⬜ À coder (SPI à activer + composant) |
| Test UI DummyCapture sur SmartPi | 🔄 En cours (2026-09-29) |
| Fix codec audio H3 (overlay DT) | ⬜ À étudier |
| Mode multimètre INA219 | ⬜ À coder |
| Intégration dans build GitHub | ⬜ Après validation sur carte |

---

## Fix codec audio H3 (notes techniques)

Le module `sun8i_codec_analog` est compilé dans le noyau Armbian (`builtin`).
Il ne s'active que si le nœud device tree correspondant est présent.

Pour l'activer :
1. Créer un overlay DTS `sun8i-h3-analog-codec.dts` avec le nœud codec et la route MIC
2. Compiler en `.dtbo` avec `dtc`
3. Copier dans `/boot/overlay-user/`
4. Ajouter `overlays=analog-codec` dans `armbianEnv.txt`
5. Redémarrer → `arecord -l` doit montrer le périphérique

Le nœud DTS requis (à vérifier dans le DTB H3 de base) :
```dts
&codec {
    status = "okay";
    allwinner,audio-routing =
        "Line Out", "LINEOUT",
        "MIC1", "Mic",
        "Mic", "HBIAS";
};
```

---

## Commandes utiles sur le SmartPi

```bash
# Lancer le scope manuellement
rm -f /tmp/.X0-lock; xinit /opt/adnrpi-scope/launch.sh -- :0 vt1 -nolisten tcp

# Logs
tail -f /tmp/scope.log

# Arrêter
killall xinit

# Vérifier I2C
i2cdetect -y 0   # scan I2C-0 (doit voir 0x40 si INA219 branché)

# Revenir à HackPad
systemctl start adnrpi-hackpad.service
```
