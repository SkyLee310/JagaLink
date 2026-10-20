/** Two rising notes, in Hz, with the gap between their starts in seconds. */
const NOTES = [784, 1047]
const NOTE_GAP_S = 0.16

let context: AudioContext | null = null

/**
 * A short chime for a new alert (F6). Silent where the browser has no Web Audio or still blocks
 * sound because nobody has clicked the page yet.
 */
export function playCue(): void {
  if (typeof AudioContext === 'undefined') return
  try {
    const audio = (context ??= new AudioContext())
    if (audio.state === 'suspended') void audio.resume()
    NOTES.forEach((frequency, index) => {
      const at = audio.currentTime + index * NOTE_GAP_S
      const tone = audio.createOscillator()
      const volume = audio.createGain()
      tone.frequency.value = frequency
      volume.gain.setValueAtTime(0.0001, at)
      volume.gain.exponentialRampToValueAtTime(0.2, at + 0.02)
      volume.gain.exponentialRampToValueAtTime(0.0001, at + NOTE_GAP_S)
      tone.connect(volume).connect(audio.destination)
      tone.start(at)
      tone.stop(at + NOTE_GAP_S)
    })
  } catch {
    // A missing chime must never break the console; the card still stands out on screen.
  }
}
