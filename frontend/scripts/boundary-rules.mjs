import path from "node:path";
import ts from "typescript";

const layers = ["domain", "application", "adapters", "ui"];
const allowed = {
  domain: ["domain"],
  application: ["application", "domain"],
  adapters: ["adapters", "application", "domain"],
  ui: ["ui", "application"],
};
const capabilities = new Set([
  "window",
  "document",
  "localStorage",
  "sessionStorage",
  "fetch",
  "crypto",
  "Date",
  "globalThis",
  "setTimeout",
  "setInterval",
]);

/** Inspect source text without executing it or importing application modules. */
export function inspectBoundaries(relative, code) {
  if (
    /\.(test|spec)\./.test(relative) ||
    relative.startsWith("testing/") ||
    relative === "composition.ts"
  )
    return [];
  const layer = relative.split("/")[0];
  if (!layers.includes(layer))
    return [relative + ": production code must belong to a declared layer"];
  const violations = [];
  const fail = (message) => violations.push(relative + ": " + message);
  const inner = layer === "domain" || layer === "application";
  const source = ts.createSourceFile(
    relative,
    code,
    ts.ScriptTarget.Latest,
    true,
  );
  function dependency(specifier) {
    if (!specifier.startsWith(".")) {
      if (inner) fail("inner layer imports external dependency: " + specifier);
      return;
    }
    const resolved = path.posix.normalize(
      path.posix.join(path.posix.dirname(relative), specifier),
    );
    const target = resolved.split("/")[0];
    if (!allowed[layer].includes(target))
      fail("forbidden dependency: " + specifier);
    if (resolved.includes("/testing/") || /\.(test|spec)(\.|$)/.test(resolved))
      fail("production code imports test support: " + specifier);
  }
  function literalDependency(node) {
    if (node && ts.isStringLiteralLike(node)) dependency(node.text);
    else fail("computed module dependencies cannot be verified");
  }
  function visit(node) {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier
    )
      literalDependency(node.moduleSpecifier);
    if (ts.isImportTypeNode(node) && ts.isLiteralTypeNode(node.argument))
      literalDependency(node.argument.literal);
    if (
      ts.isImportEqualsDeclaration(node) &&
      ts.isExternalModuleReference(node.moduleReference)
    )
      literalDependency(node.moduleReference.expression);
    if (
      ts.isCallExpression(node) &&
      (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
        (ts.isIdentifier(node.expression) &&
          node.expression.text === "require"))
    )
      literalDependency(node.arguments[0]);
    if (inner && ts.isIdentifier(node) && capabilities.has(node.text))
      fail("infrastructure capability in inner layer: " + node.text);
    if (
      inner &&
      ts.isPropertyAccessExpression(node) &&
      node.expression.getText(source) === "Math" &&
      node.name.text === "random"
    )
      fail("randomness requires an injected port");
    if (layer === "application" && ts.isClassDeclaration(node)) {
      const methods = node.members.filter(
        (member) =>
          ts.isMethodDeclaration(member) &&
          !ts.isPrivateIdentifier(member.name) &&
          !member.modifiers?.some((modifier) =>
            [
              ts.SyntaxKind.PrivateKeyword,
              ts.SyntaxKind.ProtectedKeyword,
            ].includes(modifier.kind),
          ),
      );
      if (
        methods.length !== 1 ||
        methods[0].name?.getText(source) !== "execute"
      )
        fail("use case must expose only execute()");
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  return violations;
}
