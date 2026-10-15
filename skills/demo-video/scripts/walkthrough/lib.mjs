// Recording kit: headless Chromium at DPR 2 (or a new tab in a signed-in Chrome over CDP), CDP screencast
// frames to disk, an in-page cursor, human-paced mouse / keyboard helpers, an event log (captions, tips,
// fast-forward, cuts) for the edit, and actions.json (clicks, typing, their targets and results) for the camera.
import { appendFileSync, existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { createRequire } from 'node:module'

/** PLAYWRIGHT_MODULE (a path or package name), else `playwright` from here, setup.sh's shared install, or the work dir. */
async function loadPlaywright() {
  const shared = path.join(process.env.DEMO_NODE_DIR ?? path.join(os.homedir(), '.cache/demo-video/node'), 'node_modules/playwright/index.mjs')
  const tries = [process.env.PLAYWRIGHT_MODULE, 'playwright', existsSync(shared) && shared].filter(Boolean)
  for (const t of tries) {
    try {
      return await import(t)
    } catch {}
  }
  try {
    return await import(createRequire(path.join(process.cwd(), 'x.js')).resolve('playwright'))
  } catch {}
  throw new Error('Playwright not found: run the skill\'s scripts/setup.sh, or set PLAYWRIGHT_MODULE')
}
const { chromium } = await loadPlaywright()

/** DEMO_CHROME, else the newest Chrome for Testing that Playwright installed on this Mac. */
export function chromePath() {
  if (process.env.DEMO_CHROME) return process.env.DEMO_CHROME
  const dir = path.join(os.homedir(), 'Library/Caches/ms-playwright')
  const builds = existsSync(dir)
    ? readdirSync(dir).filter((d) => /^chromium-\d+$/.test(d)).sort((a, b) => Number(b.slice(9)) - Number(a.slice(9)))
    : []
  for (const b of builds) {
    const p = path.join(dir, b, 'chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing')
    if (existsSync(p)) return p
  }
  return undefined
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
export const now = () => Date.now() / 1000
const log = (m) => console.log(`[${new Date().toLocaleTimeString()}] ${m}`)

const CURSOR = `(() => {
  const add = () => {
    if (document.getElementById('__rec_cursor') || !document.documentElement) return
    const c = document.createElement('div'); c.id = '__rec_cursor'
    c.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24"><path d="M5 2.5v17.2l4.3-4.1 2.9 6.6 2.9-1.3-2.9-6.5h6z" fill="#111" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>'
    c.style.cssText = 'position:fixed;left:0;top:0;width:24px;height:24px;z-index:2147483647;pointer-events:none;will-change:transform;filter:drop-shadow(0 1px 1.5px rgba(0,0,0,.35))'
    const r = document.createElement('div'); r.id = '__rec_ripple'
    r.style.cssText = 'position:fixed;left:0;top:0;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;background:rgba(59,130,246,.28);border:2px solid rgba(59,130,246,.55);z-index:2147483646;pointer-events:none;opacity:0;transform:scale(.4);transition:opacity .35s ease,transform .35s ease'
    document.documentElement.append(r, c)
    let pos = { x: -40, y: -40 }
    try { pos = JSON.parse(sessionStorage.getItem('__rec_pos')) || pos } catch {}
    const place = (x, y) => { c.style.transform = 'translate(' + (x - 5) + 'px,' + (y - 2.5) + 'px)'; window.__recPos = { x, y } }
    place(pos.x, pos.y)
    addEventListener('mousemove', (e) => { place(e.clientX, e.clientY); try { sessionStorage.setItem('__rec_pos', JSON.stringify({ x: e.clientX, y: e.clientY })) } catch {} }, true)
    addEventListener('mousedown', (e) => {
      r.style.transition = 'none'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'; r.style.opacity = '1'; r.style.transform = 'scale(.4)'
      requestAnimationFrame(() => { r.style.transition = 'opacity .45s ease, transform .45s ease'; r.style.transform = 'scale(1.25)'; r.style.opacity = '0' })
    }, true)
  }
  add(); addEventListener('DOMContentLoaded', add)
  new MutationObserver(() => { if (!document.getElementById('__rec_cursor')) add() }).observe(document, { childList: true, subtree: false })
})()`

/**
 * outDir: the run directory. storageState: a Playwright auth file for the headless browser.
 * cdp: 'http://127.0.0.1:<port>' records a new tab in a Chrome you signed in to by hand (SSO apps); the tab is
 *   closed by R.close(), the browser keeps running. clipboardOrigin: grant clipboard access to that origin.
 */
export async function createRecorder({ outDir, width = 1600, height = 900, dpr = 2, storageState, locale = 'en-US', cdp, clipboardOrigin,
  timezoneId = Intl.DateTimeFormat().resolvedOptions().timeZone }) {
  mkdirSync(path.join(outDir, 'frames'), { recursive: true })
  const framesLog = path.join(outDir, 'frames.jsonl')
  const eventsLog = path.join(outDir, 'events.jsonl')
  let browser, context, page
  if (cdp) {
    browser = await chromium.connectOverCDP(cdp)
    context = browser.contexts()[0] ?? (await browser.newContext())
    page = await context.newPage()
  } else {
    browser = await chromium.launch({ headless: true, ...(chromePath() ? { executablePath: chromePath() } : {}), args: [`--force-device-scale-factor=${dpr}`, `--window-size=${width},${height + 87}`] })
    context = await browser.newContext({ viewport: null, locale, timezoneId, ...(storageState ? { storageState } : {}) })
    await context.addInitScript(CURSOR)
    page = await context.newPage()
  }
  if (clipboardOrigin) await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: clipboardOrigin }).catch(() => {})
  page.setDefaultTimeout(20_000)
  // In someone's own Chrome: our tabs get the recording size at DPR `dpr` whatever the screen is, and the cursor.
  const emulated = new WeakMap()
  async function own(p) {
    if (!cdp || emulated.has(p)) return
    const s = await context.newCDPSession(p)
    await s.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: dpr, mobile: false })
    emulated.set(p, s)
    await p.addInitScript(CURSOR)
    await p.evaluate(CURSOR).catch(() => {})
  }
  await own(page)

  const st = { seq: 0, lastSaved: 0, ffGap: 0, recording: false, mouse: { x: width / 2, y: height / 2 }, cdp: null, page }
  // What the input did (epoch seconds, CSS px): to_session.py + render.py turn it into the camera.
  const actions = { viewport: { width, height }, points: [], clicks: [], focuses: [], steps: [], scrolls: [], cursors: [] }
  const boxOfLoc = async (loc) => (await loc.boundingBox({ timeout: 5000 }).catch(() => null)) ?? null
  const event = (e) => appendFileSync(eventsLog, JSON.stringify({ t: now(), ...e }) + '\n')

  async function attach(p) {
    await own(p)
    if (st.cdp) {
      await st.cdp.send('Page.stopScreencast').catch(() => {})
      await st.cdp.detach().catch(() => {})
    }
    const session = await p.context().newCDPSession(p)
    session.on('Page.screencastFrame', async ({ data, metadata, sessionId }) => {
      session.send('Page.screencastFrameAck', { sessionId }).catch(() => {})
      if (!st.recording) return
      const ts = metadata.timestamp ?? now()
      if (st.ffGap && ts - st.lastSaved < st.ffGap) return
      st.lastSaved = ts
      const seq = ++st.seq
      const file = `frames/${String(seq).padStart(6, '0')}.jpg`
      writeFileSync(path.join(outDir, file), Buffer.from(data, 'base64'))
      appendFileSync(framesLog, JSON.stringify({ seq, ts, file, w: metadata.deviceWidth, h: metadata.deviceHeight }) + '\n')
    })
    await session.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: width * dpr, maxHeight: height * dpr, everyNthFrame: 1 })
    st.cdp = session
    st.page = p
  }

  const R = {
    browser,
    context,
    get page() {
      return st.page
    },
    event,
    log,
    async start() {
      await attach(page)
      st.recording = true
      event({ type: 'start' })
    },
    async switchTo(p) {
      await attach(p)
      st.mouse = { x: width / 2, y: height / 2 }
      await p.mouse.move(st.mouse.x, st.mouse.y)
      event({ type: 'switch' })
    },
    async stop() {
      event({ type: 'end' })
      await sleep(300)
      st.recording = false
      await st.cdp?.send('Page.stopScreencast').catch(() => {})
      actions.end = now()
      writeFileSync(path.join(outDir, 'actions.json'), JSON.stringify(actions))
    },
    /** Closes the headless browser, or only our tab in a CDP-connected Chrome. */
    async close() {
      clearInterval(st.redactTimer)
      if (cdp) {
        await st.page.close().catch(() => {})
        if (st.page !== page) await page.close().catch(() => {})
      }
      await browser.close().catch(() => {})
    },
    /**
     * Rehearsal guard: every non-GET request is answered locally with an empty 418 and kept in R.captured,
     * so a rehearsal never writes. Call R.allowWrites() (or don't block) for the real take.
     */
    captured: [],
    async blockWrites() {
      await context.route('**/*', (route) => {
        const req = route.request()
        if (req.method() === 'GET' || req.method() === 'HEAD' || req.method() === 'OPTIONS') return route.fallback()
        R.captured.push({ method: req.method(), url: req.url(), body: req.postData() })
        return route.fulfill({ status: 418, body: '' })
      })
    },
    async allowWrites() {
      await context.unrouteAll({ behavior: 'ignoreErrors' })
    },
    /** Tip card, top right, until the next tip (null clears): {title, lines: [], code: []}. Not read aloud. */
    tip(card) {
      log(`tip: ${card?.title ?? '(off)'}`)
      event({ type: 'tip', tip: card ?? null })
    },
    /** Caption shown from now until the next caption (null clears). pos: 'bottom' | 'top'. */
    cap(text, pos = 'bottom') {
      log(`caption: ${text}`)
      event({ type: 'caption', text, pos })
    },
    chapter(name) {
      log(`=== ${name}`)
      event({ type: 'chapter', name })
    },
    /** Fast-forward from now (speed = output speed-up); the recorder thins frames meanwhile. */
    ffOn(speed = 20) {
      st.ffGap = Math.max(0.05, speed / 30 / 2)
      event({ type: 'ff', on: true, speed })
    },
    ffOff() {
      st.ffGap = 0
      event({ type: 'ff', on: false })
    },
    cutOn() {
      event({ type: 'cut', on: true })
    },
    cutOff() {
      event({ type: 'cut', on: false })
    },
    /** Logs, every 80 ms, the on-screen boxes (CSS px) of text matching `src` so the edit can blur them. */
    trackRedact(src) {
      st.lastRedact = ''
      st.redactTimer = setInterval(async () => {
        try {
          const rects = await st.page.evaluate((src) => {
            const re = new RegExp(src, 'g')
            const out = []
            const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
            let n
            while ((n = w.nextNode())) {
              const t = n.nodeValue
              re.lastIndex = 0
              let m
              while ((m = re.exec(t))) {
                const r = document.createRange()
                r.setStart(n, m.index)
                r.setEnd(n, m.index + m[0].length)
                for (const b of r.getClientRects()) if (b.width > 0 && b.height > 0) out.push([b.x, b.y, b.width, b.height])
              }
            }
            return out
          }, src)
          const key = JSON.stringify(rects.map((r) => r.map(Math.round)))
          if (key !== st.lastRedact) {
            st.lastRedact = key
            event({ type: 'redact', rects })
          }
        } catch {}
      }, 80)
    },
    untrackRedact() {
      clearInterval(st.redactTimer)
      event({ type: 'redact', rects: [] })
    },
    // ---------- human-paced input ----------
    async moveTo(x, y, ms) {
      const p = st.page
      const from = { ...st.mouse }
      const dist = Math.hypot(x - from.x, y - from.y)
      const dur = ms ?? Math.min(900, Math.max(350, dist * 0.9))
      const steps = Math.max(8, Math.round(dur / 16))
      for (let i = 1; i <= steps; i++) {
        const u = i / steps
        const e = u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2
        // slight arc so the path does not look ruler-straight
        const arc = Math.sin(Math.PI * u) * Math.min(40, dist * 0.08)
        const nx = from.x + (x - from.x) * e + ((y - from.y) / (dist || 1)) * arc * 0.3
        const ny = from.y + (y - from.y) * e - ((x - from.x) / (dist || 1)) * arc * 0.3
        await p.mouse.move(nx, ny)
        if (st.recording) actions.points.push({ t: now(), x: nx, y: ny })
        await sleep(dur / steps)
      }
      st.mouse = { x, y }
    },
    /** Smoothly scrolls an element into the middle of its scroll container when it is not comfortably visible. */
    async reveal(loc, { block = 'center' } = {}) {
      await loc.waitFor({ state: 'visible' })
      const box = await loc.boundingBox()
      const vh = height
      if (box && box.y >= 70 && box.y + box.height <= vh - 90) return
      const scroll = { start: now(), automatic: false }
      await loc.evaluate((el, block) => el.scrollIntoView({ behavior: 'smooth', block }), block)
      await sleep(900)
      scroll.end = now()
      if (st.recording) actions.scrolls.push(scroll)
    },
    async point(loc, { dx = 0.5, dy = 0.5, reveal = true } = {}) {
      if (reveal) await R.reveal(loc)
      const box = await loc.boundingBox()
      if (!box) throw new Error('no box for target')
      const x = box.x + box.width * dx
      const y = box.y + box.height * dy
      await R.moveTo(x, y)
      return { x, y }
    },
    /** No input: camera=studio pushes in on loc for `hold` ms (a small proof: a focus ring, a colour, a badge). */
    async look(loc, { hold = 2000 } = {}) {
      const box = await boxOfLoc(loc)
      const t = now()
      if (box && st.recording) actions.focuses.push({ t, readyAt: t, end: t + hold / 1000, interactionEnd: t, action: 'look', context: null, manual: true, ...box })
      await sleep(hold)
    },
    async hover(loc, opts) {
      await R.point(loc, opts)
      await sleep(opts?.hold ?? 500)
    },
    /**
     * Human click. `expect`: the locator of what the click opens or changes (menu, dialog, toast, row); the
     * click waits for it (`timeout` ms) and camera=studio frames it next to the control.
     */
    async click(loc, { before = 300, after = 700, action = 'click', expect, timeout = 8000, ...opts } = {}) {
      const start = now()
      if (opts.reveal !== false) await R.reveal(loc)
      const box = await boxOfLoc(loc)
      const focus = box && st.recording
        ? { t: now(), readyAt: now(), end: now(), action, context: null, manual: false, ...box }
        : null
      if (focus) actions.focuses.push(focus)
      await R.point(loc, { ...opts, reveal: false })
      const actionStart = now()
      await sleep(before)
      const click = { t: now(), ...st.mouse }
      await st.page.mouse.down()
      await sleep(70)
      await st.page.mouse.up()
      click.up = now()
      if (st.recording) actions.clicks.push(click)
      if (focus) focus.interactionEnd = now()
      if (expect) await expect.first().waitFor({ state: 'visible', timeout })
      await sleep(after)
      if (focus) {
        focus.end = now()
        const res = expect ? await boxOfLoc(expect.first()) : null
        if (res) focus.result = { t: now(), ...res }
      }
      if (st.recording)
        actions.steps.push({ action, start, actionStart, interactionEnd: focus?.interactionEnd ?? now(), expectationEnd: now(), pause: after / 1000, end: now() })
      return focus
    },
    async type(loc, text, { delay = 65, click = true, after = 500 } = {}) {
      const focus = click ? await R.click(loc, { after: 250, action: 'type' }) : null
      if (focus) focus.typingStart = now()
      await st.page.keyboard.type(text, { delay })
      if (focus) {
        focus.interactionEnd = now()
        focus.end = now()
      }
      await sleep(after)
    },
    async press(key, after = 500) {
      await st.page.keyboard.press(key)
      await sleep(after)
    },
    async wheel(dy, { steps = 12, at } = {}) {
      if (at) await R.point(at, { reveal: false })
      for (let i = 0; i < steps; i++) {
        await st.page.mouse.wheel(0, dy / steps)
        await sleep(30)
      }
      await sleep(500)
    },
    /** Waits (polling) for fn() to be truthy, fast-forwarding when it takes longer than `ffAfter` s. */
    async waitFor(fn, { timeout = 600, ffAfter = 4, speed = 20, every = 1000, label = '', onTick, interrupt } = {}) {
      let t0 = now()
      let ff = false
      for (;;) {
        let v
        try {
          v = await fn()
        } catch (e) {
          v = undefined
        }
        if (v) {
          if (ff) R.ffOff()
          return v
        }
        if (onTick) await onTick()
        if (interrupt && (await interrupt.check().catch(() => false))) {
          if (ff) {
            R.ffOff()
            ff = false
          }
          await interrupt.act()
          t0 = now()
          continue
        }
        if (!ff && now() - t0 > ffAfter) {
          ff = true
          R.ffOn(speed)
        }
        if (now() - t0 > timeout) {
          if (ff) R.ffOff()
          throw new Error(`timeout waiting: ${label}`)
        }
        await sleep(every)
      }
    },
  }
  return R
}
