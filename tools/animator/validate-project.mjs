// Static analysis only: never import or execute generated code.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';

const runtime = path.dirname(fileURLToPath(import.meta.url));
const project = path.resolve(process.argv[2]);
const board = JSON.parse(fs.readFileSync(path.join(project, '../inputs/storyboard.json')));
const timeline = JSON.parse(fs.readFileSync(path.join(project, 'src/timeline.json')));
const allowed = new Set(['react', 'react-dom', 'remotion', '@remotion/three', 'three', '@react-three/fiber', '@remotion/shapes', '@remotion/paths', '@remotion/rough-notation',
  '@remotion/skia', '@shopify/react-native-skia', '@xyflow/react', 'roughjs', 'd3', 'katex', 'lucide-react',
  '@remotion/layout-utils', '@remotion/lottie', 'lottie-web', '@rive-app/canvas-advanced', '@fontsource/inter']);
const errors = [];
const fail = (message) => errors.push(message);
const assetManifestPath = path.join(project, 'public/illustrations/manifest.json');
const assetManifest = fs.existsSync(assetManifestPath) ? JSON.parse(fs.readFileSync(assetManifestPath)) : null;
const usedIllustrations = new Set();
const configPath = path.join(project, 'tsconfig.json');
const config = ts.readConfigFile(configPath, ts.sys.readFile);
const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, project);
const options = {...parsed.options, types: parsed.options.types ?? ["node", "react", "react-dom"], baseUrl: runtime,
  paths: {'three': ['node_modules/@types/three'], 'three/*': ['node_modules/@types/three/*'],
    'react': ['node_modules/@types/react'], 'react/*': ['node_modules/@types/react/*'],
    'd3': ['node_modules/@types/d3'], 'katex': ['node_modules/@types/katex'],
    'react-dom': ['node_modules/@types/react-dom'], 'react-dom/*': ['node_modules/@types/react-dom/*'],
    'remotion/no-react': ['node_modules/remotion/dist/cjs/no-react.d.ts'],
    '*': ['node_modules/@types/*', 'node_modules/*']}, typeRoots: [path.join(runtime, 'node_modules/@types')]};
const program = ts.createProgram(parsed.fileNames, options);
for (const diagnostic of [...parsed.errors, ...ts.getPreEmitDiagnostics(program)]) {
  fail(`${diagnostic.file?.fileName ?? 'tsconfig'}: ${ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n')}`);
}
const walkFiles = (dir) => fs.readdirSync(dir, {withFileTypes: true}).flatMap(e =>
  e.isDirectory() ? walkFiles(path.join(dir, e.name)) : [path.join(dir, e.name)]);
for (const filename of walkFiles(path.join(project, 'src'))) {
  if (!/\.(tsx?|jsx?|css)$/.test(filename)) continue;
  const source = fs.readFileSync(filename, 'utf8');
  // This adapter-owned component is byte-protected by the Python validator.
  // It loads local WASM/assets and manages resource state, never animation state.
  if (filename === path.join(project, 'src/visuals/RiveIllustration.tsx')) continue;
  const withoutDisabledMotion = source.replace(/(?:animation|transition)\s*:\s*none(?:\s*!important)?\s*;?/g, '');
  if (filename.endsWith('.css')) {
    if (/@keyframes|@import|(?:animation|transition)[\w-]*\s*:|url\(\s*['"]?(?:https?:|\/\/)/.test(withoutDisabledMotion)) fail(`Forbidden CSS motion/network: ${filename}`);
    continue;
  }
  const tree = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true,
    filename.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  if (tree.checkJsDirective?.enabled === false || tree.commentDirectives?.length) {
    fail(`TypeScript validation suppression is forbidden: ${filename}`);
  }
  const isBootstrap = filename === path.join(project, 'src/index.ts');
  const hasApprovedEquation = tree.statements.some(node => ts.isImportDeclaration(node) &&
    ts.isStringLiteral(node.moduleSpecifier) && node.moduleSpecifier.text.startsWith('.') &&
    path.resolve(path.dirname(filename), node.moduleSpecifier.text + '.tsx') ===
      path.join(project, 'src/visuals/ApprovedEquation.tsx') &&
    node.importClause?.namedBindings && ts.isNamedImports(node.importClause.namedBindings) &&
    node.importClause.namedBindings.elements.some(e => e.name.text === 'ApprovedEquation' && !e.propertyName));
  const visible = [];
  const cues = new Set();
  const inspect = (node) => {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
      const spec = node.moduleSpecifier;
      if (spec && ts.isStringLiteral(spec)) {
        const bindings = ts.isImportDeclaration(node) ? node.importClause?.namedBindings : undefined;
        const forbidden = spec.text === 'd3' ? /^(?:timer|interval|timeout|transition|now)$/ :
          spec.text.startsWith('@shopify/react-native-skia') ? /^(?:useClock|useVideo(?:Loading)?|useAnimatedImageValue|use(?:Rect|RSXform|Point|Color)Buffer|usePathValue|usePathInterpolation|useVectorInterpolation|useTexture|usePictureAsTexture|useImageAsTexture|notifyChange)$/ : null;
        if (forbidden && bindings && ts.isNamedImports(bindings)) {
          for (const binding of bindings.elements) {
            if (forbidden.test((binding.propertyName ?? binding.name).text)) fail(`Library clock or native animation hook is not supported: ${binding.getText(tree)}`);
          }
        }
        if (spec.text.startsWith('.')) {
          if (!path.resolve(path.dirname(filename), spec.text).startsWith(project + path.sep)) fail('Import escapes project');
        } else if (![...allowed].some(p => spec.text === p || spec.text.startsWith(p + '/'))) {
          fail(`Unsupported external module: ${spec.text}`);
        }
      }
    }
    if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
      const name = node.expression.getText(tree).replace(/\s/g, '');
      const bootstrapImport = isBootstrap && name === 'import' && node.arguments?.length === 1 &&
        ts.isStringLiteral(node.arguments[0]) && node.arguments[0].text === './Root';
      if (!bootstrapImport && (/^(?:(?:globalThis|window)\.)?(?:Math\.random|Date(?:\.now)?|performance\.now|crypto\.(?:randomUUID|getRandomValues)|fetch|XMLHttpRequest|WebSocket|setTimeout|setInterval|requestAnimationFrame|eval|Function|require|import)$/.test(name)
          || /gsap/.test(name) || /(?:^|\.)(?:transition|timer|interval|useClock|useVideo|useAnimatedImageValue)$/.test(name))) fail(`nondeterministic or network code: ${name}`);
      if (/^(?:React\.)?(?:useState|useReducer)$/.test(name)) fail(`Mutable animation state: ${name}`);
    }
    if (ts.isJsxText(node)) visible.push(node.text);
    if (ts.isJsxExpression(node) && node.expression &&
        (ts.isStringLiteral(node.expression) || ts.isNoSubstitutionTemplateLiteral(node.expression))) {
      visible.push(node.expression.text);
    }
    if (ts.isJsxAttribute(node)) {
      const name = node.name.getText(tree);
      if (name === 'asset' && node.parent.parent.tagName?.getText(tree) === 'RiveIllustration' &&
          node.initializer && ts.isStringLiteral(node.initializer)) usedIllustrations.add(node.initializer.text);
      if (name === 'data-cue-id' && node.initializer && ts.isStringLiteral(node.initializer)) cues.add(node.initializer.text);
      const value = node.initializer && ts.isJsxExpression(node.initializer)
        ? node.initializer.expression : node.initializer;
      if (hasApprovedEquation && name === 'verbatim' && node.parent.parent.tagName.getText(tree) === 'ApprovedEquation' &&
          value && (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value))) visible.push(value.text);
      if (['src', 'href'].includes(name) && value &&
          (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) &&
          /^(?:[a-z]+:|\/\/|\/)|\.\./i.test(value.text)) fail('Nonlocal asset reference');
    }
    if (ts.isJsxElement(node) && node.openingElement.tagName.getText(tree) === 'style' &&
        /@keyframes|@import|(?:animation|transition)[\w-]*\s*:|https?:\/\//.test(node.getText(tree))) fail('Inline CSS animation/network is not seekable');
    if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
        /@keyframes|\bgsap\b|https?:\/\//.test(node.text.replace('http://www.w3.org/2000/svg', ''))) {
      // Teaching strings inside JSX are data, not executable code.
      if (!ts.isJsxExpression(node.parent) && !ts.isJsxAttribute(node.parent)) fail('Forbidden network/legacy animation reference');
    }
    if (ts.isPropertyAssignment(node) && ['animation', 'animationName', 'transition'].includes(
        ts.isStringLiteral(node.name) ? node.name.text : node.name.getText(tree)) &&
        !(ts.isStringLiteral(node.initializer) && node.initializer.text === 'none')) fail('CSS animation is not seekable');
    ts.forEachChild(node, inspect);
  };
  inspect(tree);
  const scene = board.scenes.find(s => filename === path.join(project, `src/scenes/${s.scene_id}.tsx`));
  if (scene) {
    const expected = timeline.scenes.find(s => s.scene_id === scene.scene_id);
    for (const cue of expected.cues) if (!cues.has(cue.cue_id)) fail(`Missing visible cue ${scene.scene_id}/${cue.cue_id}`);
    if (cues.size !== expected.cues.length) fail(`Unexpected or duplicate cue coverage in ${scene.scene_id}`);
    const text = visible.join(' ').replace(/\s+/g, ' ');
    for (const equation of scene.equations) {
      if (!text.includes(equation.replace(/\s+/g, ' '))) fail(`Missing visible equation in ${scene.scene_id}: ${equation}`);
    }
  }
}
if (assetManifest) {
  for (const asset of assetManifest.assets) {
    if (!usedIllustrations.has(asset.id)) fail(`Generated Rive illustration is not used: ${asset.id}`);
  }
}
if (errors.length) {
  process.stderr.write([...new Set(errors)].join('\n') + '\n');
  process.exit(1);
}
console.log('TypeScript, scene equations, cue anchors and deterministic source checks passed. Visual QA requires separate developer rendering.');
