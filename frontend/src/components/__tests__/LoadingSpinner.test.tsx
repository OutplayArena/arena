import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoadingSpinner } from "../LoadingSpinner";

describe("LoadingSpinner", () => {
  it("renders an SVG spinner", () => {
    const { container } = render(<LoadingSpinner />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveClass("animate-spin");
  });

  it("applies custom className", () => {
    const { container } = render(<LoadingSpinner className="custom-class" />);
    expect(container.firstChild).toHaveClass("custom-class");
  });

  it("renders without className", () => {
    const { container } = render(<LoadingSpinner />);
    const div = container.firstChild as HTMLElement;
    expect(div).toHaveClass("flex", "items-center", "justify-center");
  });
});
