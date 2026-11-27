import { useMemo } from "react";

export function QrCodeMatrix({ value, size = 11 }) {
  const cells = useMemo(() => {
    const seed = value || "eventpass";
    let hash = 2166136261;
    for (let i = 0; i < seed.length; i++) {
      hash ^= seed.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }

    const grid = [];
    for (let r = 0; r < size; r++) {
      for (let c = 0; c < size; c++) {
        const inTopLeft = r < 3 && c < 3;
        const inTopRight = r < 3 && c >= size - 3;
        const inBottomLeft = r >= size - 3 && c < 3;
        const isFinderBorder =
          ((inTopLeft || inTopRight || inBottomLeft) &&
            (r === 0 || r === 2 || r === size - 1 || r === size - 3 || c === 0 || c === 2 || c === size - 1 || c === size - 3)) ||
          (r === 1 && c === 1) ||
          (r === 1 && c === size - 2) ||
          (r === size - 2 && c === 1);

        const isDark =
          inTopLeft || inTopRight || inBottomLeft
            ? isFinderBorder
            : (((hash >>> ((r * size + c) % 24)) ^ (r * 31 + c * 17)) & 1) === 1;

        grid.push({ key: `${r}-${c}`, isDark });
      }
    }
    return grid;
  }, [value, size]);

  return (
    <div className="inline-flex flex-col items-center justify-center rounded-2xl bg-white p-3 shadow-lg">
      <div
        className="grid gap-[2px]"
        style={{ gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))` }}
        aria-label="Digital Ticket QR Credential"
      >
        {cells.map((cell) => (
          <div
            key={cell.key}
            className={`w-2.5 h-2.5 rounded-[1px] ${cell.isDark ? "bg-[#0A0A0A]" : "bg-white"}`}
          />
        ))}
      </div>
    </div>
  );
}
