import type { Unit } from '../shared/types'

const PAUSE_SENTENCE = 180, PAUSE_PARAGRAPH = 550, PAUSE_HEADING = 800
const PREFETCH = 3

/**
 * Plays units sequentially with prefetching and natural pauses.
 * pause() freezes mid-sentence; resume() continues exactly where it stopped.
 * start(i) begins (or restarts) from any sentence, discarding any previous run.
 */
export class Player {
  private units: Unit[] = []
  private cache = new Map<number, Promise<string>>()
  private gen = 0
  private audio = new Audio()
  private gateWaiters: (() => void)[] = []
  private endResolve: (() => void) | null = null
  private inSentence = false
  private running = false
  private paused = false
  idx = 0
  rate = 1
  voice = ''
  onChange: () => void = () => {}

  get playing() { return this.running && !this.paused }
  get isPaused() { return this.running && this.paused }

  load(units: Unit[]) { this.halt(); this.units = units; this.idx = 0; this.cache.clear(); this.onChange() }
  setVoice(v: string) { if (v !== this.voice) { this.voice = v; this.cache.clear() } }
  setRate(r: number) { this.rate = r; this.audio.defaultPlaybackRate = r; this.audio.playbackRate = r }

  private fetch(i: number): Promise<string> | undefined {
    if (i >= this.units.length) return
    if (!this.cache.has(i)) {
      const p = window.api.rpc('speak', { text: this.units[i].text, voice: this.voice }).then(
        (b64: string) => URL.createObjectURL(new Blob([Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))], { type: 'audio/wav' }))
      )
      p.catch(() => this.cache.delete(i))
      this.cache.set(i, p)
    }
    return this.cache.get(i)
  }

  private async gate(g: number) {
    while (this.paused && g === this.gen) await new Promise<void>((r) => this.gateWaiters.push(r))
  }

  private halt() {
    this.gen++
    this.running = false
    this.paused = false
    this.inSentence = false
    this.audio.pause()
    this.gateWaiters.splice(0).forEach((f) => f())
    this.endResolve?.(); this.endResolve = null
  }

  async start(from = 0) {
    if (!this.units.length) return
    this.halt()
    const g = this.gen
    this.running = true
    this.idx = Math.max(0, Math.min(this.units.length - 1, from))
    for (let i = this.idx; i < this.units.length; i++) {
      this.idx = i
      this.onChange()
      for (let k = 1; k <= PREFETCH; k++) this.fetch(i + k)
      let url: string
      try { url = await this.fetch(i)! } catch { continue }
      await this.gate(g)
      if (g !== this.gen) return
      this.audio.src = url
      this.audio.playbackRate = this.rate
      this.inSentence = true
      const ended = new Promise<void>((res) => { this.endResolve = res; this.audio.onended = () => res() })
      this.audio.play().catch(() => {})
      await ended
      this.inSentence = false
      if (g !== this.gen) return
      const cur = this.units[i], next = this.units[i + 1]
      const gap = cur.kind === 'heading' ? PAUSE_HEADING : next && next.paragraph !== cur.paragraph ? PAUSE_PARAGRAPH : PAUSE_SENTENCE
      await new Promise((r) => setTimeout(r, gap / this.rate))
      await this.gate(g)
      if (g !== this.gen) return
    }
    if (g === this.gen) { this.running = false; this.onChange() }
  }

  pause() {
    if (!this.running || this.paused) return
    this.paused = true
    this.audio.pause()
    this.onChange()
  }

  resume() {
    if (!this.running) { this.start(this.idx); return }
    if (!this.paused) return
    this.paused = false
    if (this.inSentence) this.audio.play().catch(() => {})
    this.gateWaiters.splice(0).forEach((f) => f())
    this.onChange()
  }

  toggle() { this.running ? (this.paused ? this.resume() : this.pause()) : this.start(this.idx) }
  stop() { this.halt(); this.onChange() }
  seek(i: number) { this.start(i) }
  step(d: number) { this.start(this.idx + d) }
}
