import math
from effects.base import PiEffect


class EffectRainbow(PiEffect):
    """Smooth wave pattern cycling across the strip."""
    name = "rainbow"

    def __init__(self):
        super().__init__()
        self.offset = 0.0
        self.speed = 2.0
        self.auto_color = True
        self._auto_color_speed = 60

    def next_frame(self, num_leds):
        frame = []
        for i in range(num_leds):
            phase = (i / num_leds + self.offset / num_leds) * 2 * math.pi
            val = int((math.sin(phase * 3) * 0.5 + 0.5) * 253)
            frame.append(max(0, min(253, val)))
        self.offset = (self.offset + self.speed) % num_leds
        return frame
