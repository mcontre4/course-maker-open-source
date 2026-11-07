// Regenerate only the trusted teaching-reference contact sheets, without providers.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const tools = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(tools, 'teaching-examples');
const catalog = JSON.parse(await fs.readFile(path.join(root, 'manifest.json'), 'utf8'));
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || (process.platform === 'darwin'
    ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    : '/usr/bin/chromium-headless-shell'),
  headless: true,
});
try {
  for (const entry of catalog.examples) {
    const page = await browser.newPage();
    await page.setContent('<canvas id="subject" width="1280" height="720"></canvas>');
    const notes = JSON.parse(await fs.readFile(path.join(root, entry.notes), 'utf8'));
    const style = path.join(tools, 'styles/flat-vector-science');
    for (const name of ['harness.js', 'drawing.js']) {
      await page.addScriptTag({ path: path.join(style, name) });
    }
    for (const [font, weight] of [['nunito', 900], ['nunito', 700], ['fredoka', 600]]) {
      const bytes = await fs.readFile(path.join(tools, 'node_modules/@fontsource', font,
        'files', `${font}-latin-${weight}-normal.woff2`));
      await page.evaluate(async ({ font, weight, data }) => {
        const face = new FontFace(font[0].toUpperCase() + font.slice(1),
          `url(data:font/woff2;base64,${data})`, { weight: String(weight) });
        document.fonts.add(await face.load());
      }, { font, weight, data: bytes.toString('base64') });
    }
    await page.addScriptTag({ path: path.join(root, entry.source) });
    const data = await page.evaluate(({ shots, applyStyleFinish }) => {
      const subject = document.getElementById('subject');
      const c = subject.getContext('2d');
      const sheet = document.createElement('canvas');
      sheet.width = 1920; sheet.height = 404;
      const s = sheet.getContext('2d');
      s.fillStyle = '#111538'; s.fillRect(0, 0, 1920, 404);
      for (const [i, shot] of shots.entries()) {
        c.reset(); window.explainer(c, 1280, 720, shot.at_sec);
        if (applyStyleFinish && window.STYLE?.finish) {
          window.STYLE.finish(c, 1280, 720, shot.at_sec);
        }
        s.drawImage(subject, i * 640, 0, 640, 360);
        s.fillStyle = '#fff9ed'; s.font = '20px sans-serif';
        s.fillText(`${shot.at_sec}s: ${shot.focus}`, i * 640 + 12, 390, 616);
      }
      return sheet.toDataURL('image/png').split(',')[1];
    }, { shots: notes.narration_and_visual_sequence,
      applyStyleFinish: Boolean(notes.origin.style_id) });
    await fs.writeFile(path.join(root, entry.image), Buffer.from(data, 'base64'));
    await page.close();
    console.log(`Rendered ${entry.id}`);
  }
} finally {
  await browser.close();
}
