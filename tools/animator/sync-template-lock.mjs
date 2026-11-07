// Keep editable projects on the exact dependency graph tested in the worker.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root = path.dirname(fileURLToPath(import.meta.url));
const read = async name => JSON.parse(await fs.readFile(path.join(root, name), 'utf8'));
const worker = await read('package.json');
const template = await read('template/package.json');
const lock = await read('package-lock.json');
template.dependencies = worker.dependencies;
template.devDependencies = worker.devDependencies;
template.overrides = worker.overrides;
lock.name = template.name;
lock.version = template.version;
lock.packages[''] = {...lock.packages[''], name: template.name, version: template.version,
  dependencies: template.dependencies, devDependencies: template.devDependencies};
await fs.writeFile(path.join(root, 'template/package.json'), JSON.stringify(template, null, 2) + '\n');
await fs.writeFile(path.join(root, 'template/package-lock.json'), JSON.stringify(lock, null, 2) + '\n');
