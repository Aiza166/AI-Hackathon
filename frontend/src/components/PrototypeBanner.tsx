// Shown on every page: the brief requires the project to be labelled a prototype.
export function PrototypeBanner() {
  return (
    <div className="prototype-banner" role="note" aria-label="Prototype notice">
      <strong className="prototype-tag">PROTOTYPE</strong>
      <span>Not an official government service. All people and records are simulated.</span>
      <span lang="ur" dir="rtl" className="prototype-ur">نمونہ ایپ، سرکاری سروس نہیں</span>
    </div>
  )
}
