import { describe, expect, it } from "vitest";
import {
  accountPath,
  intentFor,
  isAccountPath,
  isPrivatePath,
  safeReturnPath,
} from "./auth-routes";

describe("which pages need an account", () => {
  it.each([
    "/",
    "/explore",
    "/explore/mathematics",
    "/watch/lessons/lesson_1",
    "/creators/user_1",
    "/login",
    "/signup",
  ])("%s is open to visitors", (path) => {
    expect(isPrivatePath(path)).toBe(false);
  });

  it.each([
    "/library",
    "/workspace",
    "/my-courses",
    "/settings",
    "/credits",
    "/lessons/new",
    "/lessons/lesson_1",
    "/lessons/lesson_1/edit",
    "/courses/new",
    "/courses/course_1/syllabus",
    "/internal/tools",
  ])("%s needs an account", (path) => {
    expect(isPrivatePath(path)).toBe(true);
  });

  it("does not mistake a longer public path for a private one", () => {
    expect(isPrivatePath("/lessonsearch")).toBe(false);
    expect(isPrivatePath("/library-of-everything")).toBe(false);
  });

  it("recognizes the account pages", () => {
    expect(isAccountPath("/login")).toBe(true);
    expect(isAccountPath("/reset-password")).toBe(true);
    expect(isAccountPath("/explore")).toBe(false);
  });
});

describe("returning after sign in", () => {
  it("only accepts paths on this site", () => {
    expect(safeReturnPath("/lessons/new")).toBe("/lessons/new");
    expect(safeReturnPath("//evil.example")).toBe("/");
    expect(safeReturnPath("https://evil.example")).toBe("/");
    expect(safeReturnPath("/\\evil.example")).toBe("/");
    expect(safeReturnPath("/a b")).toBe("/");
    expect(safeReturnPath(null)).toBe("/");
  });

  it("builds sign-in links that remember the destination", () => {
    expect(accountPath("/login")).toBe("/login");
    expect(accountPath("/login", "/")).toBe("/login");
    expect(accountPath("/signup", "/lessons/new")).toBe(
      "/signup?returnTo=%2Flessons%2Fnew",
    );
    expect(accountPath("/login", "https://evil.example")).toBe("/login");
  });

  it("describes what the visitor is trying to do", () => {
    expect(intentFor("/lessons/new")).toBe("create a lesson");
    expect(intentFor("/workspace")).toBe("see your creations");
    expect(intentFor("/library?x=1")).toBe("open your library");
    expect(intentFor("/lessons/lesson_1")).toBe("open your lesson");
    expect(intentFor("/watch/lessons/lesson_1")).toBe("copy this lesson");
    expect(intentFor("/")).toBe("");
  });
});
