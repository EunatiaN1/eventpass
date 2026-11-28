export const colors = {
  background: "#0A0A0A",
  surface: "rgba(255,255,255,0.055)",
  surfaceStrong: "rgba(17,17,17,0.9)",
  border: "rgba(255,255,255,0.1)",
  text: "#FFFFFF",
  secondary: "rgba(255,255,255,0.7)",
  muted: "rgba(255,255,255,0.42)",
  orange: "#FF6B00",
  orangeSoft: "#FF8A35",
  emerald: "#00E676",
  danger: "#FF786E",
};

export const spacing = { xs: 6, sm: 10, md: 16, lg: 24, xl: 32 };
export const radius = { sm: 12, md: 18, lg: 24, pill: 999 };
export const typography = {
  title: { fontSize: 30, lineHeight: 35, fontWeight: "700" as const, letterSpacing: -0.7 },
  heading: { fontSize: 21, lineHeight: 27, fontWeight: "700" as const, letterSpacing: -0.5 },
  body: { fontSize: 15, lineHeight: 22 },
  caption: { fontSize: 12, lineHeight: 17 },
};
