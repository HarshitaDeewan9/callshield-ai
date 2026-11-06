/* Microphone PCM framing; no recording is retained by this processor. */
class PCMFramer extends AudioWorkletProcessor {
  constructor() {
    super();
    this.phase = 0;
    this.sum = 0;
    this.count = 0;
    this.frame = new Int16Array(512);
    this.position = 0;
  }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    for (const sample of channel) {
      this.sum += sample;
      this.count++;
      this.phase += 16000;
      if (this.phase >= sampleRate) {
        const value = Math.max(-1, Math.min(1, this.sum / this.count));
        this.frame[this.position++] = Math.round(
          value * (value < 0 ? 32768 : 32767),
        );
        this.phase -= sampleRate;
        this.sum = 0;
        this.count = 0;
        if (this.position === 512) {
          this.port.postMessage(this.frame.buffer, [this.frame.buffer]);
          this.frame = new Int16Array(512);
          this.position = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("pcm-framer", PCMFramer);
