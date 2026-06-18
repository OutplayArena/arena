import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { InteractiveAgentPanel } from "../InteractiveAgentPanel";
import { AppProvider } from "../../state";

function renderWithProvider(ui: React.ReactElement) {
  return render(<AppProvider>{ui}</AppProvider>);
}

describe("InteractiveAgentPanel", () => {
  it("returns null when no interactive agents", () => {
    const { container } = renderWithProvider(<InteractiveAgentPanel />);
    expect(container.firstChild).toBeNull();
  });
});
