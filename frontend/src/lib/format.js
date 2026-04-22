export function fmtINR(n, digits = 2) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  return `${sign}₹${abs.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

export function fmtPct(n, digits = 2) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${Number(n).toFixed(digits)}%`;
}

export function fmtNum(n, digits = 2) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signedClass(n) {
  if (n === null || n === undefined || isNaN(n)) return "";
  if (n > 0) return "text-emerald-400";
  if (n < 0) return "text-red-400";
  return "text-zinc-400";
}

export function regimeColor(r) {
  if (r === "Bull") return { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/40", dot: "bg-emerald-500" };
  if (r === "Bear") return { text: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/40", dot: "bg-red-500" };
  if (r === "Sideways") return { text: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/40", dot: "bg-amber-500" };
  return { text: "text-zinc-400", bg: "bg-zinc-500/10", border: "border-zinc-500/40", dot: "bg-zinc-500" };
}
