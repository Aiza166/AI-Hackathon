// Read a prompt aloud. Prefer a pre-recorded Urdu clip (/audio/<key>.mp3, cached by the PWA);
// fall back to the browser's speech engine if no clip exists yet.

export async function speak(audioKey: string, fallbackText: string): Promise<void> {
  const clip = new Audio(`/audio/${audioKey}.mp3`)
  try {
    await clip.play()
    return
  } catch {
    // no clip yet: fall through to speech synthesis
  }
  if (!('speechSynthesis' in window)) return
  const utterance = new SpeechSynthesisUtterance(fallbackText)
  utterance.lang = 'ur-PK'
  window.speechSynthesis.cancel()
  window.speechSynthesis.speak(utterance)
}
