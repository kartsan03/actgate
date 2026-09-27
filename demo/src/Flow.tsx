import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

export const FPS = 15;
export const WIDTH = 960;
export const HEIGHT = 540;
export const TOTAL = 132;

const PAPER = "#efeae0";
const INK = "#1c1915";
const DIM = "#6e675e";
const RULE = "#c9c1b3";
const AMBER = "#8a5a12";
const GREEN = "#245c32";

const FONT = '"DejaVu Sans Mono", ui-monospace, monospace';
const SIZE = 20;
const LINE = 30;
const LEFT = 36;
const TOP = 78;

type Kind = "cmd" | "out";

type Row = {
  kind: Kind;
  text: string;
  color?: string;
  start: number;
  speed: number;
};

const ROWS: Row[] = [
  { kind: "cmd", text: "actgate mcp --upstream python echo_server.py", start: 4, speed: 3 },
  { kind: "out", text: "tool echo", start: 20, speed: 0, color: DIM },
  { kind: "cmd", text: "tools/call echo text=ship it", start: 28, speed: 3 },
  { kind: "out", text: "ACTGATE_PENDING  43e0d748", start: 40, speed: 0, color: AMBER },
  { kind: "out", text: "upstream  0", start: 46, speed: 0, color: AMBER },
  { kind: "cmd", text: "actgate approve 43e0d748", start: 58, speed: 3 },
  { kind: "out", text: "approve", start: 70, speed: 0, color: DIM },
  { kind: "out", text: "upstream  0", start: 74, speed: 0, color: DIM },
  { kind: "cmd", text: "tools/call echo text=ship it", start: 84, speed: 3 },
  { kind: "out", text: "ship it", start: 96, speed: 0, color: GREEN },
  { kind: "out", text: "upstream  1", start: 100, speed: 0, color: GREEN },
];

const visibleChars = (row: Row, frame: number) => {
  if (frame < row.start) return -1;
  if (row.kind === "out") return row.text.length;
  const n = Math.floor((frame - row.start) * row.speed);
  return Math.min(row.text.length, n);
};

const caretRow = (frame: number) => {
  let current = -1;
  ROWS.forEach((row, i) => {
    if (row.kind !== "cmd" || frame < row.start) return;
    const done = row.start + Math.ceil(row.text.length / row.speed);
    if (frame <= done + 4) current = i;
  });
  return current;
};

const caption = (frame: number) => {
  if (frame < 58) return "1  pending";
  if (frame < 84) return "2  approve";
  return frame < 100 ? "3  execute" : "3  execute   once";
};

export const Flow: React.FC = () => {
  const frame = useCurrentFrame();
  const blink = Math.floor(frame / 8) % 2 === 0;
  const active = caretRow(frame);

  return (
    <AbsoluteFill style={{ backgroundColor: PAPER }}>
        <div
          style={{
            position: "absolute",
            left: 28,
            top: 22,
            color: DIM,
            fontFamily: FONT,
            fontSize: 13,
            letterSpacing: 0.4,
          }}
        >
          actgate    ledger.jsonl
        </div>
        <div
          style={{
            position: "absolute",
            right: 28,
            top: 22,
            color: frame >= 152 ? GREEN : frame >= 96 ? INK : AMBER,
            fontFamily: FONT,
            fontSize: 13,
            letterSpacing: 0.4,
          }}
        >
          {caption(frame)}
        </div>
        <div
          style={{
            position: "absolute",
            left: 28,
            right: 28,
            top: 48,
            height: 1,
            backgroundColor: RULE,
          }}
        />
        {ROWS.map((row, i) => {
          const n = visibleChars(row, frame);
          if (n < 0) return null;
          const text = row.text.slice(0, n);
          const showCaret = row.kind === "cmd" && active === i && n < row.text.length && blink;
          const mark = i === 3 || i === 6 || i === 9;
          const markColor = i === 9 ? GREEN : i === 3 ? AMBER : DIM;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: LEFT - 14,
                top: TOP + i * LINE,
                height: LINE,
                whiteSpace: "pre",
                fontFamily: FONT,
                fontSize: SIZE,
                lineHeight: `${LINE}px`,
                color: row.color ?? INK,
                borderLeft: mark ? `2px solid ${markColor}` : "2px solid transparent",
                paddingLeft: 12,
              }}
            >
              {row.kind === "cmd" ? "$ " : "  "}
              {text}
              {showCaret ? (
                <span
                  style={{
                    display: "inline-block",
                    width: 10,
                    height: 18,
                    backgroundColor: INK,
                    transform: "translateY(3px)",
                  }}
                />
              ) : null}
            </div>
          );
        })}
    </AbsoluteFill>
  );
};
