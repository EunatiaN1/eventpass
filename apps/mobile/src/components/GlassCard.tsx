import { BlurView } from "expo-blur";
import { PropsWithChildren } from "react";
import { StyleProp, StyleSheet, View, ViewStyle } from "react-native";
import { colors, radius } from "../theme/tokens";

type GlassCardProps = PropsWithChildren<{
  style?: StyleProp<ViewStyle>;
  contentStyle?: StyleProp<ViewStyle>;
  intensity?: number;
}>;

export function GlassCard({ children, style, contentStyle, intensity = 50 }: GlassCardProps) {
  return (
    <View style={[styles.shell, style]}>
      <BlurView intensity={intensity} tint="dark" style={StyleSheet.absoluteFill} />
      <View style={[styles.content, contentStyle]}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: {
    overflow: "hidden",
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "rgba(18,18,18,0.65)",
  },
  content: { flex: 1 },
});
