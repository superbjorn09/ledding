#!/usr/bin/python3
# Python 3 code to analyze sound, perform FFT and send to ESP32 via serial.
# Includes a web interface to control FFT and ESP32 parameters.

import pyaudio
import serial
import numpy
import struct
import threading
import json
import time
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


class AppState:
    """Shared state between FFT thread and web server."""
    def __init__(self):
        self.serial_lock = threading.Lock()
        self.fft_running = threading.Event()
        self.fft_running.set()  # start with FFT active
        self.exponent = 2.5
        self.num_leds = 480
        self.double = True
        self.chunk = 2**11
        self.samplerate = 48000
        self.device = 0
        self.ser = None


def list_devices():
    """List all audio input devices."""
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['maxInputChannels'] > 0:
            print(str(i) + '. ' + dev['name'])
    p.terminate()


def calculate_levels(data, chunk, samplerate, num_leds):
    """Use FFT to calculate volume for each frequency band."""
    fmt = "%dH" % (len(data) // 2)
    data2 = struct.unpack(fmt, data)
    data2 = numpy.array(data2, dtype='h')

    fourier = numpy.fft.fft(data2)

    ffty = numpy.abs(fourier[0:len(fourier) // 2]) / 1000
    ffty1 = ffty[:len(ffty) // 2]
    ffty2 = ffty[len(ffty) // 2::] + 2
    ffty2 = ffty2[::-1]
    ffty = ffty1 + ffty2
    ffty = numpy.log(ffty) - 2

    fourier = list(ffty)
    music_spectrum = len(fourier) // 4
    fill_up = num_leds - len(fourier) // 4
    fourier = fourier[:music_spectrum + fill_up]

    size = len(fourier)

    levels = [int(abs(sum(fourier[i:(i + size // num_leds)])))
              for i in range(0, size, size // num_leds)]

    return levels


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
        channels=1,
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

            num_leds = state.num_leds
            if state.double:
                num_leds = num_leds // 2

            levels = calculate_levels(data, state.chunk, state.samplerate, num_leds)

            if state.double:
                levels = list(reversed(levels)) + levels

            exponent = state.exponent

            with state.serial_lock:
                for level in levels[2:]:
                    level = int(level ** exponent)
                    if level >= 254:
                        level = 253  # 0xFE is reserved for command prefix
                    elif level <= 60:
                        level = 0
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
        body { font-family: sans-serif; max-width: 480px; margin: 20px auto; padding: 0 10px; }
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
        .slider-row { display: flex; align-items: center; gap: 10px; margin: 8px 0; }
        .slider-row input { flex: 1; }
        .slider-row span { min-width: 3em; text-align: right; }
        #status { color: #666; margin-top: 1em; font-size: 0.9em; }
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
        // load current state on page load
        fetch('/status').then(r => r.json()).then(s => {
            document.getElementById('exponent').value = s.exponent;
            document.getElementById('exp-val').textContent = s.exponent;
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
                    'double': state.double,
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
                if 'double' in body:
                    state.double = bool(body['double'])
                self._json_response({'status': 'params updated',
                                     'exponent': state.exponent})

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
    state.ser = serial.Serial(
        port='/dev/serial0',
        baudrate=115200,
        timeout=5,
    )

    t = threading.Thread(target=fft_thread, args=(state,), daemon=True)
    t.start()

    server = HTTPServer(('0.0.0.0', 8000), make_handler(state))
    print("Web server running on http://0.0.0.0:8000/")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.server_close()
        state.ser.close()


if __name__ == '__main__':
    main()
