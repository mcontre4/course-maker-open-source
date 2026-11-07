import { describe, expect, it } from "vitest";
import { inspectBoundaries } from "./boundary-rules.mjs";

describe("frontend boundary enforcement", () => {
  it("permits the intended inward dependencies", () => {
    expect(
      inspectBoundaries(
        "application/create-course.ts",
        'import type { Course } from "../domain/course"; export class CreateCourse { execute() {} }',
      ),
    ).toEqual([]);
    expect(
      inspectBoundaries(
        "ui/page.tsx",
        'import type { CourseResponse } from "../application/dto"; import { useState } from "react";',
      ),
    ).toEqual([]);
  });
  it.each([
    ["ui/page.ts", 'import type { Course } from "../domain/course";'],
    ["domain/course.ts", 'import { useState } from "react";'],
    ["ui/page.ts", 'const client = import("../adapters/client");'],
    ["ui/page.ts", 'type Client = import("../adapters/client").Client;'],
    [
      "application/use-case.ts",
      'const browser = require("../adapters/browser");',
    ],
    ["ui/page.ts", 'import { app } from "../composition";'],
    ["ui/page.ts", 'import { hidden } from "../../legacy/hidden";'],
    ["domain/course.ts", "const id = Math.random();"],
    [
      "application/use-case.ts",
      "export class MixedService { execute() {} save() {} }",
    ],
    ["domain/course.ts", 'import { helper } from "./course.test";'],
  ])("rejects a boundary escape in %s", (file, source) => {
    expect(inspectBoundaries(file, source).length).toBeGreaterThan(0);
  });
});
