#!/usr/bin/python3
# Python 3 code to analyze sound, perform FFT and send to ESP32 via serial.
# Includes a web interface to control FFT and ESP32 parameters.
# Bass overlay effects: flash, pulse, wave.

import pyaudio
import serial
import numpy
import struct
import threading
import json
import time
import math
from http.server import BaseHTTPRequestHandler, HTTPServer

# Serial command protocol — must match include/serial_cmd.h
CMD_PREFIX         = 0xFE
CMD_NEXT_MODE      = 0x01
CMD_PREV_MODE      = 0x02
CMD_NEXT_COLOR     = 0x03
CMD_PREV_COLOR     = 0x04
CMD_INC_INTENSITY  = 0x05
CMD_DEC_INTENSITY  = 0x06
CMD_INC_BRIGHTNESS = 0x07
CMD_DEC_BRIGHTNESS = 0x08

# Bass effect modes
BASS_EFFECT_OFF   = 'off'
BASS_EFFECT_FLASH = 'flash'
BASS_EFFECT_PULSE = 'pulse'
BASS_EFFECT_WAVE  = 'wave'

BASS_THRESHOLD = 80
BASS_BINS = 20  # number of center bins to average for bass detection


class BassEffectState:
    """Tracks the current state of a bass overlay effect."""
    def __init__(self):
        self.trigger_time = 0
        self.intensity = 0
        # Wave-specific
        self.wave_pos = 0.0


class AppState:
    """Shared state between FFT thread and web server."""
    def __init__(self):
        self.serial_lock = threading.Lock()
        self.fft_running = threading.Event()
        self.fft_running.set()  # start with FFT active
        self.exponent = 2.5
        self.num_leds = 480
        self.chunk = 2**11
        self.samplerate = 48000
        self.device = 0
        self.ser = None
        self.debug_levels = []
        self.debug_enabled = False
        self.bass_effect = BASS_EFFECT_OFF
        self.bass_state = BassEffectState()
        self.bass_threshold = BASS_THRESHOLD


def list_devices():
    """List all audio input devices."""
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['maxInputChannels'] > 0:
            print(str(i) + '. ' + dev['name'])
    p.terminate()


def find_monitor_source():
    """Configure and find the monitor source for FFT analysis.

    Sets PipeWire's default source to the sink monitor via pactl, then
    returns the PyAudio device index for the 'default' device. This way
    PyAudio reads whatever audio is being played out (Bluetooth stream).
    """
    import subprocess, os

    env = {**os.environ, 'XDG_RUNTIME_DIR': '/run/user/1000'}

    # Find the first .monitor source and set it as default
    try:
        result = subprocess.run(
            ['pactl', 'list', 'sources', 'short'],
            capture_output=True, text=True, timeout=5, env=env,
        )
        for line in result.stdout.strip().split('\n'):
            parts = line.split('\t')
            if len(parts) >= 2 and '.monitor' in parts[1]:
                monitor_name = parts[1]
                subprocess.run(
                    ['pactl', 'set-default-source', monitor_name],
                    timeout=5, env=env,
                )
                print('Set default source to monitor: %s' % monitor_name)
                break
    except Exception as e:
        print('pactl failed: %s' % e)

    # Find the 'default' PyAudio device
    p = pyaudio.PyAudio()
    default_index = None
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['maxInputChannels'] > 0 and dev['name'] == 'default':
            default_index = i
            print('Using default device: %d (ch: %d)' % (i, dev['maxInputChannels']))
            break
    p.terminate()
    return default_index


def find_serial_port():
    """Find the ESP32 serial port. Tries /dev/ttyUSB* first, then /dev/serial0."""
    import glob
    for pattern in ['/dev/ttyUSB*', '/dev/serial0']:
        ports = sorted(glob.glob(pattern))
        if ports:
            return ports[0]
    return '/dev/ttyUSB0'


def build_log_bins(num_bins, num_fft_bins, freq_min=20, freq_max=6000, samplerate=48000):
    """Build logarithmically spaced bin boundaries for FFT-to-LED mapping.

    Returns a list of (start, end) index pairs into the FFT array,
    one per LED. Low frequencies (bass) get more LEDs, high frequencies fewer.
    """
    fft_freq_max = samplerate / 2
    bin_hz = fft_freq_max / num_fft_bins

    log_min = math.log10(freq_min)
    log_max = math.log10(freq_max)

    bins = []
    for i in range(num_bins):
        f_start = 10 ** (log_min + (log_max - log_min) * i / num_bins)
        f_end = 10 ** (log_min + (log_max - log_min) * (i + 1) / num_bins)
        idx_start = int(f_start / bin_hz)
        idx_end = max(int(f_end / bin_hz), idx_start + 1)
        if idx_end > num_fft_bins:
            idx_end = num_fft_bins
        bins.append((idx_start, idx_end))
    return bins


def calculate_levels_channel(channel_data, samplerate, num_leds):
    """Use FFT to calculate volume for each frequency band (log-scaled) for one channel."""
    fourier = numpy.fft.fft(channel_data)
    magnitudes = numpy.abs(fourier[0:len(fourier) // 2]) / 1000

    num_fft_bins = len(magnitudes)
    log_bins = build_log_bins(num_leds, num_fft_bins,
                              freq_min=20, freq_max=6000,
                              samplerate=samplerate)

    levels = []
    for start, end in log_bins:
        level = numpy.mean(magnitudes[start:end]) if end > start else 0
        level = numpy.log1p(level)
        levels.append(int(abs(level)))

    return levels


def detect_bass(output_levels, num_leds, threshold):
    """Detect a bass hit by averaging the center bins (where bass lives)."""
    n = len(output_levels)
    mid = n // 2
    start = max(mid - BASS_BINS, 0)
    end = min(mid + BASS_BINS, n)
    bass_section = output_levels[start:end]
    if not bass_section:
        return 0
    return sum(bass_section) / len(bass_section)


def apply_bass_flash(output_levels, bass_state, now):
    """Flash: all LEDs blitz white on bass hit, fast fade-out."""
    elapsed = now - bass_state.trigger_time
    fade_duration = 0.15
    if elapsed > fade_duration:
        return output_levels

    fade = 1.0 - (elapsed / fade_duration)
    flash_val = int(253 * fade * bass_state.intensity)

    result = []
    for level in output_levels:
        result.append(min(max(level, flash_val), 253))
    return result


def apply_bass_pulse(output_levels, bass_state, now):
    """Pulse: boost all LED brightness on bass, decaying oscillation."""
    elapsed = now - bass_state.trigger_time
    decay_duration = 0.4
    if elapsed > decay_duration:
        return output_levels

    decay = 1.0 - (elapsed / decay_duration)
    # Damped oscillation for pulsing feel
    oscillation = math.cos(elapsed * 25) * 0.5 + 0.5
    boost = decay * oscillation * bass_state.intensity

    result = []
    for level in output_levels:
        boosted = int(level + 200 * boost)
        result.append(min(boosted, 253))
    return result


def apply_bass_wave(output_levels, bass_state, now):
    """Wave: ripple expanding from center outward on bass hit, fading."""
    elapsed = now - bass_state.trigger_time
    wave_duration = 0.5
    if elapsed > wave_duration:
        return output_levels

    n = len(output_levels)
    mid = n // 2
    fade = 1.0 - (elapsed / wave_duration)
    # Wave front position: 0 (center) to 1 (edges)
    wave_front = elapsed / wave_duration
    wave_width = 0.08

    result = list(output_levels)
    for i in range(n):
        dist_from_center = abs(i - mid) / max(mid, 1)
        # How close is this LED to the wave front?
        wave_proximity = 1.0 - min(abs(dist_from_center - wave_front) / wave_width, 1.0)
        if wave_proximity > 0:
            boost = int(253 * wave_proximity * fade * bass_state.intensity)
            result[i] = min(result[i] + boost, 253)
    return result


BASS_EFFECTS = {
    BASS_EFFECT_FLASH: apply_bass_flash,
    BASS_EFFECT_PULSE: apply_bass_pulse,
    BASS_EFFECT_WAVE:  apply_bass_wave,
}


def send_command(state, cmd_byte):
    """Send a command to the ESP32 via the serial command protocol."""
    if state.ser is None:
        return
    with state.serial_lock:
        state.ser.write(bytes([CMD_PREFIX, cmd_byte]))


def fft_thread(state):
    """FFT processing loop running in a background thread."""
    print("FFT thread started")

    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=2,
        rate=state.samplerate,
        input=True,
        frames_per_buffer=state.chunk,
        input_device_index=state.device,
    )

    try:
        while True:
            # wait until FFT is enabled
            state.fft_running.wait()

            data = stream.read(state.chunk, exception_on_overflow=False)

            # Split stereo into left and right channels
            stereo = numpy.frombuffer(data, dtype=numpy.int16)
            left = stereo[0::2]
            right = stereo[1::2]

            # Each channel gets half the LEDs
            half_leds = state.num_leds // 2

            levels_left = calculate_levels_channel(left, state.samplerate, half_leds)
            levels_right = calculate_levels_channel(right, state.samplerate, half_leds)

            # Left channel: bass in center (reversed), Right channel: bass in center
            levels = list(reversed(levels_left)) + levels_right

            exponent = state.exponent

            output_levels = []
            for level in levels[2:]:
                level = int(level ** exponent)
                if level >= 254:
                    level = 253
                elif level <= 60:
                    level = 0
                output_levels.append(level)

            # Bass detection and effect overlay
            now = time.time()
            if state.bass_effect != BASS_EFFECT_OFF:
                bass_avg = detect_bass(output_levels, state.num_leds, state.bass_threshold)
                if bass_avg > state.bass_threshold:
                    # Normalize intensity: 0.0 to 1.0
                    intensity = min((bass_avg - state.bass_threshold) / (253 - state.bass_threshold), 1.0)
                    # Only re-trigger if previous effect has decayed enough
                    if now - state.bass_state.trigger_time > 0.1:
                        state.bass_state.trigger_time = now
                        state.bass_state.intensity = intensity

                effect_fn = BASS_EFFECTS.get(state.bass_effect)
                if effect_fn:
                    output_levels = effect_fn(output_levels, state.bass_state, now)

            if state.debug_enabled:
                state.debug_levels = output_levels

            if state.ser is not None:
                with state.serial_lock:
                    for level in output_levels:
                        state.ser.write(bytes([level]))
                    state.ser.write(bytes([255]))
                    state.ser.read()

    except Exception as e:
        print("FFT thread error: %s" % e)
    finally:
        print("FFT thread stopping")
        stream.close()
        p.terminate()


HTML_PAGE = '''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ledding Control</title>
    <style>
        body { font-family: sans-serif; max-width: 960px; margin: 20px auto; padding: 0 10px; }
        h1 { font-size: 1.4em; }
        h2 { font-size: 1.1em; margin-top: 1.5em; }
        .btn-group { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
        button {
            padding: 10px 16px; font-size: 1em; border: 1px solid #ccc;
            border-radius: 4px; cursor: pointer; background: #f5f5f5;
        }
        button:active { background: #ddd; }
        button.on { background: #4CAF50; color: white; border-color: #4CAF50; }
        button.off { background: #f44336; color: white; border-color: #f44336; }
        button.toggle-on { background: #2196F3; color: white; border-color: #2196F3; }
        button.effect-active { background: #FF9800; color: white; border-color: #FF9800; }
        .slider-row { display: flex; align-items: center; gap: 10px; margin: 8px 0; }
        .slider-row input { flex: 1; }
        .slider-row span { min-width: 3em; text-align: right; }
        #status { color: #666; margin-top: 1em; font-size: 0.9em; }
        #led-strip {
            display: none;
            margin-top: 12px;
            background: #111;
            border-radius: 6px;
            padding: 8px;
            overflow-x: auto;
        }
        #led-strip.active { display: block; }
        #led-canvas {
            width: 100%;
            height: 60px;
            display: block;
        }
    </style>
</head>
<body>
    <h1>Ledding Control</h1>

    <h2>FFT</h2>
    <div class="btn-group">
        <button class="on" onclick="post('/fft/start')">Start</button>
        <button class="off" onclick="post('/fft/stop')">Stop</button>
    </div>
    <div class="slider-row">
        <label>Exponent:</label>
        <input type="range" min="0.5" max="5.0" step="0.1" id="exponent"
               oninput="document.getElementById('exp-val').textContent=this.value"
               onchange="post('/fft/params', {exponent: parseFloat(this.value)})">
        <span id="exp-val"></span>
        <button onclick="document.getElementById('exponent').value=2.5;document.getElementById('exp-val').textContent='2.5';post('/fft/params',{exponent:2.5})">Reset</button>
    </div>

    <h2>Bass Effect</h2>
    <div class="btn-group" id="bass-buttons">
        <button id="bass-off" onclick="setBass('off')">Off</button>
        <button id="bass-flash" onclick="setBass('flash')">Flash</button>
        <button id="bass-pulse" onclick="setBass('pulse')">Pulse</button>
        <button id="bass-wave" onclick="setBass('wave')">Wave</button>
    </div>
    <div class="slider-row">
        <label>Threshold:</label>
        <input type="range" min="20" max="200" step="5" id="bass-threshold"
               oninput="document.getElementById('thresh-val').textContent=this.value"
               onchange="post('/bass/params', {threshold: parseInt(this.value)})">
        <span id="thresh-val"></span>
    </div>

    <h2>LED Debug</h2>
    <div class="btn-group">
        <button id="debug-btn" onclick="toggleDebug()">Show LEDs</button>
    </div>
    <div id="led-strip">
        <canvas id="led-canvas"></canvas>
    </div>

    <h2>ESP32 Mode</h2>
    <div class="btn-group">
        <button onclick="cmd('prev_mode')">&#9664; Prev</button>
        <button onclick="cmd('next_mode')">Next &#9654;</button>
    </div>

    <h2>Brightness</h2>
    <div class="btn-group">
        <button onclick="cmd('dec_brightness')">&#8722;</button>
        <button onclick="cmd('inc_brightness')">+</button>
    </div>

    <h2>Color</h2>
    <div class="btn-group">
        <button onclick="cmd('prev_color')">&#9664; Prev</button>
        <button onclick="cmd('next_color')">Next &#9654;</button>
    </div>

    <h2>Intensity</h2>
    <div class="btn-group">
        <button onclick="cmd('dec_intensity')">&#8722;</button>
        <button onclick="cmd('inc_intensity')">+</button>
    </div>

    <div id="status"></div>

    <script>
        let debugActive = false;
        let debugInterval = null;
        let currentBassEffect = 'off';

        function post(url, data) {
            fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: data ? JSON.stringify(data) : ''
            }).then(r => r.json()).then(r => {
                document.getElementById('status').textContent = r.status || '';
            });
        }
        function cmd(name) {
            post('/esp/command', {command: name});
        }

        function setBass(mode) {
            currentBassEffect = mode;
            post('/bass/effect', {effect: mode});
            updateBassButtons();
        }

        function updateBassButtons() {
            ['off', 'flash', 'pulse', 'wave'].forEach(m => {
                const btn = document.getElementById('bass-' + m);
                if (m === currentBassEffect) {
                    btn.classList.add('effect-active');
                } else {
                    btn.classList.remove('effect-active');
                }
            });
        }

        function toggleDebug() {
            debugActive = !debugActive;
            const btn = document.getElementById('debug-btn');
            const strip = document.getElementById('led-strip');
            if (debugActive) {
                btn.textContent = 'Hide LEDs';
                btn.classList.add('toggle-on');
                strip.classList.add('active');
                post('/debug/on');
                debugInterval = setInterval(fetchLevels, 50);
            } else {
                btn.textContent = 'Show LEDs';
                btn.classList.remove('toggle-on');
                strip.classList.remove('active');
                post('/debug/off');
                clearInterval(debugInterval);
                debugInterval = null;
            }
        }

        function fetchLevels() {
            fetch('/debug/levels').then(r => r.json()).then(data => {
                drawLeds(data.levels || []);
            });
        }

        function drawLeds(levels) {
            const canvas = document.getElementById('led-canvas');
            const ctx = canvas.getContext('2d');
            const dpr = window.devicePixelRatio || 1;

            canvas.width = canvas.clientWidth * dpr;
            canvas.height = canvas.clientHeight * dpr;
            ctx.scale(dpr, dpr);

            const w = canvas.clientWidth;
            const h = canvas.clientHeight;
            const n = levels.length || 1;
            const ledW = w / n;

            ctx.clearRect(0, 0, w, h);

            for (let i = 0; i < levels.length; i++) {
                const v = Math.min(levels[i] / 253, 1);
                const hue = 120 - v * 120; // green(0) -> red(max)
                ctx.fillStyle = 'hsl(' + hue + ', 100%, ' + (v * 50) + '%)';
                ctx.fillRect(i * ledW, h * (1 - v), ledW - 0.5, h * v);
            }
        }

        // load current state on page load
        fetch('/status').then(r => r.json()).then(s => {
            document.getElementById('exponent').value = s.exponent;
            document.getElementById('exp-val').textContent = s.exponent;
            document.getElementById('bass-threshold').value = s.bass_threshold;
            document.getElementById('thresh-val').textContent = s.bass_threshold;
            currentBassEffect = s.bass_effect;
            updateBassButtons();
            if (s.debug_enabled) {
                toggleDebug();
            }
        });
    </script>
</body>
</html>
'''

COMMANDS = {
    'next_mode':      CMD_NEXT_MODE,
    'prev_mode':      CMD_PREV_MODE,
    'next_color':     CMD_NEXT_COLOR,
    'prev_color':     CMD_PREV_COLOR,
    'inc_intensity':  CMD_INC_INTENSITY,
    'dec_intensity':  CMD_DEC_INTENSITY,
    'inc_brightness': CMD_INC_BRIGHTNESS,
    'dec_brightness': CMD_DEC_BRIGHTNESS,
}


def make_handler(state):
    """Create an HTTP request handler with access to the shared state."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(HTML_PAGE.encode('utf-8'))
            elif self.path == '/status':
                self._json_response({
                    'fft_running': state.fft_running.is_set(),
                    'exponent': state.exponent,
                    'num_leds': state.num_leds,
                    'debug_enabled': state.debug_enabled,
                    'bass_effect': state.bass_effect,
                    'bass_threshold': state.bass_threshold,
                })
            elif self.path == '/debug/levels':
                self._json_response({
                    'levels': state.debug_levels,
                })
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == '/fft/start':
                state.fft_running.set()
                self._json_response({'status': 'FFT started'})

            elif self.path == '/fft/stop':
                state.fft_running.clear()
                self._json_response({'status': 'FFT stopped'})

            elif self.path == '/fft/params':
                body = self._read_body()
                if body is None:
                    return
                if 'exponent' in body:
                    state.exponent = float(body['exponent'])
                if 'num_leds' in body:
                    state.num_leds = int(body['num_leds'])
                self._json_response({'status': 'params updated',
                                     'exponent': state.exponent})

            elif self.path == '/bass/effect':
                body = self._read_body()
                if body is None:
                    return
                effect = body.get('effect', 'off')
                if effect in (BASS_EFFECT_OFF, BASS_EFFECT_FLASH,
                              BASS_EFFECT_PULSE, BASS_EFFECT_WAVE):
                    state.bass_effect = effect
                    self._json_response({'status': 'bass effect: %s' % effect})
                else:
                    self._json_response({'status': 'unknown effect'}, 400)

            elif self.path == '/bass/params':
                body = self._read_body()
                if body is None:
                    return
                if 'threshold' in body:
                    state.bass_threshold = int(body['threshold'])
                self._json_response({'status': 'bass threshold: %d' % state.bass_threshold})

            elif self.path == '/esp/command':
                body = self._read_body()
                if body is None:
                    return
                cmd_name = body.get('command', '')
                cmd_byte = COMMANDS.get(cmd_name)
                if cmd_byte is None:
                    self._json_response({'status': 'unknown command: %s' % cmd_name}, 400)
                    return
                send_command(state, cmd_byte)
                self._json_response({'status': 'sent: %s' % cmd_name})

            elif self.path == '/debug/on':
                state.debug_enabled = True
                self._json_response({'status': 'debug on'})

            elif self.path == '/debug/off':
                state.debug_enabled = False
                state.debug_levels = []
                self._json_response({'status': 'debug off'})

            else:
                self.send_error(404)

        def _read_body(self):
            length = int(self.headers.get('Content-Length', 0))
            if length == 0:
                return {}
            try:
                return json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, ValueError) as e:
                self._json_response({'status': 'invalid JSON: %s' % e}, 400)
                return None

        def _json_response(self, data, code=200):
            body = json.dumps(data).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            # suppress per-request log spam
            pass

    return Handler


def main():
    list_devices()

    state = AppState()

    monitor = find_monitor_source()
    if monitor is not None:
        state.device = monitor
    else:
        print("WARNING: No monitor source found, falling back to device 0")

    serial_port = find_serial_port()
    try:
        state.ser = serial.Serial(
            port=serial_port,
            baudrate=115200,
            timeout=5,
        )
        print("Using serial port: %s" % serial_port)
    except serial.SerialException as e:
        print("WARNING: Serial port not available (%s), running without ESP32" % e)
        state.ser = None

    t = threading.Thread(target=fft_thread, args=(state,), daemon=True)
    t.start()

    server = HTTPServer(('0.0.0.0', 8000), make_handler(state))
    print("Web server running on http://0.0.0.0:8000/")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.server_close()
        if state.ser:
            state.ser.close()


if __name__ == '__main__':
    main()
