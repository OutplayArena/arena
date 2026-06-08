import { useState } from "react";
import { useApp } from "@frontend/hooks/useApp";
import type { AnimatedScores } from "@frontend/hooks/useCanvasRenderer";

interface LiveViewProps {
  onScores?: (scores: AnimatedScores) => void;
  onToggleCollapse: () => void;
  createdAt?: string | null;
}

/* ---------- helpers ---------- */

type SuitKey = "h" | "d" | "c" | "s";

const SUIT: Record<SuitKey, { sym: string; ink: string }> = {
  h: { sym: "\u2665", ink: "#e53e3e" },
  d: { sym: "\u2666", ink: "#e53e3e" },
  c: { sym: "\u2663", ink: "#2d3748" },
  s: { sym: "\u2660", ink: "#2d3748" },
};

const STREET: Record<string, string> = {
  preflop: "Preflop",
  flop: "Flop",
  turn: "Turn",
  river: "River",
};

function parseCard(card: string): { rank: string; suit: SuitKey } | null {
  if (!card || card === "??") return null;
  const suit = card.slice(-1).toLowerCase();
  const rank = card.slice(0, -1);
  if (suit !== "h" && suit !== "d" && suit !== "c" && suit !== "s") return null;
  return { rank, suit };
}

function arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function obj(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : {};
}

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function num(v: unknown): number {
  return typeof v === "number" ? v : 0;
}

/* ---------- SVG card ---------- */

function CardView(p: { card: string; cx: number; cy: number; faceDown?: boolean }) {
  const parsed = parseCard(p.card);
  const w = 32;
  const h = 44;
  const r = 3;
  const x = p.cx - w / 2;
  const y = p.cy - h / 2;

  if (p.faceDown || !parsed) {
    return (
      <g>
        <rect x={x} y={y} width={w} height={h} rx={r} fill="#1a365d" stroke="#2a4a7a" strokeWidth={1.5} />
        <rect x={x + 3} y={y + 3} width={w - 6} height={h - 6} rx={2} fill="none" stroke="#3182ce" strokeWidth={1} opacity={0.35} />
        <line x1={x + 4} y1={y + 4} x2={x + w - 4} y2={y + h - 4} stroke="#3182ce" strokeWidth={0.5} opacity={0.2} />
        <line x1={x + w - 4} y1={y + 4} x2={x + 4} y2={y + h - 4} stroke="#3182ce" strokeWidth={0.5} opacity={0.2} />
      </g>
    );
  }

  const { sym, ink } = SUIT[parsed.suit];

  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={r} fill="#fff" stroke="#cbd5e0" strokeWidth={1} />
      <text x={x + 4} y={y + 11} fontSize={9} fontWeight="bold" fill={ink} fontFamily="ui-monospace,monospace">
        {parsed.rank}
      </text>
      <text x={p.cx} y={p.cy + 8} fontSize={14} fill={ink} textAnchor="middle" dominantBaseline="middle" fontFamily="serif">
        {sym}
      </text>
    </g>
  );
}

/* ---------- chip stack ---------- */

function ChipStack(p: { amt: number; cx: number; cy: number; colorVar: string }) {
  return (
    <g>
      <circle cx={p.cx} cy={p.cy + 4} r={7} fill={p.colorVar} opacity={0.25} />
      <circle cx={p.cx} cy={p.cy + 2} r={7} fill={p.colorVar} opacity={0.45} />
      <circle cx={p.cx} cy={p.cy} r={7} fill={p.colorVar} opacity={0.75} stroke={p.colorVar} strokeWidth={1} />
      <text
        x={p.cx}
        y={p.cy - 13}
        fontSize={10}
        fontWeight="bold"
        fill="var(--color-ink)"
        textAnchor="middle"
        fontFamily="ui-monospace,monospace"
      >
        ${p.amt}
      </text>
    </g>
  );
}

/* ---------- chair ---------- */

function Chair(p: { cx: number; cy: number; label: string }) {
  return (
    <g>
      <circle cx={p.cx} cy={p.cy} r={22} fill="none" stroke="var(--color-gold)" strokeWidth={2.5} />
      <circle cx={p.cx} cy={p.cy} r={17} fill="#e53e3e" />
      <circle cx={p.cx} cy={p.cy} r={12} fill="none" stroke="var(--color-gold)" strokeWidth={1} opacity={0.4} />
      <text
        x={p.cx}
        y={p.cy - 30}
        fontSize={10}
        fontWeight="bold"
        fill="var(--color-ink)"
        textAnchor="middle"
        fontFamily="ui-monospace,monospace"
      >
        {p.label}
      </text>
    </g>
  );
}

function EmptySeat(p: { cx: number; cy: number }) {
  return (
    <g>
      <circle cx={p.cx} cy={p.cy} r={20} fill="none" stroke="var(--color-line)" strokeWidth={1.5} />
      <circle cx={p.cx} cy={p.cy} r={15} fill="var(--color-surface-container)" opacity={0.3} />
    </g>
  );
}

/* ---------- community cards ---------- */

function CommunityCards(p: { cards: string[]; cx: number; cy: number }) {
  const cw = 32;
  const ch = 44;
  const gap = 6;
  const total = 5;
  const tw = total * cw + (total - 1) * gap;
  const sx = p.cx - tw / 2;

  return (
    <g>
      {Array.from({ length: total }, (_, i) => {
        const cx = sx + i * (cw + gap) + cw / 2;
        if (i < p.cards.length) {
          return <CardView key={i} card={p.cards[i]} cx={cx} cy={p.cy} />;
        }
        return (
          <g key={i}>
            <rect
              x={cx - cw / 2}
              y={p.cy - ch / 2}
              width={cw}
              height={ch}
              rx={3}
              fill="rgba(0,0,0,0.25)"
              stroke="rgba(255,255,255,0.5)"
              strokeWidth={1.5}
              strokeDasharray="4 3"
            />
          </g>
        );
      })}
    </g>
  );
}

/* ---------- deck & pot ---------- */

function Deck(p: { cx: number; cy: number }) {
  const w = 32;
  const h = 44;
  return (
    <g>
      <rect x={p.cx - w / 2 - 3} y={p.cy - h / 2 - 3} width={w} height={h} rx={3} fill="#1a365d" stroke="#2a4a7a" strokeWidth={1.5} />
      <rect x={p.cx - w / 2 - 1.5} y={p.cy - h / 2 - 1.5} width={w} height={h} rx={3} fill="#1a365d" stroke="#2a4a7a" strokeWidth={1.5} />
      <rect x={p.cx - w / 2} y={p.cy - h / 2} width={w} height={h} rx={3} fill="#1a365d" stroke="#2a4a7a" strokeWidth={1.5} />
      <rect x={p.cx - w / 2 + 3} y={p.cy - h / 2 + 3} width={w - 6} height={h - 6} rx={2} fill="none" stroke="#3182ce" strokeWidth={1} opacity={0.35} />
      <line x1={p.cx - w / 2 + 4} y1={p.cy - h / 2 + 4} x2={p.cx + w / 2 - 4} y2={p.cy + h / 2 - 4} stroke="#3182ce" strokeWidth={0.5} opacity={0.2} />
      <line x1={p.cx + w / 2 - 4} y1={p.cy - h / 2 + 4} x2={p.cx - w / 2 + 4} y2={p.cy + h / 2 - 4} stroke="#3182ce" strokeWidth={0.5} opacity={0.2} />
    </g>
  );
}

function Pot(p: { amt: number; cx: number; cy: number }) {
  return (
    <g>
      <circle cx={p.cx - 28} cy={p.cy} r={12} fill="var(--color-gold)" opacity={0.15} stroke="var(--color-gold)" strokeWidth={1.5} />
      <circle cx={p.cx - 28} cy={p.cy} r={6} fill="var(--color-gold)" opacity={0.3} />
      <text
        x={p.cx - 10}
        y={p.cy + 4}
        fontSize={11}
        fontWeight="bold"
        fill="var(--color-ink)"
        textAnchor="start"
        fontFamily="ui-monospace,monospace"
      >
        Pot: ${p.amt}
      </text>
    </g>
  );
}

/* ---------- main ---------- */

export default function TexasHoldEmLiveView(_props: LiveViewProps) {
  const { state, showRound } = useApp();
  const hasMatch = Boolean(state.activeMatch);
  const isGameRunning = Boolean(state.pendingGame);
  const match = state.activeMatch;

  const totalHands = match?.history.length ?? 0;
  const [viewIdx, setViewIdx] = useState<number | null>(null);
  const isReplaying = viewIdx !== null;

  const liveData = (match?.currentState as Record<string, unknown> | undefined) ?? null;
  const replayData = match && isReplaying
    ? (match.history[viewIdx]?.raw ?? null)
    : match
      ? (match.history[Math.max(0, state.activeRoundIndex)]?.raw ?? null)
      : null;
  const raw = !isReplaying ? liveData : replayData;
  const data = raw ?? replayData ?? {};

  const holeCardsObj = obj(data.hole_cards);
  const holeA = arr(holeCardsObj.A).filter((c): c is string => typeof c === "string");
  const holeB = arr(holeCardsObj.B).filter((c): c is string => typeof c === "string");
  const community = arr(data.community_cards).filter((c): c is string => typeof c === "string");
  const chipsLive = obj(data.chips);
  const chipsAfter = obj(data.chips_after);
  const chipsA = num(chipsLive.A) || num(chipsAfter.A) || 100;
  const chipsB = num(chipsLive.B) || num(chipsAfter.B) || 100;
  const pot = num(data.pot);
  const street = str(data.street);
  const currentPlayer = str(data.current_player);
  const totalScores = obj(data.total_scores);
  const phase = str(data.phase);
  const actionsArr = arr(data.street_actions);
  const matchComplete = match?.match_winner !== undefined;
  const isActive = isGameRunning || phase === "awaiting_action";

  /* ---- empty state ---- */

  if (!hasMatch) {
    return (
      <div className="flex flex-col h-full bg-surface-soft">
        <div className="shrink-0 flex items-center justify-between gap-4 px-5 py-3 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <span className="w-8 h-8 rounded-full bg-agent-a/15 border border-agent-a/40 flex items-center justify-center text-[11px] font-black text-agent-a">A</span>
            <span className="text-xs font-extrabold text-muted uppercase tracking-wider">Player A</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-extrabold text-muted uppercase tracking-wider">Player B</span>
            <span className="w-8 h-8 rounded-full bg-agent-b/15 border border-agent-b/40 flex items-center justify-center text-[11px] font-black text-agent-b">B</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center px-6">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-container flex items-center justify-center">
              {isGameRunning ? (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="text-accent/70 animate-spin">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              ) : (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="text-muted/60">
                  <rect x="3" y="3" width="7" height="7" rx="1" />
                  <rect x="14" y="3" width="7" height="7" rx="1" />
                  <rect x="3" y="14" width="7" height="7" rx="1" />
                  <rect x="14" y="14" width="7" height="7" rx="1" />
                </svg>
              )}
            </div>
            {isGameRunning ? (
              <>
                <p className="text-sm font-semibold text-muted">Waiting for first hand...</p>
                <p className="text-xs text-quiet mt-1.5">Dealing cards...</p>
              </>
            ) : (
              <>
                <p className="text-sm font-semibold text-muted">No game data yet</p>
                <p className="text-xs text-quiet mt-1.5">Start a game from the Config tab.</p>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  /* ---- table layout ---- */

  const TCX = 400;
  const TCY = 240;
  const ORX = 320;
  const ORY = 160;
  const IRX = 300;
  const IRY = 145;
  const SRX = 310;
  const SRY = 160;

  const seatAngle = (t: number) => ({
    x: TCX + SRX * Math.cos(t),
    y: TCY - SRY * Math.sin(t),
  });

  const seats = [
    { ...seatAngle(Math.PI), label: "", active: false, player: "" },
    { ...seatAngle(3 * Math.PI / 4), label: match.agent_a, active: true, player: "A" },
    { ...seatAngle(Math.PI / 2), label: "", active: false, player: "" },
    { ...seatAngle(Math.PI / 4), label: match.agent_b, active: true, player: "B" },
    { ...seatAngle(0), label: "", active: false, player: "" },
  ];

  const seatA = seats[1];
  const seatB = seats[3];

  const dealerX = TCX;
  const dealerY = TCY + 140;

  const holeY = TCY - 80;
  const chipY = TCY - 80;
  const chipColor = { A: "var(--color-agent-a)", B: "var(--color-agent-b)" };

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      {/* hand slider */}
      {totalHands > 0 && (
        <div className="shrink-0 flex items-center gap-3 px-4 py-2 border-b border-line/40 bg-surface/80">
          <button
            className="w-6 h-6 rounded-full bg-surface-container border border-line/40 flex items-center justify-center text-[10px] font-bold text-muted hover:text-ink hover:border-line-strong transition-colors shrink-0"
            onClick={() => {
              const next = (viewIdx ?? state.activeRoundIndex) - 1;
              if (next >= 0) { setViewIdx(next); showRound(next); }
            }}
          >
            &#9664;
          </button>
          <input
            type="range"
            className="flex-1 h-1 accent-accent cursor-pointer"
            min={0}
            max={totalHands - 1}
            value={viewIdx ?? state.activeRoundIndex}
            onChange={(e) => {
              const v = Number(e.target.value);
              setViewIdx(v);
              showRound(v);
            }}
          />
          <button
            className="w-6 h-6 rounded-full bg-surface-container border border-line/40 flex items-center justify-center text-[10px] font-bold text-muted hover:text-ink hover:border-line-strong transition-colors shrink-0"
            onClick={() => {
              const next = (viewIdx ?? state.activeRoundIndex) + 1;
              if (next < totalHands) { setViewIdx(next); showRound(next); }
            }}
          >
            &#9654;
          </button>
          <span className="text-[10px] font-semibold text-muted shrink-0 tabular-nums">
            {isReplaying ? (
              <button className="hover:text-accent transition-colors" onClick={() => { setViewIdx(null); showRound(totalHands - 1); }}>live</button>
            ) : (
              `${(viewIdx ?? state.activeRoundIndex) + 1}/${totalHands}`
            )}
          </span>
          {street && (
            <span className="text-[10px] font-bold text-accent uppercase tracking-wider shrink-0">
              {STREET[street] || street}
            </span>
          )}
          {isActive && currentPlayer && (
            <span className="text-[10px] text-muted truncate">
              {currentPlayer === "A" ? match.agent_a : match.agent_b}&apos;s turn
            </span>
          )}
          {matchComplete && (
            <span className="text-[10px] font-bold text-muted shrink-0">
              {match.match_winner === "Tie"
                ? "Draw"
                : `${match.match_winner === "A" ? match.agent_a : match.agent_b} wins`}
            </span>
          )}
        </div>
      )}

      {/* SVG table */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <svg viewBox="0 0 800 500" className="w-full h-full" preserveAspectRatio="xMidYMid meet">
          {/* drop shadow */}
          <ellipse cx={TCX} cy={TCY + 10} rx={ORX + 6} ry={ORY + 6} fill="rgba(0,0,0,0.12)" />

          {/* wood edge */}
          <ellipse cx={TCX} cy={TCY} rx={ORX} ry={ORY} fill="#8B6914" />
          <ellipse cx={TCX} cy={TCY} rx={ORX - 2} ry={ORY - 2} fill="#9B7924" />
          <ellipse cx={TCX} cy={TCY} rx={ORX - 5} ry={ORY - 5} fill="#8B6914" stroke="#6B4F12" strokeWidth={1} />
          <ellipse cx={TCX} cy={TCY} rx={ORX - 8} ry={ORY - 8} fill="#9B7924" />

          {/* green felt */}
          <ellipse cx={TCX} cy={TCY} rx={IRX} ry={IRY} fill="#1a7a3a" />
          <ellipse cx={TCX} cy={TCY} rx={IRX - 2} ry={IRY - 2} fill="#1e8449" />
          <ellipse cx={TCX} cy={TCY} rx={IRX - 4} ry={IRY - 4} fill="#229954" />

          {/* chairs */}
          {seats.map((s) =>
            s.active ? (
              <Chair key={s.player} cx={s.x} cy={s.y} label={s.label} />
            ) : (
              <EmptySeat key={`e${s.x}`} cx={s.x} cy={s.y} />
            ),
          )}

          {/* dealer */}
          <g>
            <circle cx={dealerX} cy={dealerY} r={22} fill="var(--color-agent-b)" opacity={0.2} stroke="var(--color-agent-b)" strokeWidth={2} />
            <circle cx={dealerX} cy={dealerY} r={17} fill="var(--color-agent-b)" opacity={0.3} />
            <text
              x={dealerX}
              y={dealerY + 5}
              fontSize={10}
              fontWeight="bold"
              fill="var(--color-ink)"
              textAnchor="middle"
              fontFamily="ui-monospace,monospace"
            >
              DEALER
            </text>
          </g>

          {/* player A hole cards + chips */}
          {holeA.length > 0 && (
            <g>
              {holeA.map((card, i) => (
                <CardView key={`a${i}`} card={card} cx={seatA.x + (i - 0.5) * 40} cy={holeY} />
              ))}
              <ChipStack amt={chipsA} cx={seatA.x + 58} cy={holeY} colorVar={chipColor.A} />
              {isActive && currentPlayer === "A" && (
                <circle cx={seatA.x} cy={holeY - 30} r={4} fill="var(--color-agent-a)">
                  <animate attributeName="opacity" values="0.3;1;0.3" dur="1.5s" repeatCount="indefinite" />
                </circle>
              )}
            </g>
          )}

          {/* player B hole cards + chips */}
          {holeB.length > 0 && (
            <g>
              {holeB.map((card, i) => (
                <CardView key={`b${i}`} card={card} cx={seatB.x + (i - 0.5) * 40} cy={holeY} />
              ))}
              <ChipStack amt={chipsB} cx={seatB.x - 58} cy={holeY} colorVar={chipColor.B} />
              {isActive && currentPlayer === "B" && (
                <circle cx={seatB.x} cy={holeY - 30} r={4} fill="var(--color-agent-b)">
                  <animate attributeName="opacity" values="0.3;1;0.3" dur="1.5s" repeatCount="indefinite" />
                </circle>
              )}
            </g>
          )}

          {/* community cards */}
          <CommunityCards cards={community} cx={TCX} cy={TCY} />

          {/* pot & deck */}
          <Pot amt={pot} cx={TCX} cy={TCY + 55} />
          <Deck cx={TCX - 120} cy={TCY} />
        </svg>
      </div>
    </div>
  );
}
