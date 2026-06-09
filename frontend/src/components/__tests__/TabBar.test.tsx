import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { TabBar } from "../TabBar";

describe("TabBar", () => {
  const tabs = [
    { id: "config", label: "Config" },
    { id: "live", label: "Live View" },
    { id: "history", label: "History" },
  ];

  it("renders all tabs", () => {
    render(<TabBar tabs={tabs} activeTab="config" onTabChange={() => {}} />);
    expect(screen.getByText("Config")).toBeInTheDocument();
    expect(screen.getByText("Live View")).toBeInTheDocument();
    expect(screen.getByText("History")).toBeInTheDocument();
  });

  it("sets aria-selected on active tab", () => {
    render(<TabBar tabs={tabs} activeTab="live" onTabChange={() => {}} />);
    const liveTab = screen.getByText("Live View");
    expect(liveTab).toHaveAttribute("aria-selected", "true");
  });

  it("calls onTabChange when a tab is clicked", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(<TabBar tabs={tabs} activeTab="config" onTabChange={onTabChange} />);
    await user.click(screen.getByText("History"));
    expect(onTabChange).toHaveBeenCalledWith("history");
  });

  it("renders correct number of tabs", () => {
    render(<TabBar tabs={[{ id: "a", label: "A" }]} activeTab="a" onTabChange={() => {}} />);
    expect(screen.getAllByRole("tab")).toHaveLength(1);
  });
});

import { vi } from "vitest";
