/* eslint react-hooks/immutability: off -- Reanimated shared values are intentionally updated in press handlers. */
import { PropsWithChildren, ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View, ViewStyle } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from "react-native-reanimated";
import { colors, radius } from "../theme/tokens";

type PrimaryButtonProps = PropsWithChildren<{
  onPress: () => void;
  disabled?: boolean;
  style?: ViewStyle;
  secondary?: boolean;
  loading?: boolean;
}>;

export function PrimaryButton({ children, onPress, disabled, style, secondary, loading }: PrimaryButtonProps) {
  const scale = useSharedValue(1);
  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  return (
    <Animated.View style={[animatedStyle, style]}>
      <Pressable
        accessibilityRole="button"
        disabled={disabled || loading}
        onPress={onPress}
        onPressIn={() => { scale.value = withSpring(0.97, { damping: 18, stiffness: 320 }); }}
        onPressOut={() => { scale.value = withSpring(1, { damping: 16, stiffness: 280 }); }}
        style={[styles.button, secondary && styles.secondary, disabled && styles.disabled]}
      >
        {loading ? <ActivityIndicator color={colors.text} /> : typeof children === "string" ? (
          <Text style={[styles.label, secondary && styles.secondaryLabel]}>{children}</Text>
        ) : <View style={styles.content}>{children as ReactNode}</View>}
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: 54,
    paddingHorizontal: 22,
    paddingVertical: 15,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.orange,
    shadowColor: colors.orange,
    shadowOpacity: 0.24,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 },
    elevation: 5,
  },
  secondary: { backgroundColor: "rgba(255,255,255,0.07)", borderWidth: 1, borderColor: colors.border, shadowOpacity: 0 },
  label: { color: colors.text, fontSize: 15, fontWeight: "700", letterSpacing: -0.15 },
  secondaryLabel: { color: colors.secondary },
  content: { flexDirection: "row", alignItems: "center", justifyContent: "center" },
  disabled: { opacity: 0.45 },
});
