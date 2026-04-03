from effects.base import PiEffect


class EffectBolt(PiEffect):
    """A beam of light traveling along the strip with a fading trail."""
    name = "bolt"

    def __init__(self):
        super().__init__()
        self.pos = 0.0
        self.speed = 3.0
        self.head_len = 20
        self.hue = 200  # blue

    def next_frame(self, num_leds):
        frame = [0] * num_leds
        head = int(self.pos) % num_leds
        for i in range(self.head_len):
            idx = (head - i) % num_leds
            brightness = int(253 * (1.0 - i / self.head_len))
            frame[idx] = brightness
        self.pos = (self.pos + self.speed) % num_leds
        return frame
