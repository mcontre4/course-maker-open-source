import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

const colors = ["#4d6b47", "#6f5a96", "#b5583a", "#d9a441", "#8fb283"];
const pieceCount = 110;
/** Long enough for the slowest piece (delay + fall) to leave the screen. */
const lifetimeMs = 5200;

type Piece = Readonly<{ style: CSSProperties; round: boolean }>;

function makePieces(): readonly Piece[] {
  return Array.from({ length: pieceCount }, (_, index) => {
    const size = 7 + Math.random() * 7;
    return {
      round: index % 4 === 0,
      style: {
        "--x": `${Math.random() * 100}vw`,
        "--sway": `${(Math.random() - 0.5) * 18}vw`,
        "--spin": `${(Math.random() < 0.5 ? -1 : 1) * (360 + Math.random() * 720)}deg`,
        "--delay": `${Math.random() * 0.9}s`,
        "--fall": `${2.6 + Math.random() * 1.6}s`,
        width: size,
        height: index % 4 === 0 ? size : size * 0.55,
        background: colors[index % colors.length],
      } as CSSProperties,
    };
  });
}

/**
 * A one-time shower of paper over the page. It is decorative: hidden from
 * assistive technology, never catches clicks, and removes itself when done.
 * It mounts on the page body, because a transformed ancestor would otherwise
 * turn "fixed" into "fixed to that ancestor" and cut the shower short.
 * Visitors who prefer reduced motion get none (see lesson-quiz.css).
 */
export function Confetti() {
  const pieces = useMemo(makePieces, []);
  const [done, setDone] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setDone(true), lifetimeMs);
    return () => window.clearTimeout(timer);
  }, []);
  if (done) return null;
  return createPortal(
    <div className="confetti" aria-hidden="true" data-testid="confetti">
      {pieces.map((piece, index) => (
        <i
          key={index}
          className={piece.round ? "confetti-piece round" : "confetti-piece"}
          style={piece.style}
        />
      ))}
    </div>,
    document.body,
  );
}
