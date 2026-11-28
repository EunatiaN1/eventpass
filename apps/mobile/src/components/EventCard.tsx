/* eslint react-hooks/immutability: off -- Reanimated shared values are intentionally updated in press handlers. */
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { CalendarDays, MapPin, ShieldCheck } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from "react-native-reanimated";
import { colors, radius, spacing, typography } from "../theme/tokens";
import { GlassCard } from "./GlassCard";

const IMAGES: Record<string, string> = {
  "evt-ct-electronic-2026": "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?auto=format&fit=crop&w=1200&q=85",
  "evt-afrofuture-jhb-2026": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=1200&q=85",
  "evt-soweto-jazz-2026": "https://images.unsplash.com/photo-1511192336575-5a79af67a629?auto=format&fit=crop&w=1200&q=85",
};
const FALLBACK = "https://images.unsplash.com/photo-1540039155733-5bb30b53aa14?auto=format&fit=crop&w=1200&q=85";

export type EventItem = {
  id: string;
  title: string;
  venue: string;
  event_date: string;
  ticket_price_zar: number;
  max_resale_price_zar?: number;
  resale_enabled?: boolean;
  refund_window?: { eligible: boolean; cutoff_at_local?: string };
};

export function EventCard({ event, onBuy }: { event: EventItem; onBuy: (event: EventItem) => void }) {
  const scale = useSharedValue(1);
  const pressStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const date = new Date(event.event_date).toLocaleDateString("en-ZA", {
    weekday: "short", day: "numeric", month: "short", year: "numeric",
  });

  return (
    <Animated.View style={[styles.animated, pressStyle]}>
      <GlassCard style={styles.card}>
        <View style={styles.imageWrap}>
          <Image source={{ uri: IMAGES[event.id] || FALLBACK }} style={StyleSheet.absoluteFill} contentFit="cover" transition={350} />
          <LinearGradient colors={["rgba(10,10,10,0.02)", "rgba(10,10,10,0.12)", "#0A0A0A"]} locations={[0, 0.5, 1]} style={StyleSheet.absoluteFill} />
          <View style={styles.badge}>
            <View style={styles.badgeDot} />
            <Text style={styles.badgeText}>{event.resale_enabled ? "RESALE PROTECTED" : "RESALE PAUSED"}</Text>
          </View>
          <View style={styles.priceBadge}><Text style={styles.priceText}>R{event.ticket_price_zar}</Text></View>
        </View>
        <View style={styles.details}>
          <Text style={styles.title} numberOfLines={2}>{event.title}</Text>
          <View style={styles.metaRow}>
            <CalendarDays size={15} color={colors.orangeSoft} />
            <Text style={styles.metaText}>{date}</Text>
          </View>
          <View style={styles.metaRow}>
            <MapPin size={15} color={colors.emerald} />
            <Text style={styles.metaText} numberOfLines={1}>{event.venue}</Text>
          </View>
          <View style={styles.protectionRow}>
            <ShieldCheck size={15} color={colors.emerald} />
            <Text style={styles.protectionText}>
              {event.refund_window?.eligible ? "75% refund protection" : "Refund window closed"}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => onBuy(event)}
            onPressIn={() => { scale.value = withSpring(0.97); }}
            onPressOut={() => { scale.value = withSpring(1); }}
            style={styles.buyButton}
          >
            <Text style={styles.buyText}>Get tickets · R{event.ticket_price_zar}</Text>
          </Pressable>
        </View>
      </GlassCard>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  animated: { flex: 1, marginBottom: spacing.md },
  card: { borderRadius: radius.lg },
  imageWrap: { height: 176, overflow: "hidden" },
  badge: {
    position: "absolute", top: 14, left: 14, flexDirection: "row", alignItems: "center", gap: 7,
    borderRadius: radius.pill, paddingHorizontal: 11, paddingVertical: 7,
    backgroundColor: "rgba(0,0,0,0.5)", borderWidth: 1, borderColor: colors.border,
  },
  badgeDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.emerald },
  badgeText: { fontSize: 9, fontWeight: "700", color: colors.text, letterSpacing: 1.1 },
  priceBadge: { position: "absolute", top: 14, right: 14, borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 7, backgroundColor: "rgba(10,10,10,0.7)" },
  priceText: { color: colors.text, fontSize: 13, fontWeight: "700" },
  details: { padding: 14, paddingTop: 10, gap: 9, backgroundColor: "#0A0A0A" },
  title: { ...typography.heading, color: colors.text, fontSize: 15, lineHeight: 19, marginBottom: 2 },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  metaText: { color: colors.secondary, fontSize: 11, flexShrink: 1 },
  protectionRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 1 },
  protectionText: { color: colors.emerald, fontSize: 10, fontWeight: "600", flexShrink: 1 },
  buyButton: { marginTop: 5, minHeight: 46, borderRadius: radius.md, backgroundColor: colors.orange, alignItems: "center", justifyContent: "center", paddingHorizontal: 5 },
  buyText: { color: colors.text, fontSize: 11, fontWeight: "700", textAlign: "center" },
});
