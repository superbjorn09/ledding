#!/usr/bin/python3
# Python 3 code to analyze sound, perform FFT and send to ESP32 via serial.
# Includes a web interface to control FFT and ESP32 parameters.
# Bass overlay effects: flash, pulse, wave.

import pyaudio
import serial
import numpy
import glob
import threading
import json
import time
import math
import sys
import os
import subprocess
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn, TCPServer


class ThreadingHTTPServer(ThreadingMixIn, TCPServer):
    allow_reuse_address = True

# Allow imports from the script's directory (for effects/)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effects import EFFECTS
from effects.base import MAX_BRIGHTNESS

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

# Defaults for toggleable features (all off by default)
DEFAULT_SMOOTHING = 0.0     # 0.0 = off, 0.7 = smooth
DEFAULT_PEAK_DECAY = 0.0    # 0.0 = off, 0.95 = slow decay
DEFAULT_FREQ_MAX = 6000     # Hz


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
        self.smoothing = DEFAULT_SMOOTHING
        self.peak_decay = DEFAULT_PEAK_DECAY
        self.freq_max = DEFAULT_FREQ_MAX
        self.prev_levels = None
        self.peak_levels = None
        self._pipewire_ok = False
        self._pipewire_check_time = 0
        self.frame_thread = None
        self.fft_error = None
        self.fft_restart_count = 0
        self.web_token = os.environ.get('LEDDING_TOKEN', '')
        self.pi_mode = 'fft'
        self.effects = {name: cls() for name, cls in EFFECTS.items()}


def list_devices():
    """List all audio input devices."""
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['maxInputChannels'] > 0:
            print(str(i) + '. ' + dev['name'])
    p.terminate()


def _update_monitor_source():
    """Set PipeWire's default source to the default sink's monitor.

    This ensures the FFT always captures whatever audio is being played
    out (e.g. Bluetooth stream routed to the HiFiBerry DAC).
    Returns the chosen monitor name or None.
    """
    env = {**os.environ, 'XDG_RUNTIME_DIR': '/run/user/1000'}
    try:
        result = subprocess.run(
            ['pactl', 'get-default-sink'],
            capture_output=True, text=True, timeout=5, env=env,
        )
        default_sink = result.stdout.strip()
        if default_sink:
            monitor_name = default_sink + '.monitor'
            subprocess.run(
                ['pactl', 'set-default-source', monitor_name],
                timeout=5, env=env,
            )
            return monitor_name
    except Exception as e:
        print('pactl failed: %s' % e)
    return None


def find_monitor_source():
    """Configure and find the monitor source for FFT analysis.

    Sets PipeWire's default source to the sink monitor via pactl, then
    returns the PyAudio device index for the 'default' device. This way
    PyAudio reads whatever audio is being played out (Bluetooth stream).
    """
    monitor = _update_monitor_source()
    if monitor:
        print('Set default source to monitor: %s' % monitor)

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
    for pattern in ['/dev/ttyUSB*', '/dev/serial0']:
        ports = sorted(glob.glob(pattern))
        if ports:
            return ports[0]
    return '/dev/ttyUSB0'


def build_log_bins(num_bins, num_fft_bins, freq_min=20, freq_max=6000, samplerate=48000):
    """Build logarithmically spaced bin boundaries for FFT-to-LED mapping.

    Returns (starts, ends, counts) numpy arrays for vectorized bin averaging.
    """
    fft_freq_max = samplerate / 2
    bin_hz = fft_freq_max / num_fft_bins

    log_min = math.log10(freq_min)
    log_max = math.log10(freq_max)

    starts = numpy.empty(num_bins, dtype=numpy.intp)
    ends = numpy.empty(num_bins, dtype=numpy.intp)
    for i in range(num_bins):
        f_start = 10 ** (log_min + (log_max - log_min) * i / num_bins)
        f_end = 10 ** (log_min + (log_max - log_min) * (i + 1) / num_bins)
        idx_start = int(f_start / bin_hz)
        idx_end = max(int(f_end / bin_hz), idx_start + 1)
        if idx_end > num_fft_bins:
            idx_end = num_fft_bins
        starts[i] = idx_start
        ends[i] = idx_end
    counts = numpy.maximum(ends - starts, 1).astype(numpy.float64)
    return starts, ends, counts


def calculate_levels_channel(channel_data, log_bins):
    """Use FFT to calculate volume for each frequency band (log-scaled) for one channel."""
    starts, ends, counts = log_bins
    fourier = numpy.fft.rfft(channel_data)
    magnitudes = numpy.abs(fourier) / 1000

    cumsum = numpy.empty(len(magnitudes) + 1)
    cumsum[0] = 0
    numpy.cumsum(magnitudes, out=cumsum[1:])

    bin_means = (cumsum[ends] - cumsum[starts]) / counts
    return numpy.log1p(bin_means).astype(int)


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
    flash_val = int(MAX_BRIGHTNESS * fade * bass_state.intensity)

    result = []
    for level in output_levels:
        result.append(min(max(level, flash_val), MAX_BRIGHTNESS))
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
        result.append(min(boosted, MAX_BRIGHTNESS))
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
            boost = int(MAX_BRIGHTNESS * wave_proximity * fade * bass_state.intensity)
            result[i] = min(result[i] + boost, MAX_BRIGHTNESS)
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


def frame_thread(state):
    """Frame generation loop: dispatches between FFT and Pi-side effects."""
    print("Frame thread started")

    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=2,
        rate=state.samplerate,
        input=True,
        frames_per_buffer=state.chunk,
        input_device_index=state.device,
    )

    # Precompute log bins (recomputed when freq_max changes)
    half_leds = state.num_leds // 2
    num_fft_bins = state.chunk // 2
    current_freq_max = state.freq_max
    log_bins = build_log_bins(half_leds, num_fft_bins,
                              freq_min=20, freq_max=current_freq_max,
                              samplerate=state.samplerate)

    output_led_count = state.num_leds - 4
    last_source_check = time.monotonic()

    try:
        while True:
            # Periodically re-detect monitor source (picks up Bluetooth
            # connections that happen after the service starts)
            now_mono = time.monotonic()
            if now_mono - last_source_check > 30:
                last_source_check = now_mono
                _update_monitor_source()

            mode = state.pi_mode

            if mode == 'fft':
                # --- FFT audio processing path ---
                state.fft_running.wait()

                if state.freq_max != current_freq_max:
                    current_freq_max = state.freq_max
                    log_bins = build_log_bins(half_leds, num_fft_bins,
                                              freq_min=20, freq_max=current_freq_max,
                                              samplerate=state.samplerate)
                    state.prev_levels = None
                    state.peak_levels = None

                data = stream.read(state.chunk, exception_on_overflow=False)

                stereo = numpy.frombuffer(data, dtype=numpy.int16)
                left = stereo[0::2]
                right = stereo[1::2]

                levels_left = calculate_levels_channel(left, log_bins)
                levels_right = calculate_levels_channel(right, log_bins)

                levels = numpy.concatenate((levels_left[::-1], levels_right))

                exponent = state.exponent

                arr = levels[2:].astype(numpy.float64)
                arr = numpy.power(arr, exponent)
                arr = numpy.where(arr <= 60, 0, numpy.minimum(arr, MAX_BRIGHTNESS))
                output_levels = arr.astype(numpy.int32)

                # Frame smoothing
                smoothing = state.smoothing
                if smoothing > 0 and state.prev_levels is not None and len(state.prev_levels) == len(output_levels):
                    output_levels = (state.prev_levels * smoothing + output_levels * (1.0 - smoothing)).astype(numpy.int32)
                state.prev_levels = output_levels.copy()

                # Peak hold
                peak_decay = state.peak_decay
                if peak_decay > 0:
                    if state.peak_levels is None or len(state.peak_levels) != len(output_levels):
                        state.peak_levels = output_levels.copy()
                    else:
                        decayed = (state.peak_levels * peak_decay).astype(numpy.int32)
                        state.peak_levels = numpy.maximum(output_levels, decayed)
                        output_levels = numpy.maximum(output_levels, state.peak_levels)

                # Bass detection and effect overlay
                now = time.time()
                if state.bass_effect != BASS_EFFECT_OFF:
                    bass_avg = detect_bass(output_levels, state.num_leds, state.bass_threshold)
                    if bass_avg > state.bass_threshold:
                        intensity = min((bass_avg - state.bass_threshold) / (MAX_BRIGHTNESS - state.bass_threshold), 1.0)
                        if now - state.bass_state.trigger_time > 0.1:
                            state.bass_state.trigger_time = now
                            state.bass_state.intensity = intensity

                    effect_fn = BASS_EFFECTS.get(state.bass_effect)
                    if effect_fn:
                        output_levels = effect_fn(output_levels.tolist(), state.bass_state, now)
                    else:
                        output_levels = output_levels.tolist()
                else:
                    output_levels = output_levels.tolist()

            else:
                # --- Pi-side effect path ---
                effect = state.effects.get(mode)
                if effect is None:
                    time.sleep(0.1)
                    continue

                output_levels = effect.next_frame(output_led_count)
                output_levels = numpy.clip(output_levels, 0, MAX_BRIGHTNESS).tolist()
                time.sleep(1.0 / 30)

            # --- Common output ---
            if state.debug_enabled:
                state.debug_levels = output_levels

            if state.ser is not None:
                with state.serial_lock:
                    state.ser.write(bytes(output_levels) + b'\xff')
                    state.ser.read()

    except Exception as e:
        print("Frame thread error: %s" % e)
        state.fft_error = str(e)
    finally:
        print("Frame thread stopping")
        stream.close()
        p.terminate()


def frame_supervisor(state):
    """Restart the frame thread on crash, with exponential backoff."""
    backoff = 5
    while True:
        state.fft_error = None
        t = threading.Thread(target=frame_thread, args=(state,), daemon=True)
        state.frame_thread = t
        t.start()
        t.join()
        state.fft_restart_count += 1
        state.fft_error = "FFT thread died, restarting in %ds" % backoff
        print(state.fft_error)
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


def _load_html():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'index.html')
    with open(html_path, 'r') as f:
        return f.read()

HTML_PAGE = _load_html()



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
                    'smoothing': state.smoothing,
                    'peak_decay': state.peak_decay,
                    'freq_max': state.freq_max,
                    'fft_thread_alive': state.frame_thread is not None and state.frame_thread.is_alive(),
                    'fft_error': state.fft_error,
                    'fft_restart_count': state.fft_restart_count,
                    'pi_mode': state.pi_mode,
                    'serial_connected': state.ser is not None,
                })
            elif self.path == '/health':
                fft_alive = state.frame_thread is not None and state.frame_thread.is_alive()
                serial_ok = state.ser is not None
                now = time.time()
                if now - state._pipewire_check_time > 10:
                    try:
                        result = subprocess.run(
                            ['pactl', 'info'],
                            capture_output=True, timeout=3,
                            env={**os.environ, 'XDG_RUNTIME_DIR': '/run/user/1000'},
                        )
                        state._pipewire_ok = result.returncode == 0
                    except Exception:
                        state._pipewire_ok = False
                    state._pipewire_check_time = now
                self._json_response({
                    'healthy': fft_alive,
                    'fft_thread_alive': fft_alive,
                    'fft_error': state.fft_error,
                    'fft_restart_count': state.fft_restart_count,
                    'fft_paused': not state.fft_running.is_set(),
                    'serial_connected': serial_ok,
                    'pipewire_ok': state._pipewire_ok,
                })
            elif self.path == '/debug/levels':
                hue = 0
                sat = 100
                effect = state.effects.get(state.pi_mode)
                if effect:
                    hue = effect.get_hue()
                    sat = effect.saturation
                self._json_response({
                    'levels': state.debug_levels,
                    'hue': hue,
                    'saturation': sat,
                    'mode': state.pi_mode,
                })
            elif self.path == '/favicon.ico':
                self.send_response(204)
                self.end_headers()
            else:
                self.send_error(404)

        def do_POST(self):
            if state.web_token:
                auth = self.headers.get('Authorization', '')
                if auth != 'Bearer ' + state.web_token:
                    self._json_response({'status': 'unauthorized'}, 401)
                    return

            if self.path == '/fft/start':
                state.pi_mode = 'fft'
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
                    state.exponent = max(0.1, min(10.0, float(body['exponent'])))
                if 'num_leds' in body:
                    state.num_leds = max(10, min(2000, int(body['num_leds'])))
                if 'smoothing' in body:
                    state.smoothing = max(0.0, min(0.99, float(body['smoothing'])))
                if 'peak_decay' in body:
                    state.peak_decay = max(0.0, min(0.999, float(body['peak_decay'])))
                if 'freq_max' in body:
                    state.freq_max = max(1000, min(24000, int(body['freq_max'])))
                self._json_response({'status': 'params updated',
                                     'exponent': state.exponent})

            elif self.path == '/bass/effect':
                body = self._read_body()
                if body is None:
                    return
                effect = body.get('effect', 'off')
                if effect == BASS_EFFECT_OFF or effect in BASS_EFFECTS:
                    state.bass_effect = effect
                    self._json_response({'status': 'bass effect: %s' % effect})
                else:
                    self._json_response({'status': 'unknown effect'}, 400)

            elif self.path == '/bass/params':
                body = self._read_body()
                if body is None:
                    return
                if 'threshold' in body:
                    state.bass_threshold = max(1, min(MAX_BRIGHTNESS, int(body['threshold'])))
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

            elif self.path == '/pi/mode':
                body = self._read_body()
                if body is None:
                    return
                mode = body.get('mode', 'fft')
                valid_modes = ['fft'] + list(state.effects.keys())
                if mode not in valid_modes:
                    self._json_response({'status': 'unknown mode: %s' % mode}, 400)
                    return
                state.pi_mode = mode
                if mode == 'fft':
                    state.fft_running.set()
                else:
                    state.fft_running.clear()
                self._json_response({'status': 'mode: %s' % mode})

            elif self.path == '/pi/effect_params':
                body = self._read_body()
                if body is None:
                    return
                mode = body.get('mode', state.pi_mode)
                effect = state.effects.get(mode)
                if effect is None:
                    self._json_response({'status': 'unknown effect'}, 400)
                    return
                for key, val in body.items():
                    if key == 'mode' or key.startswith('_'):
                        continue
                    if hasattr(effect, key):
                        cur = getattr(effect, key)
                        if isinstance(cur, bool):
                            setattr(effect, key, val if isinstance(val, bool) else str(val).lower() not in ('false', '0', ''))
                        else:
                            setattr(effect, key, type(cur)(val))
                self._json_response({'status': 'effect params updated'})

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

    supervisor = threading.Thread(target=frame_supervisor, args=(state,), daemon=True)
    supervisor.start()

    server = ThreadingHTTPServer(('0.0.0.0', 8000), make_handler(state))
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
