import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { DatePicker } from '../DatePicker';

describe('Inspect dark mode icon color', () => {
  it('shows the icon color in light mode', () => {
    document.documentElement.classList.remove('dark');
    const { getByTestId } = render(
      <DatePicker value="2026-06-25" onChange={() => {}} label="From" testId="dp" />
    );
    const trigger = getByTestId('dp');
    const svg = trigger.querySelector('svg')!;
    const cs = getComputedStyle(svg);
    console.log('LIGHT: svg class=', svg.getAttribute('class'));
    console.log('LIGHT: color=', cs.color);
    console.log('LIGHT: stroke=', cs.stroke);
    expect(svg).toBeTruthy();
  });

  it('shows the icon color in dark mode', () => {
    document.documentElement.classList.add('dark');
    const { getByTestId } = render(
      <DatePicker value="2026-06-25" onChange={() => {}} label="From" testId="dp" />
    );
    const trigger = getByTestId('dp');
    const svg = trigger.querySelector('svg')!;
    const cs = getComputedStyle(svg);
    console.log('DARK:  svg class=', svg.getAttribute('class'));
    console.log('DARK:  color=', cs.color);
    console.log('DARK:  stroke=', cs.stroke);
    expect(svg).toBeTruthy();
    document.documentElement.classList.remove('dark');
  });
});
