import math
import struct


class AcousticMetrics:
    """Descriptive PCM measurements only. No emotion, deception, identity or fraud inference."""

    def __init__(self):
        self.samples = self.frames = self.clipped = 0
        self.energy = 0
        self.peak = 0

    def add(self, frame):
        values = struct.unpack("<512h", frame)
        self.samples += len(values)
        self.frames += 1
        self.energy += sum(v * v for v in values)
        self.peak = max(self.peak, max(abs(v) for v in values))
        self.clipped += sum(abs(v) >= 32760 for v in values)

    def view(self):
        rms = math.sqrt(self.energy / self.samples) / 32768 if self.samples else 0
        return {
            "source": "pcm_measurement",
            "fraudInference": False,
            "usedByRiskModel": False,
            "samples": self.samples,
            "durationMs": self.samples / 16,
            "rmsDbfs": round(20 * math.log10(rms), 2) if rms else None,
            "peakAmplitude": round(self.peak / 32768, 4),
            "clippingFraction": round(self.clipped / self.samples, 6) if self.samples else 0,
            "toneInference": "not_available",
        }
