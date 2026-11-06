import time


class ThresholdAlerts:
    def __init__(self, policy, clock=time.monotonic):
        self.policy, self.clock = policy, clock
        self.armed = True
        self.last_alert = float("-inf")

    def observe(self, score):
        if score < self.policy.resetBelow:
            self.armed = True
        if (
            score >= self.policy.threshold
            and self.armed
            and self.clock() - self.last_alert >= self.policy.cooldownSeconds
        ):
            self.armed = False
            self.last_alert = self.clock()
            return {
                "type": "alert",
                "reason": "threshold_crossing",
                "score": score,
                "threshold": self.policy.threshold,
                "source": "threshold_policy",
            }
        return None
