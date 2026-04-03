import math
import time
from effects.base import PiEffect


class EffectSegments(PiEffect):
    """Rotating segments of alternating brightness."""
    name = "segments"

    def __init__(self):
        super().__init__()
        self.hue = 0
        self.auto_color = True
        self.segment_count = 6
        self.speed = 1.0  # rotations per second

    def next_frame(self, num_leds):
        t = time.time() * self.speed
        offset = t * num_leds / self.segment_count
        seg_len = num_leds / self.segment_count

        frame = []
        for i in range(num_leds):
            pos = (i + offset) % num_leds
            seg = int(pos / seg_len) % self.segment_count
            if seg % 2 == 0:
                # Smooth edges using sine
                phase = ((pos % seg_len) / seg_len) * math.pi
                val = int((math.sin(phase) * 0.7 + 0.3) * 253)
            else:
                val = 0
            frame.append(max(0, min(253, val)))

        return frame
