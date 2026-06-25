import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { DatePicker } from "../DatePicker";
import { formatYMD, parseYMD } from "../dateShared";
import { renderWithProviders } from "../../test-utils";

beforeEach(() => {
  vi.useRealTimers();
});

describe("DatePicker utilities", () => {
  it("formatYMD produces YYYY-MM-DD", () => {
    expect(formatYMD(new Date(2024, 0, 15))).toBe("2024-01-15");
    expect(formatYMD(new Date(2024, 11, 1))).toBe("2024-12-01");
  });

  it("parseYMD parses YYYY-MM-DD into a local Date", () => {
    const d = parseYMD("2024-01-15");
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2024);
    expect(d!.getMonth()).toBe(0);
    expect(d!.getDate()).toBe(15);
  });

  it("parseYMD returns null for invalid input", () => {
    expect(parseYMD("")).toBeNull();
    expect(parseYMD("not a date")).toBeNull();
    expect(parseYMD("2024-1-15")).toBeNull();
  });
});

describe("DatePicker", () => {
  it("renders the trigger with a placeholder when no value is set", () => {
    renderWithProviders(<DatePicker value="" onChange={() => {}} label="From" testId="dp" />);
    expect(screen.getByTestId("dp")).toBeInTheDocument();
    expect(screen.getByText("any")).toBeInTheDocument();
  });

  it("renders the trigger with the value when one is set", () => {
    renderWithProviders(<DatePicker value="2025-01-15" onChange={() => {}} label="From" testId="dp" />);
    expect(screen.getByText("2025-01-15")).toBeInTheDocument();
  });

  it("opens the calendar popup when the trigger is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DatePicker value="" onChange={() => {}} label="From" testId="dp" />);
    await user.click(screen.getByTestId("dp"));
    await waitFor(() => {
      expect(screen.getByTestId("dp-popup")).toBeInTheDocument();
    });
    // The popup shows a month header and day cells.
    expect(screen.getByTestId("dp-prev")).toBeInTheDocument();
    expect(screen.getByTestId("dp-next")).toBeInTheDocument();
    expect(screen.getByTestId("dp-today")).toBeInTheDocument();
  });

  it("selects a day when a calendar cell is clicked", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<DatePicker value="" onChange={onChange} label="From" testId="dp" />);
    await user.click(screen.getByTestId("dp"));
    const popup = await screen.findByTestId("dp-popup");
    // Pick the first enabled day cell.
    const dayButtons = Array.from(
      popup.querySelectorAll<HTMLButtonElement>("button[data-testid^='dp-day-']"),
    );
    const enabled = dayButtons.find((b) => !b.disabled);
    expect(enabled).toBeDefined();
    const ymd = enabled!.getAttribute("data-testid")!.replace("dp-day-", "");
    await user.click(enabled!);
    expect(onChange).toHaveBeenCalledWith(ymd);
  });

  it("closes the popup after a day is selected", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DatePicker value="" onChange={() => {}} label="From" testId="dp" />);
    await user.click(screen.getByTestId("dp"));
    const popup = await screen.findByTestId("dp-popup");
    const dayButtons = Array.from(
      popup.querySelectorAll<HTMLButtonElement>("button[data-testid^='dp-day-']"),
    );
    const enabled = dayButtons.find((b) => !b.disabled)!;
    await user.click(enabled);
    await waitFor(() => {
      expect(screen.queryByTestId("dp-popup")).not.toBeInTheDocument();
    });
  });

  it("clears the value via the inline × button", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <DatePicker value="2025-01-15" onChange={onChange} label="From" testId="dp" />,
    );
    await user.click(screen.getByTestId("dp-clear"));
    expect(onChange).toHaveBeenCalledWith("");
  });

  it("clears the value via the popup's Clear link", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <DatePicker value="2025-01-15" onChange={onChange} label="From" testId="dp" />,
    );
    await user.click(screen.getByTestId("dp"));
    await user.click(screen.getByTestId("dp-popup-clear"));
    expect(onChange).toHaveBeenCalledWith("");
  });

  it("navigates months with the prev / next buttons", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DatePicker value="2025-06-15" onChange={() => {}} label="From" testId="dp" />);
    await user.click(screen.getByTestId("dp"));
    const popup = await screen.findByTestId("dp-popup");
    // Open on June 2025 (the value's month).
    expect(popup.textContent).toContain("June 2025");
    await user.click(screen.getByTestId("dp-prev"));
    expect(popup.textContent).toContain("May 2025");
    await user.click(screen.getByTestId("dp-prev"));
    expect(popup.textContent).toContain("April 2025");
    await user.click(screen.getByTestId("dp-next"));
    await user.click(screen.getByTestId("dp-next"));
    await user.click(screen.getByTestId("dp-next"));
    expect(popup.textContent).toContain("July 2025");
  });

  it("disables days outside the minDate / maxDate range", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <DatePicker
        value="2025-02-15"
        onChange={() => {}}
        minDate="2025-02-10"
        maxDate="2025-02-20"
        label="From"
        testId="dp"
      />,
    );
    await user.click(screen.getByTestId("dp"));
    const popup = await screen.findByTestId("dp-popup");
    const dayButtons = Array.from(
      popup.querySelectorAll<HTMLButtonElement>("button[data-testid^='dp-day-']"),
    );
    // Feb 5 should be disabled (before minDate 2025-02-10).
    const feb5 = dayButtons.find((b) => b.getAttribute("data-testid") === "dp-day-2025-02-05");
    expect(feb5).toBeDefined();
    expect(feb5!.disabled).toBe(true);
    // Feb 15 should be enabled.
    const feb15 = dayButtons.find((b) => b.getAttribute("data-testid") === "dp-day-2025-02-15");
    expect(feb15).toBeDefined();
    expect(feb15!.disabled).toBe(false);
    // Feb 25 should be disabled (after maxDate 2025-02-20).
    const feb25 = dayButtons.find((b) => b.getAttribute("data-testid") === "dp-day-2025-02-25");
    expect(feb25).toBeDefined();
    expect(feb25!.disabled).toBe(true);
  });

  it("closes the popup when Escape is pressed", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DatePicker value="" onChange={() => {}} label="From" testId="dp" />);
    await user.click(screen.getByTestId("dp"));
    await waitFor(() => {
      expect(screen.getByTestId("dp-popup")).toBeInTheDocument();
    });
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByTestId("dp-popup")).not.toBeInTheDocument();
    });
  });

  it("selects today when the Today button is clicked", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<DatePicker value="" onChange={onChange} label="From" testId="dp" />);
    await user.click(screen.getByTestId("dp"));
    await user.click(screen.getByTestId("dp-today"));
    const today = formatYMD(new Date());
    expect(onChange).toHaveBeenCalledWith(today);
  });
});
