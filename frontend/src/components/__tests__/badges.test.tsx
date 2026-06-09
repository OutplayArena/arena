import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { outcomeBadge, statusBadge } from "../badges";

describe("outcomeBadge", () => {
  it("returns null for null winner", () => {
    expect(outcomeBadge(null)).toBeNull();
  });

  it("shows Agent A for winner A", () => {
    const badge = outcomeBadge("A");
    render(<>{badge}</>);
    expect(screen.getByText("Agent A")).toBeInTheDocument();
  });

  it("shows Agent B for winner B", () => {
    const badge = outcomeBadge("B");
    render(<>{badge}</>);
    expect(screen.getByText("Agent B")).toBeInTheDocument();
  });

  it("shows Draw for Tie", () => {
    const badge = outcomeBadge("Tie");
    render(<>{badge}</>);
    expect(screen.getByText("Draw")).toBeInTheDocument();
  });
});

describe("statusBadge", () => {
  it("renders ready status", () => {
    const badge = statusBadge("ready");
    render(<>{badge}</>);
    expect(screen.getByText("ready")).toBeInTheDocument();
  });

  it("renders running status", () => {
    const badge = statusBadge("running");
    render(<>{badge}</>);
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("renders completed status", () => {
    const badge = statusBadge("completed");
    render(<>{badge}</>);
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("renders failed status", () => {
    const badge = statusBadge("failed");
    render(<>{badge}</>);
    expect(screen.getByText("failed")).toBeInTheDocument();
  });

  it("renders unknown status", () => {
    const badge = statusBadge("unknown-status");
    render(<>{badge}</>);
    expect(screen.getByText("unknown-status")).toBeInTheDocument();
  });
});
