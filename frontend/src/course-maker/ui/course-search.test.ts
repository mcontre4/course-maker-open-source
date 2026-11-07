import { describe, expect, it } from "vitest";
import { legacyExploreUrl, searchResultsUrl } from "./course-search";

describe("legacyExploreUrl", () => {
  const url = (search: string) => legacyExploreUrl(new URLSearchParams(search));

  it("keeps the home page for plain visits", () => {
    expect(url("")).toBeNull();
    expect(url("q=%20")).toBeNull();
  });
  it("sends old search links to Explore", () => {
    expect(url("q=python")).toBe(searchResultsUrl("python"));
  });
  it("sends old topic and subtopic links to their pages", () => {
    expect(url("topic=Engineering")).toBe("/explore/engineering");
    expect(url("topic=Thermodynamics")).toBe(
      "/explore/engineering?sub=Thermodynamics",
    );
    expect(url("topic=Unknown")).toBe("/explore");
  });
});
