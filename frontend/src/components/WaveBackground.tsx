import { memo } from "react";

const VW = 1200;

interface WaveSpec {
  cy: number;
  amplitude: number;
  wavelength: number;
  phase: number;
  color: string;
  opacity: number;
  strokeWidth: number;
  duration: number;
}

const WAVES: WaveSpec[] = [
  // Upper band — teal, slow and wide
  { cy: 95,  amplitude: 16, wavelength: 420, phase: 0,            color: "var(--color-accent)",  opacity: 0.22, strokeWidth: 1.6, duration: 24 },
  // Upper-mid — teal secondary
  { cy: 230, amplitude:  9, wavelength: 560, phase: Math.PI / 4,  color: "var(--color-accent)",  opacity: 0.14, strokeWidth: 1.2, duration: 36 },
  // Lower-mid — agent-b / blue
  { cy: 370, amplitude: 13, wavelength: 480, phase: Math.PI * 0.6,color: "var(--color-agent-b)", opacity: 0.16, strokeWidth: 1.4, duration: 30 },
  // Lower band — agent-a / orange, livelier
  { cy: 495, amplitude: 19, wavelength: 360, phase: Math.PI / 2,  color: "var(--color-agent-a)", opacity: 0.18, strokeWidth: 1.5, duration: 19 },
];

// Pre-compute paths at module level — no runtime cost per render.
// Each path extends one extra wavelength to the right so the translateX
// animation can loop back seamlessly.
function makePath({ cy, amplitude, wavelength, phase }: WaveSpec): string {
  const totalWidth = VW + wavelength;
  const parts: string[] = [];
  for (let x = 0; x <= totalWidth; x += 6) {
    const y = cy + amplitude * Math.sin((2 * Math.PI * x) / wavelength + phase);
    parts.push(`${x === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`);
  }
  return parts.join(" ");
}

const PATHS = WAVES.map(makePath);

export const WaveBackground = memo(function WaveBackground() {
  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none select-none"
      viewBox={`0 0 ${VW} 600`}
      preserveAspectRatio="xMidYMid slice"
      overflow="hidden"
      aria-hidden="true"
    >
      {WAVES.map((w, i) => (
        <g key={i} opacity={w.opacity}>
          <path
            d={PATHS[i]}
            fill="none"
            stroke={w.color}
            strokeWidth={w.strokeWidth}
          />
          {/* Translate left by one wavelength — sine is periodic so it loops invisibly */}
          <animateTransform
            attributeName="transform"
            type="translate"
            from="0 0"
            to={`${-w.wavelength} 0`}
            dur={`${w.duration}s`}
            repeatCount="indefinite"
          />
        </g>
      ))}
    </svg>
  );
});
