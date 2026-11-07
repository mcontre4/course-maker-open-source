// Static source checks; runtime evidence is collected separately in an offline worker.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import ts from "typescript";
const project = path.resolve(process.argv[2]);
const source = fs.readFileSync(path.join(project, "animation.js"), "utf8");
new vm.Script(source);
const tree = ts.createSourceFile(
  "animation.js",
  source,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.JS,
);
const errors = [];
const runtimeGlobals = new Set(["H", "SOUND"]);
const collectGlobal = (node) => {
  // Classic browser scripts expose assignments to window/globalThis as globals.
  if (
    ts.isBinaryExpression(node) &&
    node.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
    (ts.isPropertyAccessExpression(node.left) || ts.isElementAccessExpression(node.left)) &&
    ts.isIdentifier(node.left.expression) &&
    ["window", "globalThis"].includes(node.left.expression.text)
  ) {
    const name = ts.isPropertyAccessExpression(node.left)
      ? node.left.name.text
      : ts.isStringLiteralLike(node.left.argumentExpression)
        ? node.left.argumentExpression.text
        : null;
    if (name && ts.isIdentifierText(name, ts.ScriptTarget.Latest)) runtimeGlobals.add(name);
  }
  // Authored and bundled classic scripts share the same global naming rules.
};
const drawingFile = path.join(project, "style/drawing.js");
if (fs.existsSync(drawingFile)) {
  const drawing = ts.createSourceFile(drawingFile, fs.readFileSync(drawingFile, "utf8"),
    ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  const visit = (node) => { collectGlobal(node); ts.forEachChild(node, visit); };
  visit(drawing);
} else {
  // Retain source-only validation for legacy Flat-Vector projects and tooling.
  runtimeGlobals.add("FV");
}
const inspect = (node) => {
  collectGlobal(node);
  if (
    ts.isImportDeclaration(node) ||
    ts.isExportDeclaration(node) ||
    ts.isJsxElement(node)
  )
    errors.push("Only plain JavaScript drawing is supported");
  if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
    const name = node.expression.getText(tree).replace(/\s/g, "");
    if (/^(?:React\.|Remotion\.|RiveIllustration\b)/.test(name))
      errors.push("Framework scene authoring is not supported");
    if (
      /^(?:(?:window|globalThis)\.)?(?:Math\.random|Date(?:\.now)?|performance\.now|crypto\.(?:randomUUID|getRandomValues)|fetch|XMLHttpRequest|WebSocket|setTimeout|setInterval|requestAnimationFrame|eval|Function|require|import)$/.test(
        name,
      )
    )
      errors.push("Non-deterministic or network call: " + name);
  }
  ts.forEachChild(node, inspect);
};
inspect(tree);
// Check name resolution without imposing TypeScript annotations on authored JS.
// Syntax checks alone accept missing drawing helpers until the first rendered frame.
const animationFile = path.join(project, "animation.js");
const runtimeFile = path.join(project, "__canvas_runtime__.d.ts");
const options = {
  allowJs: true,
  checkJs: true,
  noEmit: true,
  target: ts.ScriptTarget.ES2022,
  lib: ["lib.es2022.d.ts", "lib.dom.d.ts"],
  types: [],
};
const host = ts.createCompilerHost(options);
const getSourceFile = host.getSourceFile.bind(host);
host.getSourceFile = (filename, ...args) =>
  filename === runtimeFile
    ? ts.createSourceFile(
        filename,
        [...runtimeGlobals].map(name => `declare var ${name}: any;`).join("\n") +
          "\ninterface Window { [name: string]: any; }",
        ts.ScriptTarget.Latest,
      )
    : getSourceFile(filename, ...args);
const program = ts.createProgram([animationFile, runtimeFile], options, host);
for (const diagnostic of program.getSemanticDiagnostics()) {
  // Missing names, misspelled names with suggestions, and unbound shorthand fields.
  if (
    diagnostic.file?.fileName !== animationFile ||
    ![2304, 2552, 18004].includes(diagnostic.code)
  ) continue;
  const location = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start);
  errors.push(
    `animation.js:${location.line + 1}:${location.character + 1}: ` +
      ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n"),
  );
}
for (const name of ["explainer", "scoreSound", "visualPlan", "cueEvents"])
  if (!source.includes("window." + name)) errors.push("Missing window." + name);
if (source.length > 600000) errors.push("Animation source exceeds budget");
if (errors.length) throw new Error(errors.join("\n"));
console.log("Plain JavaScript syntax and deterministic source checks passed");
