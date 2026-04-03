import numpy
from effects.base import PiEffect


class EffectMeteor(PiEffect):
    """Meteor with a randomly fading trail."""
    name = "meteor"

    def __init__(self):
        super().__init__()
        self.pos = 0
        self.speed = 2
        self.size = 10
        self.trail = None
        self.hue = 15

    def next_frame(self, num_leds):
        if self.trail is None or len(self.trail) != num_leds:
            self.trail = numpy.zeros(num_leds, dtype=numpy.int32)

        # Random fade: ~40% of LEDs decay by 64 each frame
        mask = numpy.random.randint(0, 10, size=num_leds) > 5
        self.trail[mask] = numpy.maximum(0, self.trail[mask] - 64)

        # Draw meteor head
        start = max(0, self.pos - self.size + 1)
        end = min(num_leds, self.pos + 1)
        if start < end:
            self.trail[start:end] = 253

        self.pos += self.speed
        if self.pos >= num_leds + num_leds:
            self.pos = 0
            self.trail[:] = 0

        return numpy.clip(self.trail, 0, 253).tolist()
