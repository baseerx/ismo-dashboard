// Validated categorical + status colors for the dashboard's charts.
// Categorical slots are accent hues (never reused for status); status colors
// are reserved for actual good/warning/critical states and never doubled as
// generic series colors. Light/dark steps chosen from the app's own design
// tokens (frontend/src/index.css) and verified with the dataviz palette
// validator for CVD-safe adjacent contrast in both modes.

export const categorical = {
  light: ["#465fff", "#0ba5ec", "#7a5af8", "#ee46bc", "#fb6514", "#667085"],
  dark: ["#3641f5", "#0086c9", "#6938ef", "#dd2590", "#ec4a0a", "#98a2b3"],
};

export const status = {
  light: { good: "#12b76a", warning: "#f79009", critical: "#f04438", info: "#0ba5ec" },
  dark: { good: "#12b76a", warning: "#f79009", critical: "#f04438", info: "#0ba5ec" },
};

export function categoricalColors(theme: "light" | "dark", count: number): string[] {
  const set = categorical[theme];
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    out.push(set[i % set.length]);
  }
  return out;
}
