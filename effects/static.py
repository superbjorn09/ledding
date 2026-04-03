from effects.base import PiEffect


class EffectStatic(PiEffect):
    """All LEDs at one brightness level."""
    name = "static"

    def __init__(self):
        super().__init__()
        self.brightness = 253
        self.hue = 30  # warm white

    def next_frame(self, num_leds):
        return [self.brightness] * num_leds
