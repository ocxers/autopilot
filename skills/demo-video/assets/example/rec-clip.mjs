// A clip: create an item from a list page and end on the app's own proof.
//   node rec-<KEY>.mjs --run runs/<KEY>-a [--rehearse] [--cdp http://127.0.0.1:9333]
// --rehearse blocks every write (R.captured shows what the app would have sent); the take writes for real.
import { createRecorder, sleep } from './lib.mjs'

const arg = (k, d) => (process.argv.includes(k) ? process.argv[process.argv.indexOf(k) + 1] : d)
const REHEARSE = process.argv.includes('--rehearse')
const BASE = 'http://localhost:3000'

const R = await createRecorder({
  outDir: arg('--run', 'runs/clip-a'),
  cdp: arg('--cdp'), // a Chrome the owner signed in to by hand (SSO apps) …
  storageState: arg('--cdp') ? undefined : 'auth.json', // … or a saved session for headless
})
const page = R.page
try {
  if (REHEARSE) await R.blockWrites()
  await page.goto(`${BASE}/items`) // the route users reach, with the app shell
  await page.getByRole('heading', { name: 'Items' }).waitFor()
  await sleep(1000)

  await R.start()
  R.cap('Create an item from the list')
  await sleep(1500)
  const dialog = page.getByRole('dialog')
  await R.click(page.getByRole('button', { name: 'New item', exact: true }), { expect: dialog })
  R.cap('Give it a name')
  await R.type(dialog.getByLabel('Name'), 'Quarterly report', { delay: 70 })
  await sleep(600)
  const toast = page.getByText('Item created')
  await R.click(dialog.getByRole('button', { name: 'Create' }), { expect: REHEARSE ? undefined : toast })
  if (REHEARSE) console.log('would send:', JSON.stringify(R.captured, null, 1))

  // The proof: the app's own toast and the new row. Push in on the row; it is small at full frame.
  R.cap('The new item is in the list')
  await R.look(page.getByRole('row', { name: /Quarterly report/ }), { hold: 2500 })
  // A tip explains what the app does not show; never type it into the app.
  R.tip({ title: 'Saved as', lines: ['The request the app sent'], code: ['POST /api/items {"name":"Quarterly report"}'] })
  await sleep(3500)
  R.tip(null)
  await R.stop()
} finally {
  await R.close()
}
process.exit(0)
