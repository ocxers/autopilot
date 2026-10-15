// node gen.mjs jobs.json  — jobs: [{ text, out }]; one model load, writes 24 kHz WAVs
import { readFileSync, existsSync } from 'node:fs'
import { KokoroTTS } from 'kokoro-js'
const jobs = JSON.parse(readFileSync(process.argv[2], 'utf8')).filter((j) => !existsSync(j.out))
const voice = process.env.VOICE ?? 'af_heart'
const speed = Number(process.env.SPEED ?? 1)
const tts = await KokoroTTS.from_pretrained('onnx-community/Kokoro-82M-v1.0-ONNX', { dtype: 'fp32', device: 'cpu' })
let n = 0
for (const j of jobs) {
  const audio = await tts.generate(j.text, { voice, speed })
  await audio.save(j.out)
  if (++n % 10 === 0) console.log(`${n}/${jobs.length}`)
}
console.log(`done ${jobs.length}`)
