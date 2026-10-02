import { useEffect, useMemo, useRef, useState } from 'react'
import type { DocInfo, Unit, Voice } from '../shared/types'
import { Player } from './player'
import logo from './assets/logo.svg'

type PageMode = 'pdf' | 'printed'
type Theme = 'light' | 'dark' | 'yellow' | 'green' | 'blue'

const FONTS: Record<string, { label: string; css: string }> = {
  serif: { label: 'Classic serif', css: "Georgia, 'Times New Roman', serif" },
  sans: { label: 'Clean sans', css: "-apple-system, 'Helvetica Neue', Arial, sans-serif" },
  rounded: { label: 'Soft & round', css: "ui-rounded, 'Arial Rounded MT Bold', 'Avenir Next', sans-serif" },
  easy: { label: 'Easy-read (Verdana)', css: "Verdana, Geneva, sans-serif" },
  cute: { label: 'Cute handwriting', css: "'Chalkboard SE', 'Marker Felt', 'Comic Sans MS', cursive" },
  mono: { label: 'Typewriter', css: "Menlo, 'Courier New', monospace" }
}
const THEMES: [Theme, string][] = [['light', '🌸 Light'], ['dark', '🌙 Dark'], ['yellow', '🌼 Yellow'], ['green', '🌿 Green'], ['blue', '💧 Blue']]

function stored<T extends string | number>(key: string, fallback: T): T {
  try { const v = localStorage.getItem(key); if (v !== null) return (typeof fallback === 'number' ? Number(v) : v) as T } catch {}
  return fallback
}

export default function App() {
  const [info, setInfo] = useState<DocInfo | null>(null)
  const [path, setPath] = useState('')
  const [units, setUnits] = useState<Unit[]>([])
  const [voices, setVoices] = useState<Voice[]>([])
  const [voice, setVoice] = useState('')
  const [rate, setRate] = useState(1)
  const [msg, setMsg] = useState('Open a PDF to begin.')
  const [skip, setSkip] = useState({ skip_footnotes: true, skip_citations: true, skip_captions: true, skip_references: true })
  const [pageMode, setPageMode] = useState<PageMode>('pdf')
  const [secIdx, setSecIdx] = useState(0)
  const [from, setFrom] = useState('1')
  const [to, setTo] = useState('1')
  const [secFrom, setSecFrom] = useState(0)
  const [secTo, setSecTo] = useState(0)
  const [sel, setSel] = useState<{ idx: number; text: string } | null>(null)
  const [notes, setNotes] = useState('')
  const [theme, setTheme] = useState<Theme>(() => stored<Theme>('theme', 'light'))
  const [font, setFont] = useState<string>(() => stored<string>('font', 'serif'))
  const [fsize, setFsize] = useState<number>(() => stored<number>('fsize', 19))
  const [, force] = useState(0)
  const player = useMemo(() => { const p = new Player(); p.onChange = () => force((n) => n + 1); return p }, [])
  const curRef = useRef<HTMLSpanElement>(null)
  const readerRef = useRef<HTMLDivElement>(null)
  const [follow, setFollow] = useState(true)
  const range = useRef<{ start: number; end: number } | null>(null)

  const off = info?.page_offset ?? 0
  const toIdx = (n: number) => (pageMode === 'printed' ? n + off : n - 1)
  const fromIdx = (i: number) => (pageMode === 'printed' ? i - off : i + 1)
  const isEpub = info?.kind === 'epub'
  const where = (i: number) => (isEpub ? info?.seg_titles[i] ?? '' : `page ${fromIdx(i)}`)

  useEffect(() => {
    window.api.rpc('voices').then((v: Voice[]) => { setVoices(v); if (v[0]) { setVoice(v[0].id); player.setVoice(v[0].id) } })
  }, [])
  useEffect(() => {
    const c = readerRef.current, el = curRef.current
    if (!follow || !c || !el || !player.playing) return
    const top = c.scrollTop + (el.getBoundingClientRect().top - c.getBoundingClientRect().top) - c.clientHeight * 0.3
    c.scrollTo({ top, behavior: 'smooth' })
  }, [player.idx, follow])
  useEffect(() => { player.setRate(rate) }, [rate])
  useEffect(() => { try { localStorage.setItem('theme', theme); localStorage.setItem('font', font); localStorage.setItem('fsize', String(fsize)) } catch {} }, [theme, font, fsize])
  useEffect(() => { if (path) { try { localStorage.setItem('notes:' + path, notes) } catch {} } }, [notes, path])

  async function loadRange(start: number, end: number, s = skip, playFrom: number | null = 0) {
    const u: Unit[] = await window.api.rpc('units', { start, end, settings: s })
    range.current = { start, end }
    setUnits(u); player.load(u)
    const span = isEpub ? `“${where(start)}”${end > start ? ` → “${where(end)}”` : ''}`
      : `pages ${fromIdx(start)}–${fromIdx(end)} (${pageMode === 'printed' ? 'printed' : 'PDF'} numbers)`
    setMsg(u.length ? `Reading ${span} · ${u.length} sentences`
      : `Nothing readable in ${span}${isEpub ? '' : ' (scanned pages need OCR, which isn\'t built yet)'}.`)
    if (u.length && playFrom !== null) player.start(playFrom)
  }

  async function openBook(kind: 'pdf' | 'epub') {
    const p = await window.api.openBook(kind)
    if (!p) return
    setMsg('Analysing document…')
    const i: DocInfo = await window.api.rpc('load', { path: p })
    setInfo(i); setPath(p); setUnits([]); player.load([]); range.current = null
    setSecIdx(0); setSecFrom(0); setSecTo(Math.max(0, i.sections.length - 1)); setFrom('1'); setTo(String(Math.min(10, i.n_pages)))
    try { setNotes(localStorage.getItem('notes:' + p) ?? '') } catch { setNotes('') }
    setMsg(`${i.kind === 'epub' ? 'EPUB' : `${i.n_pages} pages`} · ${i.sections.length} sections found${i.scanned_pages.length ? ` · ${i.scanned_pages.length} scanned pages (OCR not yet supported)` : ''}`)
  }

  function readSection() {
    const s = info?.sections[secIdx]
    if (s) loadRange(s.start, s.end)
  }

  function readSections() {
    if (!info?.sections.length) return
    const a = Math.min(secFrom, secTo), b = Math.max(secFrom, secTo)
    loadRange(info.sections[a].start, Math.max(...info.sections.slice(a, b + 1).map((x) => x.end)))
  }

  function readPages() {
    if (!info) return
    const a = parseInt(from), b = parseInt(to || from)
    if (isNaN(a)) { setMsg('Enter a start page number.'); return }
    let s = toIdx(a), e = toIdx(isNaN(b) ? a : b)
    if (e < s) [s, e] = [e, s]
    s = Math.max(0, Math.min(info.n_pages - 1, s)); e = Math.max(0, Math.min(info.n_pages - 1, e))
    loadRange(s, e)
  }

  function toggleSkip(k: keyof typeof skip) {
    const s = { ...skip, [k]: !skip[k] }
    setSkip(s)
    if (range.current) loadRange(range.current.start, range.current.end, s, null)
  }

  // --- selecting text to read from / quote ---
  function captureSelection() {
    const s = window.getSelection()
    if (!s || s.isCollapsed || !s.anchorNode) { setSel(null); return }
    const n = s.anchorNode.nodeType === 3 ? s.anchorNode.parentElement : (s.anchorNode as Element)
    const el = n?.closest('[data-idx]') as HTMLElement | null
    if (!el) { setSel(null); return }
    setSel({ idx: Number(el.dataset.idx), text: s.toString().trim() })
  }
  function readFromSelection() {
    if (!sel) return
    window.getSelection()?.removeAllRanges()
    player.start(sel.idx); setSel(null)
  }
  function clickUnit(i: number) {
    if (window.getSelection()?.toString()) return // user is selecting, not clicking
    player.start(i)
  }
  function quoteToNotes() {
    if (!sel) return
    const page = units[sel.idx]?.page
    setNotes((n) => `${n}${n && !n.endsWith('\n') ? '\n' : ''}“${sel.text}” (${isEpub ? (page !== undefined ? where(page) : '?') : `p. ${page !== undefined ? fromIdx(page) : '?'}`})\n`)
    window.getSelection()?.removeAllRanges(); setSel(null)
  }
  function downloadNotes() {
    const base = (path.split(/[\\/]/).pop() || 'notes').replace(/\.(pdf|epub)$/i, '')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([notes], { type: 'text/plain;charset=utf-8' }))
    a.download = `${base}-notes.txt`
    a.click()
  }

  const ready = !!info
  return (
    <div className="app" data-theme={theme} style={{ '--reader-font': (FONTS[font] ?? FONTS.serif).css, '--reader-size': `${fsize}px` } as React.CSSProperties}>
      <aside>
        <div className="brand"><img src={logo} alt="" className="logo" /><div>Read4me<small>your nerdy reading buddy</small></div></div>
        <div className="openrow">
          <button className="primary" onClick={() => openBook('pdf')}>📕 Open PDF</button>
          <button className="primary" onClick={() => openBook('epub')}>📗 Open EPUB</button>
        </div>
        <div className="file">{path.split(/[\\/]/).pop()}</div>

        <h3>Look & feel</h3>
        <div className="themes">
          {THEMES.map(([t, label]) => <button key={t} className={theme === t ? 'on' : ''} onClick={() => setTheme(t)}>{label}</button>)}
        </div>
        <select value={font} onChange={(e) => setFont(e.target.value)}>
          {Object.entries(FONTS).map(([k, f]) => <option key={k} value={k}>{f.label}</option>)}
        </select>
        <label>Text size {fsize}px<input type="range" min="14" max="34" step="1" value={fsize} onChange={(e) => setFsize(+e.target.value)} /></label>

        <h3>Read a chapter / section</h3>
        <select value={secIdx} disabled={!ready || !info?.sections.length} onChange={(e) => setSecIdx(+e.target.value)}>
          {info?.sections.map((s, i) => (
            <option key={i} value={i}>{'  '.repeat(s.level - 1)}{s.title}{isEpub ? '' : ` (p${fromIdx(s.start)})`}</option>
          ))}
          {ready && !info?.sections.length && <option>No chapters detected — use pages</option>}
        </select>
        <button disabled={!ready || !info?.sections.length} onClick={readSection}>📚 Read this chapter</button>

        {isEpub ? (
          <>
            <h3>Read several sections</h3>
            <select value={secFrom} disabled={!ready} onChange={(e) => setSecFrom(+e.target.value)}>
              {info?.sections.map((x, k) => <option key={k} value={k}>From: {x.title}</option>)}
            </select>
            <select value={secTo} disabled={!ready} onChange={(e) => setSecTo(+e.target.value)}>
              {info?.sections.map((x, k) => <option key={k} value={k}>To: {x.title}</option>)}
            </select>
            <button disabled={!ready} onClick={readSections}>📖 Read these sections</button>
          </>
        ) : (
          <>
        <h3>Read pages</h3>
          <div className="pages">
            <input type="number" min={1} value={from} disabled={!ready} onChange={(e) => setFrom(e.target.value)} />
            <span>to</span>
            <input type="number" min={1} value={to} disabled={!ready} onChange={(e) => setTo(e.target.value)} />
          </div>
          <label className="inline"><input type="radio" checked={pageMode === 'pdf'} onChange={() => setPageMode('pdf')} /> PDF page numbers</label>
          <label className="inline"><input type="radio" checked={pageMode === 'printed'} onChange={() => setPageMode('printed')} /> Printed page numbers{info && info.page_offset !== 0 ? ` (offset ${info.page_offset})` : ''}</label>
          <button disabled={!ready} onClick={readPages}>📄 Read these pages</button>
          </>
        )}

        <h3>Skip while reading</h3>
        {(['skip_footnotes', 'skip_citations', 'skip_captions', 'skip_references'] as const).map((k) => (
          <label key={k}><input type="checkbox" checked={skip[k]} onChange={() => toggleSkip(k)} /> {k.replace('skip_', '')}</label>
        ))}

        <h3>Voice</h3>
        <select value={voice} onChange={(e) => { setVoice(e.target.value); player.setVoice(e.target.value) }}>
          {voices.map((v) => <option key={v.id} value={v.id}>{v.name}{v.quality !== 'standard' ? ` ★ ${v.quality}` : ''}</option>)}
        </select>
        <label>Speed {rate.toFixed(2)}×<input type="range" min="0.7" max="2" step="0.05" value={rate} onChange={(e) => setRate(+e.target.value)} /></label>
      </aside>

      <main>
        <div className="status">{msg}</div>
        <div className="reader" ref={readerRef} onMouseUp={captureSelection}>
          {units.length === 0 && <p className="hint">Open a PDF or EPUB, choose a chapter (or page range for PDFs) on the left, then press Read. While reading you can click any sentence — or highlight text — to continue from there.</p>}
          {units.map((u, i) => (
            <span key={i}>
              {(i === 0 || units[i - 1].page !== u.page) && <span className="pagemark">{isEpub ? where(u.page) : `Page ${fromIdx(u.page)}`}</span>}
              <span data-idx={i} ref={i === player.idx ? curRef : undefined}
                className={`${u.kind} ${i === player.idx ? 'cur' : ''}`} onClick={() => clickUnit(i)}>{u.text}</span>{' '}
            </span>
          ))}
        </div>
        {sel && (
          <div className="selbar">
            <button onClick={readFromSelection}>▶ Read from here</button>
            <button onClick={quoteToNotes}>＋ Add to notes</button>
          </div>
        )}
      </main>

      <section className="notes">
        <h3>📝 Notes</h3>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Write notes here. Highlight text in the reader and press “Add to notes” to quote it with its page number. Notes are saved automatically for each book." />
        <button onClick={downloadNotes} disabled={!notes.trim()}>⬇ Download notes (.txt)</button>
      </section>

      <footer className="player">
        <div className="btns">
          <button onClick={() => player.step(-1)} disabled={!units.length} title="Previous sentence">⏮</button>
          <button className="primary" onClick={() => player.toggle()} disabled={!units.length}>
            {player.playing ? '⏸ Pause' : player.isPaused ? '▶ Resume' : '▶ Play'}
          </button>
          <button onClick={() => player.step(1)} disabled={!units.length} title="Next sentence">⏭</button>
          <button onClick={() => player.stop()} disabled={!units.length} title="Stop">⏹</button>
        </div>
        <div className="now">
          <div className="nowtext">{units[player.idx]?.text ?? 'Nothing playing'}</div>
          <div className="bar"><div style={{ width: units.length ? `${((player.idx + 1) / units.length) * 100}%` : 0 }} /></div>
        </div>
        <div className="meta">
          {units.length ? `${player.idx + 1} / ${units.length}${isEpub ? '' : ` · p${fromIdx(units[player.idx]?.page ?? 0)}`}` : ''}
          <label className="inline"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> Follow text</label>
        </div>
      </footer>
    </div>
  )
}
