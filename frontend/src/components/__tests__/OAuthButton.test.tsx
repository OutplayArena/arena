import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OAuthButton } from "../OAuthButton";

describe("OAuthButton", () => {
  it("renders GitHub button with correct href", () => {
    render(<OAuthButton provider="github" />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/api/auth/github/login");
    expect(screen.getByText("Continue with GitHub")).toBeInTheDocument();
  });

  it("renders Google button with correct href", () => {
    render(<OAuthButton provider="google" />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/api/auth/google/login");
    expect(screen.getByText("Continue with Google")).toBeInTheDocument();
  });

  it("renders as an anchor tag", () => {
    render(<OAuthButton provider="github" />);
    expect(screen.getByRole("link").tagName).toBe("A");
  });
});
