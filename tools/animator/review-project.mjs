// Offline, adapter-owned render evidence. Generated code has no provider credentials.
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';

const project = path.resolve(process.argv[2]);
const output = path.resolve(process.argv[3]);
const runtime = path.dirname(new URL(import.meta.url).pathname);
execFileSync(process.execPath, [path.join(runtime, 'verify-remotion.mjs'), project, output], {stdio: 'inherit'});
execFileSync(process.execPath, [path.join(runtime, 'render-video.mjs'), project, path.join(output, 'lesson.mp4')], {stdio: 'inherit'});
const frames = fs.readdirSync(output).filter(n => /^frame-\d+\.png$/.test(n)).sort();
const script = `
from PIL import Image, ImageDraw
from pathlib import Path
import sys
out=Path(sys.argv[1]); frames=sorted(out.glob('frame-*.png'))
for page in range(0,len(frames),9):
 sheet=Image.new('RGB',(1920,1152),'#e9edf0'); draw=ImageDraw.Draw(sheet)
 for i,p in enumerate(frames[page:page+9]):
  x=(i%3)*640; y=(i//3)*384
  with Image.open(p) as im: sheet.paste(im.convert('RGB').resize((640,360)),(x,y))
  draw.text((x+8,y+363),p.name,fill='#17212b')
 sheet.save(out/f'contact-{page//9:02d}.png')
`;
execFileSync('python3', ['-c', script, output], {stdio: 'inherit'});
console.log(`Rendered ${frames.length} review frames, seeking checks, contact sheets and decoded full video`);
