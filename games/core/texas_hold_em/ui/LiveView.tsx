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
  const w = 18;
  const h = 26;
  const r = 2;
  const x = p.cx - w / 2;
  const y = p.cy - h / 2;

  if (p.faceDown || !parsed) {
    return (
      <g>
        <rect x={x} y={y} width={w} height={h} rx={r} fill="#1a365d" stroke="#2a4a7a" strokeWidth={1} />
        <rect x={x + 2} y={y + 2} width={w - 4} height={h - 4} rx={1.5} fill="none" stroke="#3182ce" strokeWidth={0.8} opacity={0.35} />
        <line x1={x + 3} y1={y + 3} x2={x + w - 3} y2={y + h - 3} stroke="#3182ce" strokeWidth={0.5} opacity={0.2} />
        <line x1={x + w - 3} y1={y + 3} x2={x + 3} y2={y + h - 3} stroke="#3182ce" strokeWidth={0.5} opacity={0.2} />
      </g>
    );
  }

  const { sym, ink } = SUIT[parsed.suit];

  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={r} fill="#fff" stroke="#cbd5e0" strokeWidth={0.8} />
      <text x={x + 2} y={y + 8} fontSize={7} fontWeight="bold" fill={ink} fontFamily="ui-monospace,monospace">
        {parsed.rank}
      </text>
      <text x={p.cx} y={p.cy + 5} fontSize={10} fill={ink} textAnchor="middle" dominantBaseline="middle" fontFamily="serif">
        {sym}
      </text>
    </g>
  );
}

/* ---------- chip stack ---------- */

function ChipStack(p: { amt: number; cx: number; cy: number; colorVar: string }) {
  return (
    <g>
      <circle cx={p.cx} cy={p.cy + 2} r={4} fill={p.colorVar} opacity={0.25} />
      <circle cx={p.cx} cy={p.cy + 1} r={4} fill={p.colorVar} opacity={0.45} />
      <circle cx={p.cx} cy={p.cy} r={4} fill={p.colorVar} opacity={0.75} stroke={p.colorVar} strokeWidth={0.6} />
      <text
        x={p.cx}
        y={p.cy - 7}
        fontSize={7}
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
      <circle cx={p.cx} cy={p.cy} r={12} fill="none" stroke="var(--color-gold)" strokeWidth={1.5} />
      <circle cx={p.cx} cy={p.cy} r={9} fill="#e53e3e" />
      <circle cx={p.cx} cy={p.cy} r={6} fill="none" stroke="var(--color-gold)" strokeWidth={0.6} opacity={0.4} />
      <text
        x={p.cx}
        y={p.cy - 18}
        fontSize={7}
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
      <circle cx={p.cx} cy={p.cy} r={10} fill="none" stroke="var(--color-line)" strokeWidth={1} />
      <circle cx={p.cx} cy={p.cy} r={7} fill="var(--color-surface-container)" opacity={0.3} />
    </g>
  );
}

/* ---------- community cards ---------- */

function CommunityCards(p: { cards: string[]; cx: number; cy: number }) {
  const cw = 18;
  const ch = 26;
  const gap = 3;
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
              rx={2}
              fill="rgba(0,0,0,0.25)"
              stroke="rgba(255,255,255,0.5)"
              strokeWidth={1}
              strokeDasharray="3 2"
            />
          </g>
        );
      })}
    </g>
  );
}

/* ---------- deck & pot ---------- */

function Deck(p: { cx: number; cy: number }) {
  const w = 18;
  const h = 26;
  return (
    <g>
      <rect x={p.cx - w / 2 - 2} y={p.cy - h / 2 - 2} width={w} height={h} rx={2} fill="#1a365d" stroke="#2a4a7a" strokeWidth={1} />
      <rect x={p.cx - w / 2 - 1} y={p.cy - h / 2 - 1} width={w} height={h} rx={2} fill="#1a365d" stroke="#2a4a7a" strokeWidth={1} />
      <rect x={p.cx - w / 2} y={p.cy - h / 2} width={w} height={h} rx={2} fill="#1a365d" stroke="#2a4a7a" strokeWidth={1} />
      <rect x={p.cx - w / 2 + 2} y={p.cy - h / 2 + 2} width={w - 4} height={h - 4} rx={1.5} fill="none" stroke="#3182ce" strokeWidth={0.8} opacity={0.35} />
      <line x1={p.cx - w / 2 + 2} y1={p.cy - h / 2 + 2} x2={p.cx + w / 2 - 2} y2={p.cy + h / 2 - 2} stroke="#3182ce" strokeWidth={0.5} opacity={0.2} />
      <line x1={p.cx + w / 2 - 2} y1={p.cy - h / 2 + 2} x2={p.cx - w / 2 + 2} y2={p.cy + h / 2 - 2} stroke="#3182ce" strokeWidth={0.5} opacity={0.2} />
    </g>
  );
}

function Pot(p: { amt: number; cx: number; cy: number }) {
  return (
    <g>
      <circle cx={p.cx - 16} cy={p.cy} r={6} fill="var(--color-gold)" opacity={0.15} stroke="var(--color-gold)" strokeWidth={1} />
      <circle cx={p.cx - 16} cy={p.cy} r={3} fill="var(--color-gold)" opacity={0.3} />
      <text
        x={p.cx - 7}
        y={p.cy + 2}
        fontSize={8}
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

  const TCX = 300;
  const TCY = 140;
  const ORX = 230;
  const ORY = 90;
  const IRX = 215;
  const IRY = 80;
  const SRX = 220;
  const SRY = 90;

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
  const dealerY = TCY + 78;

  const holeY = TCY - 45;
  const chipColor = { A: "var(--color-agent-a)", B: "var(--color-agent-b)" };

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      {/* hand slider */}
      {totalHands > 0 && (
        <div className="shrink-0 flex items-center gap-1.5 px-2 py-1 border-b border-line/40 bg-surface/80">
          <button
            className="w-4 h-4 rounded-full bg-surface-container border border-line/40 flex items-center justify-center text-[8px] font-bold text-muted hover:text-ink hover:border-line-strong transition-colors shrink-0"
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
            className="w-4 h-4 rounded-full bg-surface-container border border-line/40 flex items-center justify-center text-[8px] font-bold text-muted hover:text-ink hover:border-line-strong transition-colors shrink-0"
            onClick={() => {
              const next = (viewIdx ?? state.activeRoundIndex) + 1;
              if (next < totalHands) { setViewIdx(next); showRound(next); }
            }}
          >
            &#9654;
          </button>
          <span className="text-[8px] font-semibold text-muted shrink-0 tabular-nums">
            {isReplaying ? (
              <button className="hover:text-accent transition-colors" onClick={() => { setViewIdx(null); showRound(totalHands - 1); }}>live</button>
            ) : (
              `${(viewIdx ?? state.activeRoundIndex) + 1}/${totalHands}`
            )}
          </span>
          {street && (
            <span className="text-[8px] font-bold text-accent uppercase tracking-wider shrink-0">
              {STREET[street] || street}
            </span>
          )}
          {isActive && currentPlayer && (
            <span className="text-[8px] text-muted truncate">
              {currentPlayer === "A" ? match.agent_a : match.agent_b}&apos;s turn
            </span>
          )}
          {matchComplete && (
            <span className="text-[8px] font-bold text-muted shrink-0">
              {match.match_winner === "Tie"
                ? "Draw"
                : `${match.match_winner === "A" ? match.agent_a : match.agent_b} wins`}
            </span>
          )}
        </div>
      )}

      {/* SVG table */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <svg viewBox="0 0 600 280" className="w-full h-full" preserveAspectRatio="xMidYMid meet">
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
            <circle cx={dealerX} cy={dealerY} r={16} fill="var(--color-agent-b)" opacity={0.2} stroke="var(--color-agent-b)" strokeWidth={1.5} />
            <circle cx={dealerX} cy={dealerY} r={12} fill="var(--color-agent-b)" opacity={0.3} />
            <text
              x={dealerX}
              y={dealerY + 3}
              fontSize={8}
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
                <CardView key={`a${i}`} card={card} cx={seatA.x + (i - 0.5) * 22} cy={holeY} />
              ))}
              <ChipStack amt={chipsA} cx={seatA.x + 34} cy={holeY} colorVar={chipColor.A} />
              {isActive && currentPlayer === "A" && (
                <circle cx={seatA.x} cy={holeY - 16} r={2.5} fill="var(--color-agent-a)">
                  <animate attributeName="opacity" values="0.3;1;0.3" dur="1.5s" repeatCount="indefinite" />
                </circle>
              )}
            </g>
          )}

          {/* player B hole cards + chips */}
          {holeB.length > 0 && (
            <g>
              {holeB.map((card, i) => (
                <CardView key={`b${i}`} card={card} cx={seatB.x + (i - 0.5) * 22} cy={holeY} />
              ))}
              <ChipStack amt={chipsB} cx={seatB.x - 34} cy={holeY} colorVar={chipColor.B} />
              {isActive && currentPlayer === "B" && (
                <circle cx={seatB.x} cy={holeY - 16} r={2.5} fill="var(--color-agent-b)">
                  <animate attributeName="opacity" values="0.3;1;0.3" dur="1.5s" repeatCount="indefinite" />
                </circle>
              )}
            </g>
          )}

          {/* community cards */}
          <CommunityCards cards={community} cx={TCX} cy={TCY} />

          {/* pot & deck */}
          <Pot amt={pot} cx={TCX} cy={TCY + 32} />
          <Deck cx={TCX - 80} cy={TCY} />
        </svg>
      </div>

      {/* action log + hand result */}
      <div className="shrink-0 border-t border-line/40 bg-surface/90 backdrop-blur-sm">
        <div className="max-h-20 overflow-y-auto px-3 py-1.5 space-y-0.5 text-[9px] font-mono">
          {/* street actions grouped by street */}
          {(() => {
            const allActions = arr(data.street_actions) as Array<{ player: string; action: string; street?: string }>;
            if (!allActions.length) {
              return <div className="text-quiet italic">No actions yet</div>;
            }
            const grouped: Record<string, typeof allActions> = {};
            for (const a of allActions) {
              const s = a.street ?? "preflop";
              if (!grouped[s]) grouped[s] = [];
              grouped[s].push(a);
            }
            const streetOrder = ["preflop", "flop", "turn", "river"];
            return streetOrder.flatMap((s) => {
              const acts = grouped[s];
              if (!acts) return [];
              return [
                <div key={`h-${s}`} className="flex items-center gap-1.5 text-quiet text-[8px] uppercase tracking-wider pt-0 first:pt-0">
                  <span className="w-2 h-px bg-line/40" />
                  {s === "preflop" ? "Preflop" : s.charAt(0).toUpperCase() + s.slice(1)}
                  <span className="flex-1 h-px bg-line/40" />
                </div>,
                ...acts.map((a, i) => {
                  const pLabel = a.player === "A" ? match.agent_a : match.agent_b;
                  const pColor = a.player === "A" ? "var(--color-agent-a)" : "var(--color-agent-b)";
                  const actionLabel = a.action === "fold" ? "folded" : a.action;
                  return (
                    <div key={`a-${s}-${i}`} className="flex items-center gap-1 pl-1.5">
                      <span className="w-0.5 h-0.5 rounded-full shrink-0" style={{ backgroundColor: pColor }} />
                      <span className="font-semibold text-ink text-[9px]" style={{ color: pColor }}>{pLabel}</span>
                      <span className="text-muted lowercase">{actionLabel}</span>
                    </div>
                  );
                }),
              ];
            });
          })()}

          {/* hand result */}
          {(() => {
            const result = obj(data.result) as Record<string, unknown> | null;
            if (!result || !result.outcome) return null;
            const winner = str(result.winner);
            const potAmt = num(data.pot || data.final_hand_pot);
            const potStr = potAmt ? `$${potAmt}` : "";
            const isTie = winner === "Tie" || winner === "";
            const wLabel = isTie ? "Draw" : (winner === "A" ? match.agent_a : match.agent_b);
            const wColor = isTie ? "var(--color-gold)" : (winner === "A" ? "var(--color-agent-a)" : "var(--color-agent-b)");
            let detail = "";
            if (result.outcome === "fold") {
              const loser = str(result.winner) === "A" ? match.agent_b : match.agent_a;
              detail = `${loser} folded`;
            } else if (result.outcome === "showdown") {
              const handR = result.hand as Record<string, unknown> | undefined;
              const handName = handR ? str(handR.hand).replace(/_/g, " ") : "";
              if (handName) detail = handName;
              if (isTie) detail = "Tie";
            }
            return (
              <div className="flex items-center gap-1 pt-0.5 border-t border-line/30 mt-0.5 text-[10px]">
                <span className="font-bold" style={{ color: wColor }}>{wLabel}</span>
                {potStr && <span className="text-gold font-semibold">wins {potStr}</span>}
                {detail && <span className="text-quiet">· {detail}</span>}
              </div>
            );
          })()}
        </div>

        {/* past hands mini summary */}
        {match.history.length > 0 && (
          <div className="border-t border-line/30 px-3 py-1 flex items-center gap-1.5 overflow-x-auto text-[8px] font-mono">
            <span className="text-quiet uppercase tracking-wider shrink-0">History</span>
            {match.history.map((h, i) => {
              const rawH = obj(h.raw) as Record<string, unknown>;
              const res = obj(rawH.result) as Record<string, unknown> | null;
              const w = str(res?.winner ?? "");
              const isTie = w === "Tie" || w === "";
              const color = isTie ? "var(--color-gold)" : (w === "A" ? "var(--color-agent-a)" : "var(--color-agent-b)");
              const label = isTie ? "=" : (w === "A" ? match.agent_a : match.agent_b);
              const isActive = i === (viewIdx ?? state.activeRoundIndex);
              return (
                <button
                  key={i}
                  onClick={() => { setViewIdx(i); showRound(i); }}
                  className={`shrink-0 flex items-center gap-0.5 px-1 py-0.5 rounded border transition-colors ${
                    isActive ? "border-accent/50 bg-accent/8" : "border-transparent hover:border-line/40"
                  }`}
                >
                  <span className="text-quiet">#{i + 1}</span>
                  <span className="font-semibold" style={{ color }}>{label}</span>
                  <span className="text-quiet">${num(rawH.pot || rawH.final_hand_pot)}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
