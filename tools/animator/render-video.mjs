import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
const [project, output] = process.argv.slice(2);
if (project && fs.existsSync(path.join(project, "player.html"))) {
  const result = spawnSync(
    process.execPath,
    [
      new URL("./render-canvas.mjs", import.meta.url).pathname,
      project,
      path.dirname(output),
    ],
    { stdio: "inherit" },
  );
  if (result.status !== 0) process.exit(result.status || 1);
  const rendered = path.join(path.dirname(output), "lesson.mp4");
  if (path.resolve(rendered) !== path.resolve(output))
    fs.renameSync(rendered, output);
} else await import("./render-remotion.mjs");
