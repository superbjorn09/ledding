#!/usr/bin/python3
# Python 2.7 code to analyze sound and interface with Arduino

import pyaudio # from http://people.csail.mit.edu/hubert/pyaudio/
import serial  # from http://pyserial.sourceforge.net/
import numpy   # from http://numpy.scipy.org/
import audioop
import sys
import math
import struct
import json
import wave
import time
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer


'''
Sources

http://www.swharden.com/blog/2010-03-05-realtime-fft-graph-of-audio-wav-file-or-microphone-input-with-python-scipy-and-wckgraph/
http://macdevcenter.com/pub/a/python/2001/01/31/numerically.html?page=2

'''

LED_COUNT      = 16      # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
#LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53
host_name = '0.0.0.0'    # Change this to your Raspberry Pi IP address
host_port = 8000
html_template = '''
    <!doctype html>
    <html lang=en>
    <head>
	<!-- Required meta tags -->
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

	<!-- Bootstrap CSS -->
	<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" integrity="sha384-JcKb8q3iqJ61gNV9KGb8thSsNjpSL0n8PARn9HuZOnIxN0hoP+VmmDGMN5t9UJ0Z" crossorigin="anonymous">

	<title>Hello, people!! =D </title>
    </head>
        <body style="width:300px; margin: 20px auto;">
            <h1>Welcome to my Raspberry Pi</h1>
            <p>Select Mode:<br>
                <a href="/mode-0">Mode 0: Off</a><br>
                <a href="/mode-1">Mode 1: Theater Chase</a><br>
                <a href="/mode-2">Mode 2: Theater Chase Rainbow</a><br>
                <a href="/mode-3">Mode 3: Rainbow</a><br>
                <a href="/mode-4">Mode 4: Rainbow Cycle</a><br>
            </p>
            <div id="led-status"></div>
            <script>
                document.getElementById("led-status").innerHTML="{}";
            </script>
        </body>
    </html>
'''

print("Debug Information:")
print(f"LED Count: {LED_COUNT}")
print(f"LED PIN: {LED_PIN}")
print(f"LED Frequency {LED_FREQ_HZ} Hz")
print(f"LED DMA: {LED_DMA}")
print(f"LED Brightness: {LED_BRIGHTNESS}")
print(f"LED Invert: {LED_INVERT}")
print(f"LED Channel: {LED_CHANNEL}")
# strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
# strip.begin()


class MyServer(BaseHTTPRequestHandler):
    """ A special implementation of BaseHTTPRequestHander for reading data from
        and control GPIO of a Raspberry Pi
    """

    def do_HEAD(self):
        """ do_HEAD() can be tested use curl command
            'curl -I http://server-ip-address:port'
        """
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        html = html_template
        self.do_HEAD()
        status = ''
        if self.path=='/':
            pass
        elif self.path=='/mode-0':
            #TODO: This should close the thread created before (if there is any)
            status='Currently Off'
        elif self.path=='/mode-1':
            status='Playing Mode 1'
            x = threading.Thread(target=arduino_soundlight, args=())
            x.start()
        elif self.path=='/mode-2':
            status='Playing Mode 2'
        elif self.path=='/mode-3':
            status='Playing Mode 3'
        elif self.path=='/mode-4':
            status='Playing Mode 4'
        self.wfile.write(html.format(status).encode("utf-8"))


def list_devices():
    # List all audio input devices
    p = pyaudio.PyAudio()
    i = 0
    n = p.get_device_count()
    while i < n:
        dev = p.get_device_info_by_index(i)
        if dev['maxInputChannels'] > 0:
            print(str(i)+'. '+dev['name'])
        i += 1

def arduino_soundlight():
    print("Starting Arduino Soundlight")
    chunk      = 2**11 # Change if too fast/slow, never less than 2**11
    scale      = 26    # Change if too dim/bright
    exponent   = 1     # Change if too little/too much difference between loud and quiet sounds
    samplerate = 44100

    # CHANGE THIS TO CORRECT INPUT DEVICE
    # Enable stereo mixing in your sound card
    # to make you sound output an input
    # Use list_devices() to list all your input devices
    device   = 0 # Original
    MAX = 0
    num_leds = 148 #Thats how my LEDs we have
    double = True
    if double:
        num_leds = num_leds / 2# + 4
    else:
        num_leds = num_leds# + 4

    p = pyaudio.PyAudio()
    stream = p.open(format = pyaudio.paInt16,
                    channels = 2,
                    rate = 44100,
                    input = True,
                    frames_per_buffer = chunk,
                    input_device_index = device)

    print("Starting, use Ctrl+C to stop")
    try:
        ser = serial.Serial(
            port='/dev/ttyAMA0',
            baudrate = 115200,
            timeout = 5,
        )
        while True:
            data  = stream.read(chunk, exception_on_overflow = False)

            # Do FFT
            levels = calculate_levels(data, chunk, samplerate, num_leds)
            if double:
                new = list(reversed(levels)) + levels

            levels = new

            peak = abs(int(sum(levels)-(num_leds*2)))**3.0
            peak = int(peak / 100000 / 2.5)
            if peak > ( num_leds * 2 ) or peak > 254:
                peak = num_leds * 2

            # Make it look better and send to serial
            for index, level in enumerate(levels[2:]):
                level = int(level**6.0)

                if level >= 255:
                    level = 254
                elif level <= 60:
                    level = 0
                ser.write(bytes([level]))
            ser.write(bytes([255]))
            #TODO: For peak levels
            #ser.write(chr(int(peak)))
            s = ser.read()

    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping")
        stream.close()
        p.terminate()
        ser.close()

def calculate_levels(data, chunk, samplerate, num_leds):
    # Use FFT to calculate volume for each frequency
    global MAX

    # Convert raw sound data to Numpy array
    fmt = "%dH"%(len(data)/2)
    data2 = struct.unpack(fmt, data)
    data2 = numpy.array(data2, dtype='h')

    # Apply FFT
    fourier = numpy.fft.fft(data2)

    ffty = numpy.abs(fourier[0:len(fourier)//2])/1000
    ffty1=ffty[:len(ffty)//2]
    ffty2=ffty[len(ffty)//2::]+2
    ffty2=ffty2[::-1]
    ffty=ffty1+ffty2
    ffty=numpy.log(ffty)-2

    # we filter out the deep and high frequencies, because they are
    # a) not hearable
    # b) it looks so much better this way
    fourier = list(ffty)
    music_spectrum = len(fourier)//4
    fill_up = int(num_leds - len(fourier)/4)
    fourier = fourier[:music_spectrum+fill_up]

    size = len(fourier)

    # Add up for num_leds lights
    levels = [int(abs(sum(fourier[i:(i+int(size//num_leds))]))) for i in range(0, size, int(size//num_leds))]

    return levels

if __name__ == '__main__':
    http_server = HTTPServer((host_name, host_port), MyServer)
    print("Server Starts - %s:%s" % (host_name, host_port))

    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        http_server.server_close()
