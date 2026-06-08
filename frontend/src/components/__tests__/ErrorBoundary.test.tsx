import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "../ErrorBoundary";

function ThrowError({ message }: { message: string }) {
  throw new Error(message);
}

describe("ErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <div>Child content</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("Child content")).toBeInTheDocument();
  });

  it("renders fallback UI on error", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <ThrowError message="Test explosion" />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Test explosion")).toBeInTheDocument();
    spy.mockRestore();
  });

  it("shows generic message when error has no message", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function ThrowEmptyError() {
      throw new Error();
    }
    render(
      <ErrorBoundary>
        <ThrowEmptyError />
      </ErrorBoundary>,
    );
    expect(screen.getByText("An unexpected error occurred.")).toBeInTheDocument();
    spy.mockRestore();
  });
});

