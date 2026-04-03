import time
import numpy
from effects.base import PiEffect


class EffectSegments(PiEffect):
    """Rotating segments of alternating brightness."""
    name = "segments"

    def __init__(self):
        super().__init__()
        self.hue = 0
        self.auto_color = True
        self.segment_count = 6
        self.speed = 1.0

    def next_frame(self, num_leds):
        t = time.time() * self.speed
        offset = t * num_leds / self.segment_count
        seg_len = num_leds / self.segment_count

        i = numpy.arange(num_leds, dtype=numpy.float64)
        pos = (i + offset) % num_leds
        seg = (pos / seg_len).astype(numpy.int32) % self.segment_count

        phase = (pos % seg_len) / seg_len * numpy.pi
        vals = ((numpy.sin(phase) * 0.7 + 0.3) * 253).astype(numpy.int32)

        # Zero out odd segments
        vals[seg % 2 != 0] = 0

        return numpy.clip(vals, 0, 253).tolist()
