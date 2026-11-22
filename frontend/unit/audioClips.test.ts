import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { test } from 'node:test'
import { CLIPS } from '../src/i18n/audioClips.ts'

for (const lang of ['sd', 'pa'] as const) {
  test(`every ${lang} clip key has an mp3 file`, () => {
    assert.ok(CLIPS[lang].size > 0)
    for (const key of CLIPS[lang]) {
      assert.ok(existsSync(new URL(`../public/audio/${lang}/${key}.mp3`, import.meta.url)), `${lang}/${key}.mp3 missing`)
    }
  })
}
