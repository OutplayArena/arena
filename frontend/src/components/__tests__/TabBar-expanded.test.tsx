import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { TabBar } from "../TabBar";

describe("TabBar — keyboard navigation", () => {
  const tabs = [
    { id: "config", label: "Config" },
    { id: "live", label: "Live View" },
    { id: "history", label: "History" },
  ];

  it("has correct ARIA roles", () => {
    render(<TabBar tabs={tabs} activeTab="config" onTabChange={() => {}} />);
    const nav = screen.getByRole("tablist");
    expect(nav).toBeInTheDocument();
    const tabButtons = screen.getAllByRole("tab");
    expect(tabButtons).toHaveLength(3);
  });

  it("sets tabIndex=0 on active tab, -1 on others", () => {
    render(<TabBar tabs={tabs} activeTab="live" onTabChange={() => {}} />);
    const buttons = screen.getAllByRole("tab");
    expect(buttons[0].getAttribute("tabIndex")).toBe("-1");
    expect(buttons[1].getAttribute("tabIndex")).toBe("0");
    expect(buttons[2].getAttribute("tabIndex")).toBe("-1");
  });

  it("sets aria-controls on tabs", () => {
    render(<TabBar tabs={tabs} activeTab="config" onTabChange={() => {}} />);
    expect(screen.getByText("Config")).toHaveAttribute("aria-controls", "tabpanel-config");
  });

  it("ArrowRight cycles to next tab", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(<TabBar tabs={tabs} activeTab="config" onTabChange={onTabChange} />);

    const configTab = screen.getByText("Config");
    await user.type(configTab, "{ArrowRight}");

    expect(onTabChange).toHaveBeenCalledWith("live");
  });

  it("ArrowLeft cycles to previous tab", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(<TabBar tabs={tabs} activeTab="config" onTabChange={onTabChange} />);

    const configTab = screen.getByText("Config");
    await user.type(configTab, "{ArrowLeft}");

    expect(onTabChange).toHaveBeenCalledWith("history");
  });

  it("ArrowLeft wraps around to last tab from first", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(<TabBar tabs={tabs} activeTab="config" onTabChange={onTabChange} />);

    const configTab = screen.getByText("Config");
    await user.type(configTab, "{ArrowLeft}");

    expect(onTabChange).toHaveBeenCalledWith("history");
  });

  it("ArrowRight wraps around to first tab from last", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(<TabBar tabs={tabs} activeTab="history" onTabChange={onTabChange} />);

    const historyTab = screen.getByText("History");
    await user.type(historyTab, "{ArrowRight}");

    expect(onTabChange).toHaveBeenCalledWith("config");
  });
});
