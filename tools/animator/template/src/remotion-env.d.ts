// Remotion 4.0.539 emits Bun's global Timer name in its declaration files.
// Our Node/browser worker uses the host setTimeout handle; no library checks are skipped.
type Timer = ReturnType<typeof globalThis.setTimeout>;
