// Phone-side photo preparation: shrink to at most 1568 px (what the server and Jev use),
// re-encode as JPEG (~150-300 KB instead of 3-5 MB on a weak connection), and give a
// quick quality hint before anything is uploaded. The server checks again; this only
// saves her a wasted upload.

export const MAX_SIDE = 1568
const JPEG_QUALITY = 0.85
const HINT_SIDE = 400
// Same idea as the server check (variance of the Laplacian), on a small grey copy.
const BLUR_HINT = 40
const DARK_HINT = 70

export type PhotoHint = 'ok' | 'blurry' | 'dark' | 'small'

export interface PreparedPhoto {
  blob: Blob
  width: number
  height: number
  hint: PhotoHint
  previewUrl: string
}

async function decode(file: Blob): Promise<ImageBitmap | HTMLImageElement> {
  if ('createImageBitmap' in window) {
    try {
      return await createImageBitmap(file, { imageOrientation: 'from-image' })
    } catch {
      // older engines: fall back to an <img>
    }
  }
  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    img.src = url
    await img.decode()
    return img
  } finally {
    URL.revokeObjectURL(url)
  }
}

function hintFor(canvas: HTMLCanvasElement, originalMin: number): PhotoHint {
  if (originalMin < 280) return 'small'
  const scale = HINT_SIDE / Math.max(canvas.width, canvas.height)
  const w = Math.max(1, Math.round(canvas.width * scale))
  const h = Math.max(1, Math.round(canvas.height * scale))
  const small = document.createElement('canvas')
  small.width = w
  small.height = h
  const ctx = small.getContext('2d', { willReadFrequently: true })
  if (!ctx) return 'ok'
  ctx.drawImage(canvas, 0, 0, w, h)
  const { data } = ctx.getImageData(0, 0, w, h)
  const grey = new Float32Array(w * h)
  for (let i = 0; i < w * h; i++) grey[i] = 0.299 * data[i * 4] + 0.587 * data[i * 4 + 1] + 0.114 * data[i * 4 + 2]
  const sorted = Array.from(grey).sort((a, b) => a - b)
  if (sorted[Math.floor(sorted.length * 0.9)] < DARK_HINT) return 'dark'
  let sum = 0
  let sumSq = 0
  let n = 0
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x
      const lap = grey[i - 1] + grey[i + 1] + grey[i - w] + grey[i + w] - 4 * grey[i]
      sum += lap
      sumSq += lap * lap
      n++
    }
  }
  const variance = n ? sumSq / n - (sum / n) ** 2 : 0
  return variance < BLUR_HINT ? 'blurry' : 'ok'
}

export async function preparePhoto(file: Blob): Promise<PreparedPhoto> {
  const source = await decode(file)
  const scale = Math.min(1, MAX_SIDE / Math.max(source.width, source.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(source.width * scale)
  canvas.height = Math.round(source.height * scale)
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('This phone cannot prepare photos')
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height)
  const hint = hintFor(canvas, Math.min(source.width, source.height))
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Could not prepare the photo'))), 'image/jpeg', JPEG_QUALITY),
  )
  return { blob, width: canvas.width, height: canvas.height, hint, previewUrl: URL.createObjectURL(blob) }
}

export interface UploadResult<T> {
  ok: boolean
  status: number
  data: T | null
  message: string
}

// XHR (not fetch) so we can show upload progress on a slow connection.
export function uploadWithProgress<T>(url: string, form: FormData, token: string | null, onProgress: (fraction: number) => void): Promise<UploadResult<T>> {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total)
    }
    xhr.onload = () => {
      type Body = { success?: boolean; data?: T; error?: { message?: string } }
      let body: Body | null
      try {
        body = JSON.parse(xhr.responseText) as Body
      } catch {
        body = null
      }
      const ok = xhr.status >= 200 && xhr.status < 300 && Boolean(body?.success)
      resolve({ ok, status: xhr.status, data: body?.data ?? null, message: body?.error?.message ?? (ok ? '' : 'Upload failed') })
    }
    xhr.onerror = () => resolve({ ok: false, status: 0, data: null, message: 'No connection. Please try again when you have signal.' })
    xhr.send(form)
  })
}
