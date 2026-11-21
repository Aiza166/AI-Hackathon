import { Icon } from '../lib/icons'
import { isConsentProblem, type OutboxRow } from '../lib/outbox'
import type { OutboxState } from '../lib/useOutbox'
import { ListenButton } from './ui'

// "Saved on this phone, waiting to send" strip on the citizen/helper home screen.

const WAITING_UR = 'آپ کا دعویٰ اس فون پر محفوظ ہے۔ سگنل آتے ہی یہ خود بھیج دیا جائے گا۔'
const LOGIN_UR = 'دعویٰ بھیجنے کے لیے دوبارہ سائن ان کریں۔ آپ کا دعویٰ اس فون پر محفوظ ہے۔'
const PAUSED_UR = 'کئی بار کوشش ہو چکی ہے۔ "ابھی بھیجیں" دبائیں۔'
const FAILED_UR = 'یہ دعویٰ قبول نہیں ہوا۔ کھول کر ٹھیک کریں اور دوبارہ بھیجیں۔'
const CONSENT_UR = 'اس خاندان نے آپ کو اجازت نہیں دی یا واپس لے لی۔ پہلے ان سے اجازت لیں۔'
const DISCARDED_UR = 'اس فون پر محفوظ کچھ معلومات اب نہیں کھل سکتیں، اس لیے ہٹا دی گئیں۔ دعویٰ دوبارہ بھریں۔'
const DUPLICATE_UR = 'یہ دعویٰ پہلے سے ہمارے پاس ہے۔ دوبارہ نہیں بھیجا گیا۔'

interface OutboxStripProps {
  state: OutboxState
  showWho: boolean // Helper Mode: name the family each claim is for
  onSignInAgain: () => void
  onOpenFix: (row: OutboxRow) => void
}

function names(rows: OutboxRow[]): string {
  return [...new Set(rows.map((r) => r.subjectName))].join(', ')
}

export function OutboxStrip({ state, showWho, onSignInAgain, onOpenFix }: OutboxStripProps) {
  const { queued, failed, needsLogin, paused, online, syncing, notices, discarded, dismissDiscarded, sendNow, dismissNotice, remove } = state
  return (
    <>
      {discarded > 0 && (
        <div className="note note-attn outbox" role="alert">
          <Icon name="warning" size={22} />
          <span className="outbox-text">
            <span lang="ur" dir="rtl" className="note-ur">{DISCARDED_UR}</span>
            {discarded === 1 ? '1 saved item' : `${discarded} saved items`} on this phone could no longer be opened (the tab was closed or you signed out), so {discarded === 1 ? 'it was' : 'they were'} removed. Please fill in the claim again.
          </span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={dismissDiscarded}>
            <span lang="ur" dir="rtl">ٹھیک ہے</span>
            <span className="btn-en">OK</span>
          </button>
        </div>
      )}
      {queued.length > 0 && (
        <div className="note note-attn outbox" role="status">
          <Icon name="cloud-off" size={24} />
          <span className="outbox-text">
            <span lang="ur" dir="rtl" className="note-ur">{needsLogin ? LOGIN_UR : WAITING_UR}</span>
            {queued.length === 1 ? '1 claim is' : `${queued.length} claims are`} saved on this phone, waiting to send.
            {showWho && <> Waiting for: <strong>{names(queued)}</strong>.</>}
            {needsLogin && ' Sign in again to send it.'}
            {!needsLogin && !online && ' No signal right now: it will send by itself when signal returns.'}
            {paused && (
              <>
                <span lang="ur" dir="rtl" className="note-ur">{PAUSED_UR}</span>
                {' Automatic tries have stopped after several server errors. Tap Send now to try again.'}
              </>
            )}
          </span>
          <span className="outbox-actions">
            <ListenButton audioKey={needsLogin ? 'outbox_login' : 'outbox_waiting'} text={needsLogin ? LOGIN_UR : WAITING_UR} compact />
            {needsLogin ? (
              <button type="button" className="btn btn-primary btn-sm" onClick={onSignInAgain}>
                <span lang="ur" dir="rtl">دوبارہ سائن ان</span>
                <span className="btn-en">Sign in again to send</span>
              </button>
            ) : (
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => void sendNow()} disabled={syncing}>
                <span lang="ur" dir="rtl">ابھی بھیجیں</span>
                <span className="btn-en">{syncing ? 'Sending…' : 'Send now'}</span>
              </button>
            )}
          </span>
        </div>
      )}
      {failed.map((row) => {
        const consent = isConsentProblem(row)
        return (
          <div key={row.id} className="note note-risk outbox" role="alert">
            <Icon name={consent ? 'lock' : 'warning'} size={22} />
            <span className="outbox-text">
              <span lang="ur" dir="rtl" className="note-ur">{consent ? CONSENT_UR : FAILED_UR}</span>
              {showWho && <><strong>{row.subjectName}</strong>: </>}
              {consent
                ? 'This family has not shared access with you, or withdrew it. Ask her to share access again from her own phone, then open the claim and send it.'
                : `A saved claim was not accepted: ${row.lastError ?? 'unknown reason'} Open it, fix it and send it again.`}
            </span>
            <span className="outbox-actions">
              <button type="button" className="btn btn-primary btn-sm" onClick={() => onOpenFix(row)}>
                <span lang="ur" dir="rtl">کھولیں اور ٹھیک کریں</span>
                <span className="btn-en">Open and fix</span>
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => void remove(row)}>
                <span lang="ur" dir="rtl">ہٹا دیں</span>
                <span className="btn-en">Remove</span>
              </button>
            </span>
          </div>
        )
      })}
      {notices.map((notice, i) => (
        <div key={`${notice.reference ?? 'dup'}-${i}`} className="note note-info outbox" role="status">
          <Icon name="check" size={22} />
          <span className="outbox-text">
            <span lang="ur" dir="rtl" className="note-ur">{DUPLICATE_UR}</span>
            {showWho && <><strong>{notice.subjectName}</strong>: </>}
            This claim is already with us{notice.reference ? <> (reference <strong>{notice.reference}</strong>)</> : ''}. Nothing was filed twice.
          </span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => dismissNotice(notice)}>
            <span lang="ur" dir="rtl">ٹھیک ہے</span>
            <span className="btn-en">OK</span>
          </button>
        </div>
      ))}
    </>
  )
}
