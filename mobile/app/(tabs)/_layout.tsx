import { BlurTargetView, BlurView } from "expo-blur";
import { Tabs } from "expo-router";
import { CalendarDays, Ticket, UserRound } from "lucide-react-native";
import { useRef } from "react";
import { Platform, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors } from "../../src/theme/tokens";

export default function TabLayout() {
  const targetRef = useRef<any>(null);
  const insets = useSafeAreaInsets();
  return <BlurTargetView ref={targetRef} style={styles.target}><Tabs screenOptions={({ route }) => ({
    headerShown: false,
    tabBarActiveTintColor: colors.orangeSoft,
    tabBarInactiveTintColor: colors.muted,
    tabBarLabelStyle: { fontSize: 10, fontWeight: "700", marginBottom: Platform.OS === "ios" ? 0 : 5 },
    tabBarStyle: [styles.bar, { height: 58 + insets.bottom, paddingBottom: Math.max(insets.bottom, 8) }],
    tabBarBackground: () => <View style={styles.background}><BlurView blurTarget={Platform.OS === "android" ? targetRef : undefined} blurMethod={Platform.OS === "android" ? "dimezisBlurViewSdk31Plus" : undefined} tint="dark" intensity={50} style={StyleSheet.absoluteFill} /><View style={styles.border} /></View>,
    tabBarIcon: ({ color, size }) => route.name === "index" ? <CalendarDays size={size} color={color} /> : route.name === "tickets" ? <Ticket size={size} color={color} /> : <UserRound size={size} color={color} />,
  })}>
    <Tabs.Screen name="index" options={{ title: "Events" }} />
    <Tabs.Screen name="tickets" options={{ title: "My Tickets" }} />
    <Tabs.Screen name="resale" options={{ title: "Resale" }} />
  </Tabs></BlurTargetView>;
}

const styles = StyleSheet.create({
  target: { flex: 1 },
  bar: { position: "absolute", backgroundColor: "transparent", borderTopWidth: 0, elevation: 0, paddingTop: 9 },
  background: { flex: 1, backgroundColor: "rgba(18,18,18,0.6)" },
  border: { position: "absolute", top: 0, left: 24, right: 24, height: 1, backgroundColor: colors.border },
});
