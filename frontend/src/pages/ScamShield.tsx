import { useEffect, useState } from 'react'
import { apiUrl, errorText, getToken, post } from '../api/client'
import type { ScamChannel, ScamResult } from '../api/types'
import { ScamVerdictView } from '../components/ScamVerdict'
import { Bilingual, ErrorNote, ListenButton } from '../components/ui'
import { Icon } from '../lib/icons'
import { preparePhoto, uploadWithProgress } from '../lib/photo'
import { useRecorder } from '../lib/recorder'
import { takePendingShare } from '../lib/share'

// Scam Shield v2 for citizens and helpers: a message or link, a screenshot of a chat, or a phone call
// (what they said, or a voice note / call recording). The server decides; this screen only asks and shows.
// Content shared from WhatsApp/SMS ("Share" -> Sahara) arrives prefilled (see src/lib/share.ts).

type Mode = 'message' | 'screenshot' | 'call'

// Mock districts (match the seeded demo world) so the staff Scam Map can group reports.
const AREAS = ['Karachi East', 'Karachi South', 'Hyderabad', 'Sukkur', 'Multan', 'Lahore', 'Faisalabad', 'Quetta']
const DEMO_SCAM = 'Mubarak ho! Aap ki pension release ho gayi hai. Rs 5000 processing fee aaj hi jama karwain warna cancel. Link: pension-release.example.com'
const INTRO_UR = 'جو پیغام، لنک یا کال آئی ہے وہ یہاں دیں۔ ہم بتائیں گے کہ یہ دھوکہ تو نہیں۔'
const ON_CALL_UR = 'کیا اس وقت کوئی فون پر آپ کو یہ کرنے کو کہہ رہا ہے؟'

const MODES: { id: Mode; icon: string; ur: string; en: string }[] = [
  { id: 'message', icon: 'message', ur: 'پیغام یا لنک', en: 'Message or link' },
  { id: 'screenshot', icon: 'camera', ur: 'اسکرین شاٹ', en: 'Screenshot' },
  { id: 'call', icon: 'phone', ur: 'فون کال', en: 'Phone call' },
]

interface ScamShieldProps {
  onBack: () => void
}

export function ScamShield({ onBack }: ScamShieldProps) {
  const [mode, setMode] = useState<Mode>('message')
  const [text, setText] = useState('')
  const [sender, setSender] = useState('')
  const [onCall, setOnCall] = useState<boolean | null>(null)
  const [area, setArea] = useState('')
  const [image, setImage] = useState<File | null>(null)
  const [audio, setAudio] = useState<File | null>(null)
  const [result, setResult] = useState<ScamResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const recorder = useRecorder((file) => setAudio(file))

  // Shared from WhatsApp / SMS: fill the form once, then the share is deleted from the phone.
  useEffect(() => {
    let active = true
    void takePendingShare().then((shared) => {
      if (!active || !shared) return
      if (shared.text) setText(shared.text)
      if (shared.file?.type.startsWith('image/')) {
        setImage(shared.file)
        setMode('screenshot')
      } else if (shared.file) {
        setAudio(shared.file)
        setMode('call')
      }
    })
    return () => { active = false }
  }, [])

  async function upload(path: string, form: FormData): Promise<void> {
    if (sender.trim()) form.append('sender', sender.trim())
    if (onCall !== null) form.append('on_call_with_unknown', String(onCall))
    if (area) form.append('area', area)
    const sent = await uploadWithProgress<ScamResult>(apiUrl(path), form, getToken(), () => undefined)
    if (sent.ok && sent.data) setResult(sent.data)
    else setError(sent.message)
  }

  async function check(): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      if (mode === 'screenshot' && image) {
        const photo = await preparePhoto(image)
        const form = new FormData()
        form.append('file', photo.blob, 'screenshot.jpg')
        await upload('/api/v1/scam/check-image', form)
      } else if (mode === 'call' && audio && !text.trim()) {
        const form = new FormData()
        form.append('audio', audio, audio.name)
        form.append('kind', 'call_recording')
        await upload('/api/v1/scam/check-audio', form)
      } else {
        const channel: ScamChannel = mode === 'call' ? 'call' : 'sms'
        const body = { text: text.trim(), sender: sender.trim() || null, on_call_with_unknown: onCall, area: area || null, channel }
        setResult((await post<ScamResult>('/api/v1/scam/check', body)).data)
      }
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  async function pasteFromClipboard(): Promise<void> {
    try {
      setText((await navigator.clipboard.readText()).slice(0, 2000))
    } catch {
      setError('Paste is blocked on this phone. Long-press the box and choose Paste.')
    }
  }

  function startAgain(): void {
    setResult(null)
    setText('')
    setSender('')
    setOnCall(null)
    setImage(null)
    setAudio(null)
  }

  const ready = mode === 'screenshot' ? image !== null : mode === 'call' ? text.trim().length > 0 || audio !== null : text.trim().length > 0

  return (
    <section className="stack-lg" aria-labelledby="scam-title">
      <button type="button" className="btn btn-ghost btn-sm self-start" onClick={onBack}>
        <Icon name="arrow-left" size={20} />
        <span lang="ur" dir="rtl">واپس</span>
        <span>Back</span>
      </button>
      <div className="hello">
        <Bilingual as="h1" id="scam-title" ur="کیا یہ دھوکہ ہے؟" en="Scam Shield: is this a scam?" />
        <ListenButton audioKey="prompt_scam_intro" text={INTRO_UR} />
      </div>

      {!result && (
        <form className="form" onSubmit={(e) => { e.preventDefault(); void check() }}>
          <fieldset className="fieldset">
            <legend className="field-label">
              <span lang="ur" dir="rtl">کیا آیا ہے؟</span>
              <span>What did you get?</span>
            </legend>
            <div className="choice-grid choice-3">
              {MODES.map((m) => (
                <button key={m.id} type="button" className="choice" aria-pressed={mode === m.id} onClick={() => setMode(m.id)}>
                  <Icon name={m.icon} size={36} />
                  <span lang="ur" dir="rtl" className="choice-ur">{m.ur}</span>
                  <span className="choice-en">{m.en}</span>
                </button>
              ))}
            </div>
          </fieldset>

          {mode === 'call' && <OnCallQuestion value={onCall} onChange={setOnCall} />}

          {mode === 'screenshot' ? (
            <FilePick id="scam-image" accept="image/*" icon="camera" file={image} onPick={setImage}
              ur="پیغام کا اسکرین شاٹ چنیں" en="Choose a screenshot of the chat or SMS" />
          ) : (
            <label className="field">
              <span className="field-label">
                <Icon name={mode === 'call' ? 'phone' : 'message'} size={22} />
                <span lang="ur" dir="rtl">{mode === 'call' ? 'فون کرنے والے نے کیا کہا؟' : 'پیغام یا لنک یہاں لکھیں یا چسپاں کریں'}</span>
                <span>{mode === 'call' ? 'What did the caller say? (type it)' : 'Paste or type the message or link'}</span>
              </span>
              <textarea className="input" rows={5} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} />
            </label>
          )}

          {mode === 'message' && (
            <div className="row">
              <button type="button" className="btn btn-quiet btn-sm" onClick={() => void pasteFromClipboard()}>
                <span lang="ur" dir="rtl">چسپاں کریں</span> Paste
              </button>
              <button type="button" className="btn btn-quiet btn-sm" onClick={() => setText(DEMO_SCAM)}>Fill demo scam SMS (mock)</button>
            </div>
          )}

          {mode === 'call' && (
            <div className="stack">
              <p className="fine">Or send a voice note or call recording. We listen once and do not keep it.</p>
              <FilePick id="scam-audio" accept="audio/*,video/mp4,video/webm,video/3gpp" icon="speaker" file={audio} onPick={setAudio}
                ur="وائس نوٹ یا کال ریکارڈنگ چنیں" en="Choose a voice note or call recording" />
              {recorder.supported && (
                <button type="button" className={`btn btn-big ${recorder.recording ? 'btn-danger' : 'btn-secondary'}`}
                  onClick={() => void (recorder.recording ? recorder.stop() : recorder.start())}>
                  <Icon name="mic" size={24} />
                  <span lang="ur" dir="rtl">{recorder.recording ? 'روکیں' : 'بول کر بتائیں'}</span>
                  <span className="btn-en">{recorder.recording ? 'Stop recording' : 'Record what they said'}</span>
                </button>
              )}
              <ErrorNote message={recorder.error} />
            </div>
          )}

          <label className="field">
            <span className="field-label">
              <span lang="ur" dir="rtl">{mode === 'call' ? 'کس نمبر سے کال آئی؟ (اختیاری)' : 'کس نمبر سے آیا؟ (اختیاری)'}</span>
              <span>{mode === 'call' ? 'Number that called (optional)' : 'Sender number or name (optional)'}</span>
            </span>
            <span dir="ltr" className="ltr-island">
              <input className="input input-big input-digits" maxLength={40} autoComplete="off" value={sender} onChange={(e) => setSender(e.target.value)} />
            </span>
          </label>

          {mode !== 'call' && <OnCallQuestion value={onCall} onChange={setOnCall} />}

          <label className="field">
            <span className="field-label">
              <span lang="ur" dir="rtl">آپ کا ضلع (اختیاری)</span>
              <span>Your district (optional, helps warn others)</span>
            </span>
            <select className="input input-big" value={area} onChange={(e) => setArea(e.target.value)}>
              <option value="">Not saying</option>
              {AREAS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </label>

          <ErrorNote message={error} />
          <button type="submit" className="btn btn-primary btn-big" disabled={busy || !ready || recorder.recording}>
            <Icon name="shield" size={24} />
            <span lang="ur" dir="rtl">جانچ کریں</span>
            <span className="btn-en">{busy ? 'Checking…' : 'Check this message'}</span>
          </button>
          <p className="fine">We keep only a fingerprint of the message, not the text, picture, recording or number. Links are never opened.</p>
        </form>
      )}

      {result && <ScamVerdictView result={result} onAgain={startAgain} />}
    </section>
  )
}

interface OnCallQuestionProps {
  value: boolean | null
  onChange: (value: boolean) => void
}

function OnCallQuestion({ value, onChange }: OnCallQuestionProps) {
  return (
    <fieldset className="fieldset">
      <legend className="field-label">
        <span lang="ur" dir="rtl">{ON_CALL_UR}</span>
        <span>Is someone on the phone telling you to do this right now?</span>
      </legend>
      <div className="choice-grid choice-2">
        {[true, false].map((answer) => (
          <button key={String(answer)} type="button" className="choice" aria-pressed={value === answer} onClick={() => onChange(answer)}>
            <Icon name={answer ? 'phone' : 'close'} size={40} />
            <span lang="ur" dir="rtl" className="choice-ur">{answer ? 'ہاں' : 'نہیں'}</span>
            <span className="choice-en">{answer ? 'Yes' : 'No'}</span>
            {value === answer && <span className="choice-tick"><Icon name="check" size={22} /></span>}
          </button>
        ))}
      </div>
    </fieldset>
  )
}

interface FilePickProps {
  id: string
  accept: string
  icon: string
  file: File | null
  onPick: (file: File | null) => void
  ur: string
  en: string
}

function FilePick({ id, accept, icon, file, onPick, ur, en }: FilePickProps) {
  return (
    <div className="field">
      <label htmlFor={id} className="btn btn-secondary btn-big">
        <Icon name={icon} size={24} />
        <span lang="ur" dir="rtl">{ur}</span>
        <span className="btn-en">{file ? file.name : en}</span>
      </label>
      <input id={id} type="file" accept={accept} className="sr-only"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)} />
    </div>
  )
}
