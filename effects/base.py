import time


class PiEffect:
    """Base class for Pi-side LED effects."""
    name = "base"

    def __init__(self):
        self.hue = 0          # 0-360, used for debug visualization color
        self.saturation = 100  # 0-100, 0=white, 100=full color
        self.auto_color = False
        self._auto_color_speed = 30  # degrees per second

    def next_frame(self, num_leds):
        """Return a list of num_leds brightness values (0-253)."""
        return [0] * num_leds

    def get_hue(self):
        """Return the current hue, auto-cycling if enabled."""
        if self.auto_color:
            self.hue = (time.time() * self._auto_color_speed) % 360
        return self.hue
