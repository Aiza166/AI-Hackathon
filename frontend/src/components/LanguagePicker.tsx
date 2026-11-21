import { LANGS } from '../lib/lang'
import { useLang } from '../lib/useLang'
import { Local } from './ui'

// Language choice for citizen screens: Urdu (default), Sindhi, Punjabi (Shahmukhi).
// Each name is written in its own script so a reader recognises her language without English.
// Sindhi and Punjabi always carry the "machine-assisted, to be reviewed" label; audio stays Urdu.

export function LanguagePicker() {
  const { lang, setLang } = useLang()
  return (
    <section className="lang-picker" aria-labelledby="lang-title">
      <h2 id="lang-title" className="lang-title">
        <Local k="lang.title" ur="زبان" className="lang-title-ur" />
        <span className="lang-title-en" lang="en">Language</span>
      </h2>
      <div className="segmented lang-options" role="group" aria-labelledby="lang-title">
        {LANGS.map((l) => (
          <button
            key={l.id}
            type="button"
            className="segment"
            aria-pressed={lang === l.id}
            onClick={() => setLang(l.id)}
          >
            <span lang={l.tag} dir="rtl" className="segment-ur">{l.native}</span>
            <span className="segment-en" lang="en">{l.en}</span>
          </button>
        ))}
      </div>
      {lang !== 'ur' && (
        <p className="fine lang-note" role="note">
          <Local k="lang.note" ur="مشینی مدد سے ترجمہ، ابھی جانچ باقی ہے۔ آواز اردو میں ہے۔" className="lang-note-local" />
          <span lang="en"> Machine-assisted translation, to be reviewed. Audio stays in Urdu.</span>
        </p>
      )}
    </section>
  )
}
