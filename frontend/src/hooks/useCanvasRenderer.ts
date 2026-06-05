import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Match, MatchRound } from "../types";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  color: string;
}

type PlayerSide = "A" | "B" | "Tie";

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function battlefieldName(index: number): string {
  return `battlefield_${index + 1}`;
}

function clampActionValue(
  round: MatchRound | null,
  key: "action_a" | "action_b",
  index: number,
): number {
  if (!round) return 0;
  const arr = round[key] as unknown[] | undefined;
  const val = arr?.[index];
  return typeof val === "number" ? val : 0;
}

function fieldWinner(round: MatchRound | null, index: number): PlayerSide {
  const a = clampActionValue(round, "action_a", index);
  const b = clampActionValue(round, "action_b", index);
  if (a > b) return "A";
  if (b > a) return "B";
  return "Tie";
}

function winnerColor(winner: PlayerSide): string {
  const style = getComputedStyle(document.documentElement);
  if (winner === "A") return style.getPropertyValue("--color-agent-a").trim() || "#f28c38";
  if (winner === "B") return style.getPropertyValue("--color-agent-b").trim() || "#2d9cdb";
  return style.getPropertyValue("--color-gold").trim() || "#d5a11e";
}

function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function fillRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
  fill: string | CanvasGradient,
  stroke?: string,
  lineWidth = 1,
) {
  drawRoundedRect(ctx, x, y, w, h, r);
  ctx.fillStyle = fill;
  ctx.fill();
  if (stroke) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = lineWidth;
    ctx.stroke();
  }
}

interface BFRect {
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

function battlefieldRects(
  width: number,
  height: number,
  count: number,
): BFRect[] {
  const margin = Math.max(12, width * 0.022);
  const gap = Math.max(7, width * 0.01);
  const top = Math.max(24, height * 0.04);
  const rows = count > 6 ? 2 : 1;
  const columns = Math.ceil(count / rows);
  const available = width - margin * 2 - gap * (columns - 1);
  const cardWidth = available / columns;
  const rowGap = rows > 1 ? Math.max(10, height * 0.018) : 0;
  const cardHeight = Math.min(
    rows > 1 ? 190 : 260,
    Math.max(148, (height - top - 32 - rowGap * (rows - 1)) / rows),
  );

  return Array.from({ length: count }, (_, index) => {
    const row = Math.floor(index / columns);
    const column = index % columns;
    return {
      name: battlefieldName(index),
      x: margin + column * (cardWidth + gap),
      y: top + row * (cardHeight + rowGap) + Math.sin(index * 1.55) * 3,
      w: cardWidth,
      h: cardHeight,
    };
  });
}

function drawBackground(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
) {
  const style = getComputedStyle(document.documentElement);
  const surface = style.getPropertyValue("--color-surface").trim() || "#ffffff";
  const surfaceSoft = style.getPropertyValue("--color-surface-soft").trim() || "#fbfaf5";
  const line = style.getPropertyValue("--color-line").trim() || "#dde1de";
  const agentA = style.getPropertyValue("--color-agent-a").trim() || "#f28c38";
  const agentB = style.getPropertyValue("--color-agent-b").trim() || "#2d9cdb";

  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, surface);
  gradient.addColorStop(0.52, surfaceSoft);
  gradient.addColorStop(1, surface);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.globalAlpha = 0.08;
  ctx.strokeStyle = line;
  ctx.lineWidth = 1;
  const gridSize = Math.max(28, Math.floor(width / 20));
  for (let x = gridSize; x < width; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = gridSize; y < height; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.globalAlpha = 0.06;
  for (let i = 0; i < 8; i += 1) {
    const x = (i * 197 + 41) % width;
    const y = (i * 137 + 23) % height;
    const color = i % 2 === 0 ? agentA : agentB;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, 2.5, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawFlag(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  color: string,
  side: number,
  progress: number,
) {
  const drop = (1 - progress) * -24;
  ctx.save();
  ctx.translate(0, drop);
  ctx.globalAlpha = progress;
  ctx.strokeStyle = "#151817";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x, y - 38);
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(x, y - 36);
  ctx.lineTo(x + side * 30, y - 29);
  ctx.lineTo(x, y - 20);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function drawMarbleCluster(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  count: number,
  color: string,
  compact: boolean,
  align: "left" | "right" = "left",
) {
  const maxVisible = compact ? 10 : 14;
  const total = Math.min(count, 64);
  const visible = total === 0 ? 0 : Math.max(1, Math.min(maxVisible, Math.ceil(total / 3 * 2)));
  const overflow = total > Math.round(visible * 1.5) ? total : 0;

  const r = compact ? 2.8 : 3.4;
  const gap = compact ? 2 : 2.5;
  const cols = compact ? 5 : 6;
  const rowHeight = r * 2 + gap;
  const maxRows = compact ? 3 : 4;
  const actualRows = Math.min(maxRows, Math.ceil(visible / cols));
  const dir = align === "left" ? 1 : -1;

  for (let i = 0; i < visible; i += 1) {
    const row = Math.floor(i / cols);
    const col = i % cols;
    if (row >= maxRows) break;

    const rowOffset = (cols - Math.min(cols, visible - row * cols)) * 0.5;
    const px = x + dir * (col + rowOffset) * (r * 2 + gap);
    const py = y - row * rowHeight;

    const grad = ctx.createRadialGradient(-r * 0.25, -r * 0.3, r * 0.15, 0, 0, r);
    grad.addColorStop(0, brighten(color, 0.4));
    grad.addColorStop(0.6, color);
    grad.addColorStop(1, darken(color, 0.3));
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fill();
  }

  if (overflow > 0) {
    const lastRow = Math.min(actualRows - 1, Math.floor((visible - 1) / cols));
    const lastCol = (visible - 1) % cols;
    const rowOff = (cols - Math.min(cols, visible - lastRow * cols)) * 0.5;
    const lx = x + dir * ((lastCol + rowOff) * (r * 2 + gap) + r * 2 + gap + 2);
    const ly = y - lastRow * rowHeight;
    ctx.fillStyle = color;
    ctx.font = `700 ${compact ? 8 : 9}px ui-monospace, sans-serif`;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(`+${overflow}`, lx, ly);
  }
}

function brighten(hex: string, amount: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const clamp = (v: number) => Math.min(255, Math.round(v + (255 - v) * amount));
  return `rgb(${clamp(r)},${clamp(g)},${clamp(b)})`;
}

function darken(hex: string, amount: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const clamp = (v: number) => Math.max(0, Math.round(v * (1 - amount)));
  return `rgb(${clamp(r)},${clamp(g)},${clamp(b)})`;
}


function drawBattlefield(
  ctx: CanvasRenderingContext2D,
  rect: BFRect,
  round: MatchRound | null,
  index: number,
  t: number,
) {
  const isRevealed = !!round;
  const winner = isRevealed ? fieldWinner(round, index) : null;
  const style = getComputedStyle(document.documentElement);
  const surface = style.getPropertyValue("--color-surface").trim() || "#ffffff";
  const surfaceContainer = style.getPropertyValue("--color-surface-container").trim() || "#f4f3ed";
  const line = style.getPropertyValue("--color-line").trim() || "#dde1de";
  const muted = style.getPropertyValue("--color-muted").trim() || "#6c747a";
  const agentAColor = style.getPropertyValue("--color-agent-a").trim() || "#f28c38";
  const agentBColor = style.getPropertyValue("--color-agent-b").trim() || "#2d9cdb";
  const gold = style.getPropertyValue("--color-gold").trim() || "#d5a11e";

  const cardColor = [surface, surfaceContainer, surface, surfaceContainer, surface][index % 5];
  const border = winner ? winnerColor(winner) : line;
  const radius = 10;

  ctx.save();
  ctx.shadowColor = winner ? border : "rgba(38,50,56,0.06)";
  ctx.shadowBlur = winner ? 12 + Math.sin(t / 100) * 3 : 6;
  ctx.shadowOffsetY = 3;
  fillRoundedRect(ctx, rect.x, rect.y, rect.w, rect.h, radius, cardColor, border, winner ? 2 : 1);
  ctx.restore();

  const wash = ctx.createLinearGradient(rect.x, rect.y, rect.x, rect.y + rect.h);
  wash.addColorStop(0, "rgba(255,255,255,0.35)");
  wash.addColorStop(0.6, "rgba(255,255,255,0.02)");
  wash.addColorStop(1, "rgba(38,50,56,0.04)");
  fillRoundedRect(ctx, rect.x + 1, rect.y + 1, rect.w - 2, rect.h - 2, radius, wash);

  ctx.fillStyle = muted;
  ctx.font = `800 10px ui-monospace, sans-serif`;
  ctx.textAlign = "center";
  ctx.fillText(rect.name, rect.x + rect.w / 2, rect.y + 20);

  const centerX = rect.x + rect.w / 2;
  const actionA = clampActionValue(round, "action_a", index);
  const actionB = clampActionValue(round, "action_b", index);
  const compact = rect.w < 180;
  const fontSize = compact ? 17 : 20;

  // Value chips
  const chipW = compact ? 36 : 42;
  const chipH = 28;
  const chipY = rect.y + 34;

  const aLabel = isRevealed ? String(actionA) : "?";
  ctx.font = `900 ${fontSize}px ui-monospace, monospace`;
  const aW = Math.max(chipW, ctx.measureText(aLabel).width + 16);
  fillRoundedRect(ctx, rect.x + 8, chipY, aW, chipH, 6, "rgba(8, 11, 11, 0.7)", agentAColor, 1.5);
  ctx.fillStyle = agentAColor;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(aLabel, rect.x + 8 + aW / 2, chipY + chipH / 2 + 1);

  const bLabel = isRevealed ? String(actionB) : "?";
  ctx.font = `900 ${fontSize}px ui-monospace, monospace`;
  const bW = Math.max(chipW, ctx.measureText(bLabel).width + 16);
  fillRoundedRect(ctx, rect.x + rect.w - 8 - bW, chipY, bW, chipH, 6, "rgba(8, 11, 11, 0.7)", agentBColor, 1.5);
  ctx.fillStyle = agentBColor;
  ctx.textAlign = "center";
  ctx.fillText(bLabel, rect.x + rect.w - 8 - bW / 2, chipY + chipH / 2 + 1);

  ctx.textBaseline = "alphabetic";

  // Proportional bar
  if (isRevealed && (actionA > 0 || actionB > 0)) {
    const barX = rect.x + 12;
    const barY = chipY + chipH + 8;
    const barW = rect.w - 24;
    const barH = compact ? 8 : 10;
    const total = actionA + actionB;
    const ratio = total > 0 ? actionA / total : 0.5;

    fillRoundedRect(ctx, barX, barY, barW, barH, barH / 2, "rgba(38,50,56,0.08)");

    const aW2 = barW * ratio;
    if (aW2 > 1) {
      const aGrad = ctx.createLinearGradient(barX, barY, barX + aW2, barY);
      aGrad.addColorStop(0, agentAColor);
      aGrad.addColorStop(1, brighten(agentAColor, 0.2));
      fillRoundedRect(ctx, barX, barY, aW2, barH, barH / 2, aGrad);
    }

    const bW2 = barW * (1 - ratio);
    if (bW2 > 1) {
      const bGrad = ctx.createLinearGradient(barX + barW - bW2, barY, barX + barW, barY);
      bGrad.addColorStop(0, brighten(agentBColor, 0.2));
      bGrad.addColorStop(1, agentBColor);
      fillRoundedRect(ctx, barX + barW - bW2, barY, bW2, barH, barH / 2, bGrad);
    }
  }

  // Center divider
  const dividerTop = chipY + chipH + (compact ? 26 : 32);
  const dividerBottom = rect.y + rect.h - 14;
  ctx.save();
  ctx.globalAlpha = 0.1;
  ctx.strokeStyle = line;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(centerX, dividerTop);
  ctx.lineTo(centerX, dividerBottom);
  ctx.stroke();
  ctx.restore();

  // Marble clusters at bottom
  const baseY = dividerBottom - 2;
  const clusterPadding = 6;

  if (isRevealed) {
    drawMarbleCluster(ctx, rect.x + clusterPadding, baseY, actionA, agentAColor, compact);
    drawMarbleCluster(ctx, rect.x + rect.w - clusterPadding, baseY, actionB, agentBColor, compact, "right");
  } else {
    ctx.globalAlpha = 0.12;
    drawMarbleCluster(ctx, rect.x + clusterPadding, baseY, actionA, agentAColor, compact);
    drawMarbleCluster(ctx, rect.x + rect.w - clusterPadding, baseY, actionB, agentBColor, compact, "right");
    ctx.globalAlpha = 1;
  }

  // Winner indicator
  if (winner) {
    const winY = dividerTop + (dividerBottom - dividerTop) * 0.65;

    if (winner === "Tie") {
      ctx.fillStyle = gold;
      ctx.font = `900 ${compact ? 16 : 20}px ui-monospace, sans-serif`;
      ctx.textAlign = "center";
      ctx.fillText("Draw", centerX, winY);
    } else {
      drawFlag(ctx, centerX, winY + 12, winner === "A" ? agentAColor : agentBColor, winner === "A" ? 1 : -1, 1);
    }
  }
}

function spawnParticles(
  width: number,
  height: number,
  count: number,
  round: MatchRound | null,
  particles: Particle[],
) {
  if (!round) return;
  const rects = battlefieldRects(width, height, count);
  for (let i = 0; i < count; i += 1) {
    const rect = rects[i];
    const color = winnerColor(fieldWinner(round, i));
    for (let j = 0; j < 18; j += 1) {
      particles.push({
        x: rect.x + rect.w / 2,
        y: rect.y + rect.h / 2,
        vx: (Math.random() - 0.5) * 4.8,
        vy: (Math.random() - 0.5) * 3.8 - 0.9,
        life: 42 + Math.random() * 28,
        color,
      });
    }
  }
}

function drawParticles(ctx: CanvasRenderingContext2D, particles: Particle[]) {
  for (let i = particles.length - 1; i >= 0; i -= 1) {
    const p = particles[i];
    p.x += p.vx;
    p.y += p.vy;
    p.vy += 0.035;
    p.life -= 1;

    if (p.life <= 0) {
      particles.splice(i, 1);
      continue;
    }

    ctx.globalAlpha = Math.max(0, p.life / 70);
    ctx.fillStyle = p.color;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3.1, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

export interface AnimatedScores {
  displayedScoreA: number;
  displayedScoreB: number;
}

export function useCanvasRenderer(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  activeMatch: Match | null,
  activeRoundIndex: number,
  onRenderError?: (err: Error) => void,
): AnimatedScores {
  const particlesRef = useRef<Particle[]>([]);
  const revealStartRef = useRef(0);
  const displayedARef = useRef(0);
  const displayedBRef = useRef(0);
  const prevRoundRef = useRef(-1);
  const [scores, setScores] = useState<AnimatedScores>({
    displayedScoreA: 0,
    displayedScoreB: 0,
  });
  const scoresRef = useRef(scores);

  useEffect(() => {
    scoresRef.current = scores;
  }, [scores]);

  const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;

  useEffect(() => {
    if (activeRoundIndex !== prevRoundRef.current) {
      revealStartRef.current = performance.now();
      prevRoundRef.current = activeRoundIndex;

      const canvas = canvasRef.current;
      if (canvas && activeMatch) {
        const rect = canvas.getBoundingClientRect();
        spawnParticles(
          rect.width,
          rect.height,
          activeMatch.num_battlefields,
          activeMatch.history[activeRoundIndex] ?? null,
          particlesRef.current,
        );
      }
    }
  }, [activeRoundIndex, activeMatch, canvasRef]);

  const canvasStateRef = useRef({ activeMatch, activeRoundIndex });

  useEffect(() => {
    canvasStateRef.current = { activeMatch, activeRoundIndex };
  });

  const renderRef = useRef<(t: number) => void>(() => {});

  const onRenderErrorRef = useRef(onRenderError);
  useEffect(() => {
    onRenderErrorRef.current = onRenderError;
  }, [onRenderError]);

  useLayoutEffect(() => {
    renderRef.current = (t: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
      requestAnimationFrame((nextT: number) => renderRef.current(nextT));
      return;
    }

    try {
    const width = rect.width;
    const height = rect.height;

    canvas.width = Math.max(320, Math.floor(width * dpr));
    canvas.height = Math.max(320, Math.floor(height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const { activeMatch: match, activeRoundIndex: roundIndex } =
      canvasStateRef.current;
    const round = match?.history?.[roundIndex] ?? null;

    const targetA = round ? round.total_score_a : 0;
    const targetB = round ? round.total_score_b : 0;
    displayedARef.current = lerp(displayedARef.current, targetA, 0.12);
    displayedBRef.current = lerp(displayedBRef.current, targetB, 0.12);

    const da = displayedARef.current;
    const db = displayedBRef.current;
    const prev = scoresRef.current;
    if (
      Math.abs(da - prev.displayedScoreA) > 0.5 ||
      Math.abs(db - prev.displayedScoreB) > 0.5
    ) {
      const newScores = {
        displayedScoreA: Math.abs(da - targetA) < 0.03 ? targetA : da,
        displayedScoreB: Math.abs(db - targetB) < 0.03 ? targetB : db,
      };
      setScores(newScores);
    }

    drawBackground(ctx, width, height);
    const bfs = battlefieldRects(
      width,
      height,
      match?.num_battlefields ??
        (round ? (round.action_a as number[]).length : 5),
    );
    const bfCount = bfs.length;
    for (let i = 0; i < bfCount; i += 1) {
      drawBattlefield(ctx, bfs[i], round, i, t);
    }
    drawParticles(ctx, particlesRef.current);

    requestAnimationFrame((nextT: number) => renderRef.current(nextT));
    } catch (err) {
      console.error("Canvas render error:", err);
      if (onRenderErrorRef.current) {
        onRenderErrorRef.current(err instanceof Error ? err : new Error(String(err)));
      }
    }
  };
  });

  useEffect(() => {
    const raf = requestAnimationFrame((nextT: number) =>
      renderRef.current(nextT),
    );
    return () => cancelAnimationFrame(raf);
  }, []);

  return scores;
}
