import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { useApp } from "@frontend/hooks/useApp";

interface ActionEntry {
  player: string;
  action: string;
  street: string;
  amount?: number;
  bet?: number;
}

interface CardData {
  rank: string;
  suit: string;
}

const SUITS: Record<string, { sym: string; ink: string; pip: string }> = {
  h: { sym: "\u2665", ink: "#dc2626", pip: "HEARTS" },
  d: { sym: "\u2666", ink: "#dc2626", pip: "DIAMONDS" },
  c: { sym: "\u2663", ink: "#111827", pip: "CLUBS" },
  s: { sym: "\u2660", ink: "#111827", pip: "SPADES" },
};

const STREET_LABEL: Record<string, string> = {
  preflop: "Pre-Flop",
  flop: "Flop",
  turn: "Turn",
  river: "River",
};

const STREET_ORDER = ["preflop", "flop", "turn", "river"] as const;
const RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"];

const tableRootStyle: CSSProperties = {
  background: "#050806",
  color: "#ffffff",
};

const headerStyle: CSSProperties = {
  background: "rgba(8,9,8,.97)",
  borderBottom: "1px solid rgba(253,230,138,.14)",
  boxShadow: "0 10px 24px rgba(0,0,0,.28)",
};

const arenaStyle: CSSProperties = {
  background:
    "radial-gradient(circle at 50% 46%, rgba(31,122,82,.32), transparent 34%), radial-gradient(circle at 15% 10%, rgba(255,224,130,.12), transparent 24%), linear-gradient(135deg,#050806,#151109 45%,#050806)",
};

const railStyle: CSSProperties = {
  background: "linear-gradient(135deg,#9a5b24 0%,#4c2814 48%,#170c07 100%)",
  boxShadow: "0 34px 90px rgba(0,0,0,.68), inset 0 3px 8px rgba(255,255,255,.25)",
};

const feltStyle: CSSProperties = {
  background: "linear-gradient(135deg,#16865f 0%,#07543c 50%,#042a22 100%)",
  border: "1px solid rgba(167,243,208,.24)",
  boxShadow: "inset 0 0 58px rgba(0,0,0,.66), inset 0 0 0 8px rgba(255,255,255,.035)",
};

const footerRailStyle: CSSProperties = {
  background: "rgba(7,8,6,.98)",
  borderTop: "1px solid rgba(253,230,138,.14)",
};

function parseCard(c: string): CardData | null {
  if (c.length < 2) return null;
  const rank = c.slice(0, -1).replace("T", "10");
  const suit = c.slice(-1);
  if (!RANKS.includes(rank)) return null;
  return { rank, suit };
}

function agentInitial(name: string): string {
  return (name.trim().charAt(0) || "?").toUpperCase();
}

function fmtChips(n: number): string {
  if (!Number.isFinite(n)) return "0";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 10000) return `${(n / 1000).toFixed(0)}K`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(Math.round(n * 10) / 10);
}

function actionAmount(action: ActionEntry): number | undefined {
  return action.amount ?? action.bet;
}

function resultLine(result: Record<string, unknown>): string {
  const outcome = result.outcome as string | undefined;
  const winner = result.winner as string | undefined;
  if (outcome === "showdown") return winner === "Tie" ? "Split pot" : `${winner} wins at showdown`;
  if (outcome === "fold") return `${winner} wins by fold`;
  return outcome ?? "";
}

function useDealAnimationKey(cards: string[]): string {
  return cards.join("-");
}

function FeltTexture() {
  return (
    <div
      className="absolute inset-0 pointer-events-none opacity-70"
      style={{
        backgroundImage: [
          "radial-gradient(ellipse at center, rgba(255,255,255,0.12), transparent 38%)",
          "repeating-linear-gradient(0deg, rgba(255,255,255,0.035) 0 1px, transparent 1px 4px)",
          "repeating-linear-gradient(90deg, rgba(0,0,0,0.04) 0 1px, transparent 1px 5px)",
        ].join(", "),
      }}
    />
  );
}

function PokerStyles() {
  return (
    <style>
      {`
        @keyframes texas-card-enter {
          0% { opacity: 0; transform: translate3d(0,-28px,0) rotate(-5deg) scale(.88); }
          65% { opacity: 1; transform: translate3d(0,3px,0) rotate(1deg) scale(1.02); }
          100% { opacity: 1; transform: translate3d(0,0,0) rotate(0) scale(1); }
        }
        @keyframes texas-card-flip {
          0% { transform: rotateY(86deg) translateY(-8px); opacity: .15; }
          100% { transform: rotateY(0deg) translateY(0); opacity: 1; }
        }
        @keyframes texas-button-pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(250,204,21,.35), 0 8px 18px rgba(0,0,0,.35); }
          50% { box-shadow: 0 0 0 8px rgba(250,204,21,0), 0 8px 18px rgba(0,0,0,.35); }
        }
        @keyframes texas-chip-pop {
          0% { opacity: 0; transform: translateY(12px) scale(.86); }
          100% { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes texas-light-sweep {
          0% { transform: translateX(-120%) skewX(-18deg); opacity: 0; }
          30% { opacity: .55; }
          100% { transform: translateX(120%) skewX(-18deg); opacity: 0; }
        }
        .texas-session {
          position: relative;
          width: min(94vw, 1120px);
          height: min(64vh, 620px);
          min-height: 500px;
          margin: 0 auto;
        }
        .texas-table {
          position: absolute;
          inset: 124px 22px 124px;
          border-radius: 999px;
          padding: 14px;
          background: linear-gradient(135deg,#9a5b24 0%,#552b13 46%,#170b05 100%);
          box-shadow: 0 36px 90px rgba(0,0,0,.72), inset 0 4px 10px rgba(255,255,255,.24), inset 0 -10px 22px rgba(0,0,0,.28);
        }
        .texas-felt {
          position: relative;
          height: 100%;
          border-radius: 999px;
          overflow: hidden;
          background:
            radial-gradient(ellipse at 50% 48%, rgba(45,191,132,.32), transparent 42%),
            linear-gradient(135deg,#16865f 0%,#096343 48%,#043225 100%);
          border: 1px solid rgba(167,243,208,.28);
          box-shadow: inset 0 0 58px rgba(0,0,0,.66), inset 0 0 0 10px rgba(255,255,255,.035);
        }
        .texas-felt::before {
          content: "";
          position: absolute;
          inset: 20px 42px;
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,.12);
          box-shadow: inset 0 0 24px rgba(0,0,0,.2);
        }
        .texas-felt::after {
          content: "NASH HOLD'EM";
          position: absolute;
          left: 50%;
          top: 52%;
          transform: translate(-50%,-50%);
          font-size: clamp(22px,4vw,48px);
          font-weight: 900;
          letter-spacing: .18em;
          color: rgba(255,255,255,.055);
          white-space: nowrap;
        }
        .texas-seat {
          position: absolute;
          z-index: 35;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          width: min(92vw, 500px);
        }
        .texas-seat-top {
          left: 50%;
          top: 0;
          transform: translateX(-50%);
        }
        .texas-seat-bottom {
          left: 50%;
          bottom: 18px;
          transform: translateX(-50%);
        }
        .texas-nameplate {
          width: min(100%, 280px);
          display: grid;
          grid-template-columns: 44px minmax(0,1fr) auto;
          align-items: center;
          gap: 10px;
          padding: 9px 11px;
          border-radius: 10px;
          background: linear-gradient(180deg,rgba(20,20,18,.92),rgba(7,7,6,.94));
          border: 1px solid rgba(255,255,255,.18);
          box-shadow: 0 16px 34px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.08);
        }
        .texas-nameplate-active {
          border-color: rgba(252,211,77,.9);
          box-shadow: 0 0 0 1px rgba(252,211,77,.22), 0 0 26px rgba(252,211,77,.16), 0 16px 34px rgba(0,0,0,.42);
        }
        .texas-avatar {
          width: 44px;
          height: 44px;
          display: grid;
          place-items: center;
          border-radius: 50%;
          color: white;
          font-size: 15px;
          font-weight: 900;
          box-shadow: inset 0 0 0 2px rgba(255,255,255,.18), 0 8px 18px rgba(0,0,0,.36);
        }
        .texas-hole-cards {
          display: flex;
          gap: 8px;
          align-items: center;
          justify-content: center;
          min-height: 96px;
          flex-shrink: 0;
        }
        .texas-board-zone {
          position: absolute;
          z-index: 25;
          left: 50%;
          top: 50%;
          transform: translate(-50%,-50%);
          display: grid;
          justify-items: center;
          gap: 10px;
        }
        .texas-board {
          display: flex;
          gap: clamp(7px,1vw,12px);
          align-items: center;
          justify-content: center;
          padding: 10px 12px 26px;
          border-radius: 16px;
          background: rgba(2,20,14,.22);
          border: 1px solid rgba(255,255,255,.08);
          box-shadow: inset 0 0 24px rgba(0,0,0,.22);
        }
        .texas-pot {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 8px 16px;
          border-radius: 999px;
          background: rgba(5,8,6,.82);
          border: 1px solid rgba(253,230,138,.28);
          box-shadow: 0 16px 34px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.08);
        }
        .texas-bet {
          position: absolute;
          z-index: 28;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 10px;
          border-radius: 999px;
          background: rgba(0,0,0,.48);
          border: 1px solid rgba(253,230,138,.25);
          box-shadow: 0 10px 22px rgba(0,0,0,.35);
        }
        .texas-bet-top {
          left: 50%;
          top: 25%;
          transform: translateX(-50%);
        }
        .texas-bet-bottom {
          left: 50%;
          bottom: 25%;
          transform: translateX(-50%);
        }
        @media (max-width: 760px) {
          .texas-session {
            width: 100%;
            height: 620px;
            min-height: 620px;
          }
          .texas-table {
            inset: 142px 4px 142px;
            padding: 9px;
          }
          .texas-seat {
            width: min(96vw, 500px);
            gap: 7px;
          }
          .texas-seat-top {
            top: 0;
          }
          .texas-seat-bottom {
            bottom: 12px;
          }
          .texas-board {
            gap: 5px;
            padding-left: 6px;
            padding-right: 6px;
          }
        }
      `}
    </style>
  );
}

function ChipIcon({ dim = 16 }: { dim?: number }) {
  return (
    <svg width={dim} height={dim} viewBox="0 0 24 24" fill="none" className="shrink-0 drop-shadow">
      <circle cx="12" cy="12" r="10" fill="#f5c542" stroke="#7c4a03" strokeWidth="1.4" />
      <path d="M12 2v5M12 17v5M2 12h5M17 12h5M4.9 4.9l3.6 3.6M15.5 15.5l3.6 3.6M19.1 4.9l-3.6 3.6M8.5 15.5l-3.6 3.6" stroke="#fff7c2" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="12" cy="12" r="5.4" fill="#b45309" stroke="#fff7c2" strokeWidth="1" />
      <circle cx="12" cy="12" r="2.2" fill="#fff7c2" />
    </svg>
  );
}

function ChipStack({ value, compact = false }: { value: number; compact?: boolean }) {
  const chips = compact ? 3 : 5;
  return (
    <div className="flex items-center gap-2">
      <div className={`relative ${compact ? "w-8 h-7" : "w-11 h-9"}`} aria-hidden="true">
        {Array.from({ length: chips }).map((_, i) => (
          <span
            key={i}
            className="absolute left-0 rounded-full border border-yellow-100/70 bg-gradient-to-br from-yellow-300 via-amber-500 to-orange-700 shadow-[0_2px_4px_rgba(0,0,0,.4)]"
            style={{
              width: compact ? 24 : 34,
              height: compact ? 9 : 11,
              bottom: i * (compact ? 5 : 6),
              left: i % 2,
              animation: `texas-chip-pop .24s ease-out ${i * 45}ms both`,
            }}
          />
        ))}
      </div>
      <span className={`${compact ? "text-[11px]" : "text-sm"} font-black text-amber-100 tabular-nums drop-shadow`}>
        {fmtChips(value)}
      </span>
    </div>
  );
}

function pipPositions(rank: string): Array<[number, number, boolean?]> {
  const top: [number, number] = [50, 24];
  const upperLeft: [number, number] = [35, 31];
  const upperRight: [number, number] = [65, 31];
  const midLeft: [number, number] = [35, 50];
  const midRight: [number, number] = [65, 50];
  const lowerLeft: [number, number] = [35, 69];
  const lowerRight: [number, number] = [65, 69];
  const bottom: [number, number] = [50, 76];
  const center: [number, number] = [50, 50];
  const mirror = (items: Array<[number, number]>): Array<[number, number, boolean?]> =>
    items.map(([x, y]) => [x, y, y > 50]);

  switch (rank) {
    case "A":
      return [[50, 50]];
    case "2":
      return mirror([top, bottom]);
    case "3":
      return mirror([top, center, bottom]);
    case "4":
      return mirror([upperLeft, upperRight, lowerLeft, lowerRight]);
    case "5":
      return mirror([upperLeft, upperRight, center, lowerLeft, lowerRight]);
    case "6":
      return mirror([upperLeft, upperRight, midLeft, midRight, lowerLeft, lowerRight]);
    case "7":
      return mirror([upperLeft, upperRight, top, midLeft, midRight, lowerLeft, lowerRight]);
    case "8":
      return mirror([upperLeft, upperRight, top, midLeft, midRight, bottom, lowerLeft, lowerRight]);
    case "9":
      return mirror([upperLeft, upperRight, top, midLeft, midRight, center, bottom, lowerLeft, lowerRight]);
    case "10":
      return mirror([upperLeft, upperRight, top, midLeft, midRight, [35, 40], [65, 40], bottom, lowerLeft, lowerRight]);
    default:
      return [[50, 50]];
  }
}

function PipPattern({ rank, suit, board }: { rank: string; suit: { sym: string; ink: string }; board: boolean }) {
  const positions = pipPositions(rank);
  const size = rank === "A" ? (board ? 36 : 32) : board ? 18 : 16;
  return (
    <div className="absolute inset-[15%_16%]">
      {positions.map(([x, y, rotated], i) => (
        <span
          key={`${rank}-${i}`}
          className="absolute leading-none"
          style={{
            left: `${x}%`,
            top: `${y}%`,
            color: suit.ink,
            fontSize: size,
            fontFamily: "Georgia, Times New Roman, serif",
            transform: `translate(-50%, -50%)${rotated ? " rotate(180deg)" : ""}`,
          }}
        >
          {suit.sym}
        </span>
      ))}
    </div>
  );
}

function CourtArtwork({ rank, suit, board }: { rank: string; suit: { sym: string; ink: string }; board: boolean }) {
  const accent = suit.ink === "#dc2626" ? "#dc2626" : "#1f2937";
  const gold = "#d6a737";
  const robe = rank === "K" ? gold : rank === "Q" ? "#2563eb" : "#7c3aed";
  const label = rank === "K" ? "KING" : rank === "Q" ? "QUEEN" : "JACK";
  const scale = board ? 1 : 0.94;

  return (
    <svg
      className="absolute"
      viewBox="0 0 100 140"
      aria-hidden="true"
      style={{
        left: "17%",
        top: "15%",
        width: "66%",
        height: "70%",
        transform: `scale(${scale})`,
      }}
    >
      <rect x="7" y="7" width="86" height="126" rx="8" fill="#fffdf5" stroke="#d8cfae" strokeWidth="1.5" />
      <path d="M18 68 C26 36 74 36 82 68 C75 96 25 96 18 68Z" fill={robe} stroke="#24170d" strokeWidth="1.2" />
      <circle cx="50" cy="45" r="15" fill="#f3d6ad" stroke="#422006" strokeWidth="1.2" />
      <path d="M34 36 L41 23 L50 34 L59 23 L66 36 Z" fill={gold} stroke="#7c4a03" strokeWidth="1.2" />
      <path d="M39 44 Q50 55 61 44" fill="none" stroke="#422006" strokeWidth="1.3" strokeLinecap="round" />
      <circle cx="44" cy="43" r="1.8" fill="#422006" />
      <circle cx="56" cy="43" r="1.8" fill="#422006" />
      <path d="M31 69 L50 55 L69 69 L62 103 L38 103 Z" fill={rank === "Q" ? "#f8fafc" : "#fef3c7"} stroke="#422006" strokeWidth="1.2" />
      <text x="50" y="84" textAnchor="middle" fontSize="18" fontWeight="900" fill={suit.ink} fontFamily="Georgia, Times New Roman, serif">{suit.sym}</text>
      <path d="M26 107 H74" stroke="#422006" strokeWidth="1.2" />
      <text x="50" y="121" textAnchor="middle" fontSize="9" fontWeight="900" fill="#422006" fontFamily="Georgia, Times New Roman, serif">{label}</text>
      <g transform="rotate(180 50 70)" opacity=".96">
        <path d="M18 68 C26 36 74 36 82 68 C75 96 25 96 18 68Z" fill={robe} stroke="#24170d" strokeWidth="1.2" />
        <circle cx="50" cy="45" r="15" fill="#f3d6ad" stroke="#422006" strokeWidth="1.2" />
        <path d="M34 36 L41 23 L50 34 L59 23 L66 36 Z" fill={gold} stroke="#7c4a03" strokeWidth="1.2" />
        <text x="50" y="84" textAnchor="middle" fontSize="18" fontWeight="900" fill={suit.ink} fontFamily="Georgia, Times New Roman, serif">{suit.sym}</text>
      </g>
    </svg>
  );
}

function PlayingCard({
  card,
  delay = 0,
  faceDown = false,
  board = false,
  ghost = false,
}: {
  card: CardData | null;
  delay?: number;
  faceDown?: boolean;
  board?: boolean;
  ghost?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  const cardBoxStyle: CSSProperties = {
    width: board ? "clamp(54px, 7.4vw, 84px)" : "clamp(52px, 6.5vw, 72px)",
    height: board ? "clamp(76px, 10.5vw, 118px)" : "clamp(74px, 9.1vw, 102px)",
  };
  const cornerRankStyle: CSSProperties = {
    fontSize: board ? "clamp(14px, 1.75vw, 20px)" : "clamp(13px, 1.55vw, 18px)",
    fontFamily: "Georgia, Times New Roman, serif",
    letterSpacing: "-0.04em",
  };
  const cornerSuitStyle: CSSProperties = {
    fontSize: board ? "clamp(13px, 1.65vw, 19px)" : "clamp(12px, 1.5vw, 17px)",
    fontFamily: "Georgia, Times New Roman, serif",
  };

  useEffect(() => {
    setVisible(false);
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [card?.rank, card?.suit, delay, faceDown]);

  if (ghost) {
    return (
      <div className="rounded-[8px] border border-white/10 bg-black/14 shadow-[inset_0_0_18px_rgba(0,0,0,.35)]" style={cardBoxStyle} />
    );
  }

  if (faceDown || !card) {
    return (
      <div
        className="relative shrink-0 overflow-hidden rounded-[8px] border border-sky-100/30 bg-gradient-to-br from-blue-950 via-blue-700 to-sky-950 shadow-[0_12px_20px_rgba(0,0,0,.38)]"
        style={{
          ...cardBoxStyle,
          opacity: visible ? 1 : 0,
          background: "linear-gradient(135deg,#172554 0%,#1d4ed8 48%,#0c4a6e 100%)",
          animation: visible ? `texas-card-enter .46s cubic-bezier(.2,.9,.2,1) ${delay}ms both` : undefined,
        }}
      >
        <div className="absolute inset-[5px] rounded-[5px] border border-white/25" />
        <div className="absolute inset-[10px] rounded-[4px] border border-white/15 bg-[radial-gradient(circle_at_center,rgba(255,255,255,.16),transparent_58%)]" />
        <div className="absolute inset-0 opacity-45" style={{ backgroundImage: "repeating-linear-gradient(45deg, rgba(255,255,255,.2) 0 1px, transparent 1px 7px)" }} />
        <span className="absolute inset-0 flex items-center justify-center text-white/75 text-3xl font-black">♠</span>
      </div>
    );
  }

  const suit = SUITS[card.suit] ?? { sym: card.suit, ink: "#111827", pip: card.suit };
  const isCourt = card.rank === "J" || card.rank === "Q" || card.rank === "K";

  return (
    <div
      className="relative shrink-0 overflow-hidden border shadow-[0_13px_22px_rgba(0,0,0,.42),inset_0_0_0_1px_rgba(255,255,255,.9)] [transform-style:preserve-3d]"
      style={{
        ...cardBoxStyle,
        opacity: visible ? 1 : 0,
        borderRadius: board ? 11 : 10,
        borderColor: "#d7d7d7",
        background: "linear-gradient(180deg,#ffffff 0%,#fffdf7 52%,#f4f4f0 100%)",
        animation: visible ? `texas-card-enter .45s cubic-bezier(.2,.9,.2,1) ${delay}ms both` : undefined,
      }}
      title={`${card.rank} of ${suit.pip.toLowerCase()}`}
    >
      <span
        className="absolute left-[6px] top-[5px] z-10 flex flex-col items-center font-black leading-none"
        style={{ color: suit.ink }}
      >
        <span style={cornerRankStyle}>{card.rank}</span>
        <span style={cornerSuitStyle}>{suit.sym}</span>
      </span>
      <span
        className="absolute bottom-[5px] right-[6px] z-10 flex rotate-180 flex-col items-center font-black leading-none"
        style={{ color: suit.ink }}
      >
        <span style={cornerRankStyle}>{card.rank}</span>
        <span style={cornerSuitStyle}>{suit.sym}</span>
      </span>
      <div className="absolute inset-[6px] rounded-[8px] border" style={{ borderColor: "rgba(17,24,39,.08)" }} />
      {isCourt ? (
        <CourtArtwork rank={card.rank} suit={suit} board={board} />
      ) : (
        <PipPattern rank={card.rank} suit={suit} board={board} />
      )}
    </div>
  );
}

function ActionPill({ action, amount, player }: { action: string; amount?: number; player?: string }) {
  const tone: Record<string, string> = {
    fold: "bg-red-500/18 text-red-200 border-red-300/25",
    check: "bg-sky-400/16 text-sky-100 border-sky-200/25",
    call: "bg-emerald-400/18 text-emerald-100 border-emerald-200/25",
    raise: "bg-amber-400/20 text-amber-100 border-amber-200/30",
    bet: "bg-amber-400/20 text-amber-100 border-amber-200/30",
  };
  const label = action.toLowerCase();
  return (
    <span className={`inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[11px] font-black uppercase tracking-wide shadow-sm ${tone[label] ?? "bg-white/10 text-white/70 border-white/15"}`}>
      {player ? <span className="text-white/50">{player}</span> : null}
      <span>{label}</span>
      {amount != null ? <span className="tabular-nums text-white/70">{fmtChips(amount)}</span> : null}
    </span>
  );
}

function DealerButton({ className = "", style }: { className?: string; style?: CSSProperties }) {
  return (
    <span className={`absolute z-30 grid h-9 w-9 place-items-center rounded-full border border-yellow-200 bg-gradient-to-b from-white to-yellow-100 text-xs font-black text-neutral-950 shadow-[0_8px_18px_rgba(0,0,0,.35)] ${className}`} style={{ ...style, animation: "texas-button-pulse 2.1s ease-in-out infinite" }}>
      D
    </span>
  );
}

function PlayerSeat({
  side,
  name,
  cards,
  chips,
  active,
  dealer,
}: {
  side: "A" | "B";
  name: string;
  cards: CardData[];
  chips: number;
  active: boolean;
  dealer: boolean;
}) {
  const isBottom = side === "A";
  const avatarStyle: CSSProperties = {
    background: side === "A"
      ? "linear-gradient(135deg,#0891b2,#2563eb)"
      : "linear-gradient(135deg,#c026d3,#e11d48)",
  };
  const cardsNode = (
    <div className="texas-hole-cards">
      {cards.length > 0 ? cards.map((card, i) => <PlayingCard key={`${side}-${card.rank}${card.suit}-${i}`} card={card} delay={i * 120} />) : (
        <>
          <PlayingCard card={null} faceDown delay={0} />
          <PlayingCard card={null} faceDown delay={120} />
        </>
      )}
    </div>
  );
  const plateNode = (
    <div className={`texas-nameplate ${active ? "texas-nameplate-active" : ""}`}>
      <div className="texas-avatar" style={avatarStyle}>{agentInitial(name)}</div>
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-black text-white">{name}</span>
          <span className="rounded border border-white/10 bg-white/8 px-1.5 py-0.5 text-[9px] font-black text-white/55">{side}</span>
        </div>
        <div className="mt-1 flex items-center gap-2 text-[11px] font-bold text-amber-100">
          <ChipIcon dim={13} />
          <span className="tabular-nums">{fmtChips(chips)}</span>
        </div>
      </div>
      {dealer ? <span className="grid h-8 w-8 place-items-center rounded-full border border-yellow-200 bg-white text-[11px] font-black text-neutral-950 shadow-lg">D</span> : <span className="w-8" />}
      {active ? (
        <span className="absolute -right-1 -top-1 flex h-3 w-3">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-300 opacity-75" />
          <span className="relative inline-flex h-3 w-3 rounded-full bg-amber-300" />
        </span>
      ) : null}
    </div>
  );

  return (
    <div className={`texas-seat ${isBottom ? "texas-seat-bottom" : "texas-seat-top"}`}>
      {isBottom ? cardsNode : plateNode}
      {isBottom ? plateNode : cardsNode}
    </div>
  );
}

function BetMarker({ value, side }: { value: number; side: "A" | "B" }) {
  if (value <= 0) return null;
  return (
    <div className={`texas-bet ${side === "A" ? "texas-bet-bottom" : "texas-bet-top"}`}>
      <ChipStack value={value} compact />
    </div>
  );
}

function Board({
  cards,
  dealKey,
  street,
  pot,
  actions,
}: {
  cards: Array<CardData | null>;
  dealKey: string;
  street: string | null;
  pot: number | null;
  actions: ActionEntry[];
}) {
  const labels = ["Flop", "Flop", "Flop", "Turn", "River"];

  return (
    <div className="texas-board-zone">
      <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/24 px-4 py-1.5 text-[10px] font-black uppercase tracking-[0.32em] text-emerald-100/65 shadow-inner">
        <span>{STREET_LABEL[street ?? "preflop"] ?? street ?? "Pre-Flop"}</span>
      </div>
      <PotDisplay pot={pot} />
      <div className="texas-board" key={dealKey}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="relative">
            <PlayingCard card={cards[i]} faceDown={cards[i] == null} delay={260 + i * 130} board />
            <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[9px] font-black uppercase tracking-widest text-white/35">
              {labels[i]}
            </span>
          </div>
        ))}
      </div>
      {actions.length > 0 ? (
        <div className="relative z-20 flex max-w-[520px] flex-wrap justify-center gap-2">
          {actions.map((action, i) => (
            <ActionPill key={`${action.street}-${i}-${action.player}-${action.action}`} player={action.player} action={action.action} amount={actionAmount(action)} />
          ))}
        </div>
      ) : (
        <div className="relative z-20 text-[10px] font-black uppercase tracking-[0.28em] text-white/38">Waiting for action</div>
      )}
    </div>
  );
}

function PotDisplay({ pot }: { pot: number | null }) {
  return (
    <div className="texas-pot">
      <div className="flex -space-x-2" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => <ChipIcon key={i} dim={24} />)}
      </div>
      <div>
        <div className="text-[10px] font-black uppercase tracking-[0.28em] text-amber-100/45">Pot</div>
        <div className="text-2xl font-black leading-none text-amber-100 tabular-nums">{pot == null ? "-" : fmtChips(pot)}</div>
      </div>
    </div>
  );
}

function EmptyState({ isRunning }: { isRunning: boolean }) {
  return (
    <div className="flex h-full flex-col bg-[#08110d] text-white">
      <PokerStyles />
      <div className="relative flex flex-1 items-center justify-center overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(19,122,80,.35),transparent_32%),linear-gradient(135deg,#050806,#11100a_48%,#050806)]" />
        <div className="relative mx-6 flex max-w-sm flex-col items-center text-center">
          <div className="mb-5 grid h-24 w-24 place-items-center rounded-full border-[10px] border-[#5a3116] bg-gradient-to-br from-emerald-700 to-emerald-950 shadow-[0_24px_70px_rgba(0,0,0,.55)]">
            {isRunning ? (
              <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="text-amber-200 animate-spin">
                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              </svg>
            ) : (
              <span className="text-4xl text-amber-100">♠</span>
            )}
          </div>
          <p className="text-sm font-black text-white">{isRunning ? "Waiting for first hand..." : "No table is running"}</p>
          <p className="mt-2 text-xs font-medium text-white/45">{isRunning ? "The agents are taking their seats." : "Start a Texas Hold'em match from Config."}</p>
        </div>
      </div>
    </div>
  );
}

export default function TexasHoldEmLiveView() {
  const { state, showRound } = useApp();
  const match = state.activeMatch;
  const isRunning = Boolean(state.pendingGame);
  const activeIdx = state.activeRoundIndex;

  const cs = (match as Record<string, unknown>)?.currentState as Record<string, unknown> | undefined;
  const phase = cs?.phase as string | undefined;
  const useLive = isRunning && cs && phase !== "complete" && phase !== undefined;
  const history = match?.history ?? [];

  let hand: number | null = null;
  let holeCards: Record<string, string[]> | null = null;
  let community: string[] | null = null;
  let chips: Record<string, number> | null = null;
  let bets: Record<string, number> | null = null;
  let pot: number | null = null;
  let street: string | null = null;
  let actions: ActionEntry[] | null = null;
  let result: Record<string, unknown> | null = null;
  let turn: string | null = null;

  if (useLive) {
    hand = (cs.hand_number as number) ?? null;
    holeCards = (cs.hole_cards as Record<string, string[]>) ?? null;
    community = (cs.community_cards as string[]) ?? null;
    chips = (cs.chips as Record<string, number>) ?? null;
    bets = (cs.bets as Record<string, number>) ?? null;
    pot = (cs.pot as number) ?? null;
    street = (cs.street as string) ?? null;
    actions = (cs.street_actions as ActionEntry[]) ?? null;
    turn = ((cs.awaiting as string[]) ?? [])[0] ?? null;
    if (history.length > 0 && (cs.hand_over as boolean)) {
      result = ((history[history.length - 1]?.raw as Record<string, unknown>)?.result as Record<string, unknown>) ?? null;
    }
  } else {
    const entry = history[activeIdx] ?? null;
    const raw = entry?.raw as Record<string, unknown> | undefined;
    if (raw) {
      hand = (raw.hand as number) ?? null;
      holeCards = (raw.hole_cards as Record<string, string[]>) ?? null;
      community = (raw.community_cards as string[]) ?? null;
      chips = (raw.chips_after as Record<string, number>) ?? null;
      bets = (raw.bets as Record<string, number>) ?? null;
      pot = (raw.pot as number) ?? null;
      street = (raw.street as string) ?? null;
      actions = (raw.street_actions as ActionEntry[]) ?? null;
      result = (raw.result as Record<string, unknown>) ?? null;
    }
  }

  const allActions = actions ?? [];
  const grouped = useMemo(() => {
    const byStreet: Record<string, ActionEntry[]> = {};
    for (const action of allActions) {
      if (!byStreet[action.street]) byStreet[action.street] = [];
      byStreet[action.street].push(action);
    }
    return byStreet;
  }, [allActions]);

  if (!match) return <EmptyState isRunning={isRunning} />;

  const aCards = (holeCards?.A ?? []).map(parseCard).filter(Boolean) as CardData[];
  const bCards = (holeCards?.B ?? []).map(parseCard).filter(Boolean) as CardData[];
  const communityRaw = community ?? [];
  const communityCards = communityRaw.map(parseCard);
  const dealKey = useDealAnimationKey(communityRaw);
  const currentStreetActions = allActions.filter((action) => action.street === (street ?? "preflop"));
  const dealerSide = hand != null && hand % 2 === 0 ? "A" : "B";
  const scoreboardA = Math.round((match.total_score_a ?? 0) * 10) / 10;
  const scoreboardB = Math.round((match.total_score_b ?? 0) * 10) / 10;
  const roundProgress = match.num_rounds > 0 && hand ? Math.min(100, Math.round((hand / match.num_rounds) * 100)) : 0;
  const recentActions = allActions.slice(-5);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden text-white" style={tableRootStyle}>
      <PokerStyles />

      <div className="shrink-0 px-4 py-2.5" style={headerStyle}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-full border border-emerald-300/25 bg-emerald-500/12 text-lg text-emerald-100">♣</div>
            <div>
              <div className="text-[10px] font-black uppercase tracking-[0.32em] text-white/38">Texas Hold'em</div>
              <div className="flex items-center gap-2 text-sm font-black">
                <span className="tabular-nums">Hand {hand ?? "-"}</span>
                <span className="text-white/30">/</span>
                <span className="tabular-nums text-white/60">{match.num_rounds}</span>
              </div>
            </div>
          </div>

          <div className="min-w-[180px] flex-1 max-w-md">
            <div className="mb-1 flex items-center justify-between text-[10px] font-black uppercase tracking-widest text-white/38">
              <span>{STREET_LABEL[street ?? "preflop"] ?? street ?? "Pre-Flop"}</span>
              <span>{roundProgress}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-amber-300 to-red-400 transition-all duration-700" style={{ width: `${roundProgress}%` }} />
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5">
            <span className="text-xs font-black text-cyan-200 tabular-nums">{fmtChips(scoreboardA)}</span>
            <span className="max-w-[92px] truncate text-[11px] font-bold text-white/48">{match.agent_a}</span>
            <span className="text-[10px] font-black text-white/25">VS</span>
            <span className="max-w-[92px] truncate text-[11px] font-bold text-white/48">{match.agent_b}</span>
            <span className="text-xs font-black text-fuchsia-200 tabular-nums">{fmtChips(scoreboardB)}</span>
          </div>

          {result ? (
            <div className="rounded-full border border-amber-200/30 bg-amber-300/13 px-3 py-1.5 text-[11px] font-black text-amber-100 shadow-lg">
              {resultLine(result)}
            </div>
          ) : null}
        </div>
      </div>

      <div className="relative flex-1 overflow-hidden px-3 py-3 sm:px-5" style={arenaStyle}>
        <div className="absolute inset-0" style={arenaStyle} />
        <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/50 to-transparent" />

        <div className="texas-session">
          <PlayerSeat
            side="B"
            name={match.agent_b}
            cards={bCards}
            chips={chips?.B ?? 0}
            active={turn === "B"}
            dealer={dealerSide === "B"}
          />

          <div className="texas-table" style={railStyle}>
            <div className="absolute inset-[4px] rounded-[999px] border border-amber-100/20" />
            <div className="texas-felt" style={feltStyle}>
              <FeltTexture />
              <div className="absolute -left-1/3 top-0 h-full w-1/3 bg-gradient-to-r from-transparent via-white/12 to-transparent" style={{ animation: "texas-light-sweep 5.5s ease-in-out infinite" }} />
              {dealerSide === "A" ? (
                <DealerButton style={{ left: "26%", bottom: "21%" }} />
              ) : (
                <DealerButton style={{ right: "26%", top: "21%" }} />
              )}
              <BetMarker value={bets?.B ?? 0} side="B" />
              <BetMarker value={bets?.A ?? 0} side="A" />
              <Board cards={communityCards} dealKey={dealKey} street={street} pot={pot} actions={currentStreetActions} />
            </div>
          </div>

          <PlayerSeat
            side="A"
            name={match.agent_a}
            cards={aCards}
            chips={chips?.A ?? 0}
            active={turn === "A"}
            dealer={dealerSide === "A"}
          />
        </div>
      </div>

      <div className="shrink-0" style={footerRailStyle}>
        <div className="grid gap-3 px-4 py-3 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
          <div className="min-w-0">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-[10px] font-black uppercase tracking-[0.3em] text-white/35">Betting streets</span>
              {turn ? <span className="rounded-full bg-amber-300/15 px-2 py-1 text-[10px] font-black uppercase tracking-widest text-amber-100">{turn} to act</span> : null}
            </div>
            <div className="flex flex-wrap gap-2">
              {STREET_ORDER.map((streetName) => {
                const streetItems = grouped[streetName] ?? [];
                const isCurrent = streetName === (street ?? "preflop");
                return (
                  <div key={streetName} className={`min-h-[38px] min-w-[150px] flex-1 rounded-[8px] border px-3 py-2 ${isCurrent ? "border-emerald-300/35 bg-emerald-300/8" : "border-white/8 bg-white/[0.035]"}`}>
                    <div className="mb-1 text-[9px] font-black uppercase tracking-[0.22em] text-white/38">{STREET_LABEL[streetName]}</div>
                    <div className="flex flex-wrap gap-1.5">
                      {streetItems.length > 0 ? streetItems.map((action, i) => (
                        <ActionPill key={`${streetName}-${i}`} action={action.action} amount={actionAmount(action)} player={action.player} />
                      )) : <span className="text-[11px] font-semibold text-white/22">No action</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="min-w-0 rounded-[8px] border border-white/8 bg-white/[0.035] px-3 py-2">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-[0.3em] text-white/35">Hand history</span>
              {recentActions.length > 0 ? <span className="text-[10px] font-bold text-white/28">Latest {recentActions.length}</span> : null}
            </div>
            {history.length > 0 ? (
              <div className="flex gap-2 overflow-x-auto pb-1">
                {history.map((entry, idx) => {
                  const raw = entry.raw as Record<string, unknown> | undefined;
                  if (!raw) return null;
                  const handNum = raw.hand as number;
                  const res = raw.result as Record<string, unknown> | undefined;
                  const isActive = idx === activeIdx;
                  return (
                    <button
                      key={`${handNum}-${idx}`}
                      type="button"
                      onClick={() => showRound(idx)}
                      className={`min-w-[92px] rounded-[8px] border px-3 py-2 text-left transition ${
                        isActive ? "border-amber-200/45 bg-amber-200/12 shadow-[0_0_20px_rgba(251,191,36,.08)]" : "border-white/8 bg-black/18 hover:border-white/18 hover:bg-white/8"
                      }`}
                    >
                      <span className={`block text-xs font-black ${isActive ? "text-amber-100" : "text-white/60"}`}>Hand {handNum}</span>
                      <span className="mt-1 block truncate text-[10px] font-semibold text-white/35">{res ? resultLine(res) : "In progress"}</span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="flex min-h-[46px] items-center gap-2 text-[11px] font-semibold text-white/28">
                <ChipIcon dim={15} />
                <span>The first completed hand will appear here.</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
