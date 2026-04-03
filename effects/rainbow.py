import numpy
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
        i = numpy.arange(num_leds, dtype=numpy.float64)
        phase = (i / num_leds + self.offset / num_leds) * 2 * numpy.pi
        vals = ((numpy.sin(phase * 3) * 0.5 + 0.5) * 253).astype(numpy.int32)
        self.offset = (self.offset + self.speed) % num_leds
        return numpy.clip(vals, 0, 253).tolist()
