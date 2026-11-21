import { useEffect, useRef, useState } from 'react'

// Record a short voice note in the browser (MediaRecorder: WebM/Opus on Chrome, MP4 on Safari).
// The server converts it to WAV for speech-to-text. Hidden when the phone has no MediaRecorder.

export const MAX_RECORD_MS = 55_000 // the speech service hears at most about a minute

export interface Recorder {
  supported: boolean
  recording: boolean
  error: string | null
  start: () => Promise<void>
  stop: () => void
}

export function useRecorder(onDone: (audio: File) => void): Recorder {
  const [recording, setRecording] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const timerRef = useRef<number | null>(null)
  const supported = typeof window !== 'undefined' && 'MediaRecorder' in window && Boolean(navigator.mediaDevices?.getUserMedia)

  function stop(): void {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    timerRef.current = null
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }

  async function start(): Promise<void> {
    setError(null)
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setError('Microphone permission was not given. You can upload a recording instead.')
      return
    }
    const chunks: Blob[] = []
    const recorder = new MediaRecorder(stream)
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data) }
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop())
      setRecording(false)
      const type = recorder.mimeType || 'audio/webm'
      const ext = type.includes('mp4') ? 'm4a' : type.includes('ogg') ? 'ogg' : 'webm'
      if (chunks.length > 0) onDone(new File(chunks, `voice-note.${ext}`, { type: type.split(';')[0] }))
    }
    recorderRef.current = recorder
    recorder.start()
    setRecording(true)
    timerRef.current = window.setTimeout(stop, MAX_RECORD_MS)
  }

  useEffect(() => stop, [])
  return { supported, recording, error, start, stop }
}
