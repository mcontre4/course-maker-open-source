import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { inspectBoundaries } from "./boundary-rules.mjs";

const root = fileURLToPath(new URL("../src/course-maker/", import.meta.url));
async function files(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return (
    await Promise.all(
      entries.map((entry) =>
        entry.isDirectory()
          ? files(path.join(directory, entry.name))
          : [path.join(directory, entry.name)],
      ),
    )
  ).flat();
}
const results = await Promise.all(
  (await files(root))
    .filter((file) => /\.tsx?$/.test(file))
    .map(async (file) =>
      inspectBoundaries(
        path.relative(root, file).split(path.sep).join("/"),
        await readFile(file, "utf8"),
      ),
    ),
);
const violations = results.flat();
if (violations.length) {
  process.stderr.write(violations.join("\n") + "\n");
  process.exitCode = 1;
} else process.stdout.write("Frontend hexagonal boundaries pass.\n");
