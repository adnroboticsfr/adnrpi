"""
Backends de capture pour l'oscilloscope ADNRPi.

Sélection automatique dans make_capture() :
  1. Pi Pico USB serial (/dev/ttyACM0) — 12-bit, DC, ~50kHz
  2. ADS1115 I2C        (/dev/i2c-0)   — 16-bit, DC, 860 SPS
  3. ALSA microphone    (sounddevice)   — 16-bit, AC, 44100 Hz
  4. Dummy synthétique                  — test sans matériel

H3 GPIO note : les 40 broches sont entièrement numériques (pas d'ADC).
Pour une mesure analogique il faut un ADC externe.
"""
import threading
import collections
import math
import numpy as np
import os


# ── 1. Pi Pico via USB serial ─────────────────────────────────────────────────

class PicoCapture:
    """Lit les échantillons ADC depuis un Pi Pico via /dev/ttyACM0.

    Protocole MicroPython attendu sur le Pico :
        from machine import ADC, Pin
        import sys, utime
        adc = ADC(Pin(26))         # ADC0 = GP26
        while True:
            sys.stdout.write(f"S,{adc.read_u16() >> 4}\\n")  # 12-bit
            utime.sleep_us(20)

    Les valeurs 12-bit (0-4095) sont converties en flottant centré [-1, +1].
    """
    SAMPLE_RATE = 44100    # estimation — limité par USB serial en pratique

    def __init__(self, port="/dev/ttyACM0", vref=3.3):
        self._port    = port
        self._vref    = vref
        self._buf     = collections.deque(maxlen=self.SAMPLE_RATE * 2)
        self._lock    = threading.Lock()
        self._running = False

    def start(self):
        import serial
        self._ser     = serial.Serial(self._port, 115200, timeout=0.1)
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False
        if hasattr(self, "_ser"):
            self._ser.close()

    def _loop(self):
        while self._running:
            try:
                line = self._ser.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("S,"):
                    raw = int(line[2:])
                    # 12-bit centré : (val/4095 * vref - vref/2) / (vref/2)
                    v = (raw / 4095.0 - 0.5) * 2.0
                    with self._lock:
                        self._buf.append(v)
            except Exception:
                pass

    def get_samples(self, n):
        with self._lock:
            buf = list(self._buf)
        if len(buf) >= n:
            return buf[-n:]
        return [0.0] * (n - len(buf)) + buf

    @property
    def sample_rate(self):
        return self.SAMPLE_RATE

    @property
    def label(self):
        return "PICO"


# ── 2. ADS1115 via I2C (/dev/i2c-0) ──────────────────────────────────────────

class ADS1115Capture:
    """Lit le canal AIN0-GND de l'ADS1115 à 860 SPS.

    Câblage SmartPi One (I2C-0, toujours actif) :
        ADS1115 VCC  → Pin 1  (3.3V)
        ADS1115 GND  → Pin 6
        ADS1115 SDA  → Pin 3  (I2C0_SDA / GPIOA12)
        ADS1115 SCL  → Pin 5  (I2C0_SCL / GPIOA11)
        ADS1115 AIN0 → signal à mesurer (0–3.3V)
        ADDR pin GND → adresse I2C 0x48

    Fréquence max : ~430 Hz (Nyquist à 860 SPS).
    Bon pour : tensions DC, signaux lents, mode multimètre.
    """
    SAMPLE_RATE = 860      # SPS max de l'ADS1115
    I2C_ADDR    = 0x48     # ADDR=GND
    REG_CONV    = 0x00
    REG_CONF    = 0x01

    # Config : AIN0/GND, gain ±4.096V, 860SPS, single-shot
    _CONF_SINGLE = 0xC3E3  # OS=1 MUX=100 PGA=001 MODE=1 DR=111 COMP_QUE=11

    def __init__(self, bus=0, addr=0x48):
        self._bus_num = bus
        self._addr    = addr
        self._buf     = collections.deque(maxlen=self.SAMPLE_RATE * 5)
        self._lock    = threading.Lock()
        self._running = False

    def start(self):
        import smbus2
        self._bus     = smbus2.SMBus(self._bus_num)
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False
        if hasattr(self, "_bus"):
            self._bus.close()

    def _write_conf(self):
        import smbus2
        msb = (self._CONF_SINGLE >> 8) & 0xFF
        lsb = self._CONF_SINGLE & 0xFF
        self._bus.write_i2c_block_data(self._addr, self.REG_CONF, [msb, lsb])

    def _read_raw(self):
        data = self._bus.read_i2c_block_data(self._addr, self.REG_CONV, 2)
        raw  = (data[0] << 8) | data[1]
        if raw > 32767:
            raw -= 65536
        return raw

    def _loop(self):
        import time
        while self._running:
            try:
                self._write_conf()
                time.sleep(1 / self.SAMPLE_RATE + 0.0002)
                raw = self._read_raw()
                # PGA=±4.096V → 1 LSB = 4.096/32768 V
                volts = raw * 4.096 / 32768.0
                # Centrer autour de 0 (milieu de la plage 0-3.3V)
                normalized = (volts - 1.65) / 1.65
                with self._lock:
                    self._buf.append(normalized)
            except Exception:
                time.sleep(0.01)

    def get_samples(self, n):
        with self._lock:
            buf = list(self._buf)
        if len(buf) >= n:
            return buf[-n:]
        return [0.0] * (n - len(buf)) + buf

    @property
    def sample_rate(self):
        return self.SAMPLE_RATE

    @property
    def label(self):
        return "ADS1115"


# ── 3. Microphone ALSA ────────────────────────────────────────────────────────

class AudioCapture:
    """Capture le microphone via sounddevice (backend ALSA).

    Note H3 : le codec sun8i-codec-analog est builtin mais nécessite
    un overlay device tree pour être activé. Si /dev/snd/ n'a pas de
    périphérique PCM, la capture échouera → fallback sur DummyCapture.
    """
    SAMPLE_RATE = 44100
    BLOCK_SIZE  = 1024

    def __init__(self, device=None):
        self._device = device
        self._buf    = collections.deque(maxlen=self.SAMPLE_RATE * 3)
        self._lock   = threading.Lock()
        self._stream = None

    def start(self):
        import sounddevice as sd
        self._stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            blocksize=self.BLOCK_SIZE,
            channels=1,
            dtype="float32",
            device=self._device,
            callback=self._cb,
        )
        self._stream.start()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _cb(self, indata, frames, t, status):
        with self._lock:
            self._buf.extend(indata[:, 0].tolist())

    def get_samples(self, n):
        with self._lock:
            buf = list(self._buf)
        if len(buf) >= n:
            return buf[-n:]
        return [0.0] * (n - len(buf)) + buf

    @property
    def sample_rate(self):
        return self.SAMPLE_RATE

    @property
    def label(self):
        return "MIC"


# ── 4. Générateur synthétique ─────────────────────────────────────────────────

class DummyCapture:
    """Signal 440Hz + 1320Hz pour tester l'UI sans matériel."""
    SAMPLE_RATE = 44100

    def __init__(self):
        self._t    = 0.0
        self._lock = threading.Lock()

    def start(self):
        pass

    def stop(self):
        pass

    def get_samples(self, n):
        with self._lock:
            t = np.linspace(self._t, self._t + n / self.SAMPLE_RATE, n, endpoint=False)
            self._t += n / self.SAMPLE_RATE
        sig = (0.55 * np.sin(2 * math.pi * 440  * t) +
               0.25 * np.sin(2 * math.pi * 1320 * t) +
               0.06 * np.random.randn(n))
        return sig.tolist()

    @property
    def sample_rate(self):
        return self.SAMPLE_RATE

    @property
    def label(self):
        return "SIM"


# ── Sélection automatique ─────────────────────────────────────────────────────

def make_capture():
    """Essaie les backends dans l'ordre et retourne (capture, label)."""

    # 1. Pi Pico USB
    if os.path.exists("/dev/ttyACM0"):
        try:
            c = PicoCapture()
            c.start()
            return c, "PICO"
        except Exception:
            pass

    # 2. ADS1115 I2C
    if os.path.exists("/dev/i2c-0"):
        try:
            import smbus2
            c = ADS1115Capture()
            c.start()
            return c, "ADS1115"
        except Exception:
            pass

    # 3. Microphone ALSA
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        has_input = any(d["max_input_channels"] > 0 for d in devs)
        if has_input:
            c = AudioCapture()
            c.start()
            return c, "MIC"
    except Exception:
        pass

    # 4. Dummy synthétique
    c = DummyCapture()
    c.start()
    return c, "SIM"
