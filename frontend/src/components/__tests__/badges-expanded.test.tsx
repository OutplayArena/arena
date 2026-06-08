import { describe, it, expect, vi, beforeEach } from "vitest";
import { downloadJSON } from "../badges";

describe("downloadJSON", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a Blob and triggers download", () => {
    const createObjectURL = vi.fn().mockReturnValue("blob:url");
    const revokeObjectURL = vi.fn();
    URL.createObjectURL = createObjectURL;
    URL.revokeObjectURL = revokeObjectURL;

    const clickSpy = vi.fn();
    const origCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = origCreateElement(tag);
      if (tag === "a") {
        el.click = clickSpy;
      }
      return el;
    });

    downloadJSON({ key: "value" }, "test.json");

    expect(createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:url");
  });
});
