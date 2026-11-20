import { Icon } from '../lib/icons'
import type { OutboxState } from '../lib/useOutbox'
import { ListenButton } from './ui'

// "Saved on this phone, waiting to send" strip on the citizen/helper home screen.

const WAITING_UR = 'آپ کا دعویٰ اس فون پر محفوظ ہے۔ سگنل آتے ہی یہ خود بھیج دیا جائے گا۔'
const FAILED_UR = 'محفوظ دعویٰ قبول نہیں ہوا۔ براہ کرم دوبارہ دیکھ کر بھیجیں۔'

export function OutboxStrip({ state }: { state: OutboxState }) {
  const { pending, online, syncing, failed, sendNow } = state
  return (
    <>
      {pending > 0 && (
        <div className="note note-attn outbox" role="status">
          <Icon name="cloud-off" size={24} />
          <span className="outbox-text">
            <span lang="ur" dir="rtl" className="note-ur">{WAITING_UR}</span>
            {pending === 1 ? '1 claim is' : `${pending} claims are`} saved on this phone, waiting to send.
            {!online && ' No signal right now: it will send by itself when signal returns.'}
          </span>
          <span className="outbox-actions">
            <ListenButton audioKey="outbox_waiting" text={WAITING_UR} compact />
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => void sendNow()} disabled={syncing}>
              <span lang="ur" dir="rtl">ابھی بھیجیں</span>
              <span className="btn-en">{syncing ? 'Sending…' : 'Send now'}</span>
            </button>
          </span>
        </div>
      )}
      {failed.map((message) => (
        <p key={message} className="note note-risk" role="alert">
          <Icon name="warning" size={20} />
          <span>
            <span lang="ur" dir="rtl" className="note-ur">{FAILED_UR}</span>
            A saved claim was not accepted: {message} Please check it and send it again.
          </span>
        </p>
      ))}
    </>
  )
}
