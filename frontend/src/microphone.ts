export async function startMicrophone(
  socket: WebSocket,
  onLevel: (level: number) => void,
) {
  if (!navigator.mediaDevices?.getUserMedia)
    throw new Error(
      "Microphone capture needs HTTPS or localhost and a supported browser.",
    );
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    video: false,
  });
  let context: AudioContext | undefined;
  try {
    context = new AudioContext();
    await context.audioWorklet.addModule("/pcm-worklet.js");
    await context.resume();
    const source = context.createMediaStreamSource(stream),
      node = new AudioWorkletNode(context, "pcm-framer");
    const mute = context.createGain();
    mute.gain.value = 0;
    source.connect(node);
    node.connect(mute);
    mute.connect(context.destination);
    node.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
      if (socket.readyState !== WebSocket.OPEN) return;
      if (socket.bufferedAmount > 16384) {
        socket.close(1013, "Audio connection is too slow");
        return;
      }
      const samples = new Int16Array(event.data);
      let energy = 0;
      for (const sample of samples) energy += sample * sample;
      onLevel(Math.sqrt(energy / samples.length) / 32768);
      socket.send(event.data);
    };
    return async () => {
      node.port.onmessage = null;
      source.disconnect();
      node.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      await context?.close();
      onLevel(0);
    };
  } catch (error) {
    stream.getTracks().forEach((t) => t.stop());
    await context?.close();
    throw error;
  }
}
