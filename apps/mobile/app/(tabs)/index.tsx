import { useCallback, useEffect, useState } from "react";
import { FlatList, Pressable, RefreshControl, SafeAreaView, StyleSheet, Text, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { AuthModal } from "../../src/components/AuthModal";
import { CheckoutSheet } from "../../src/components/CheckoutSheet";
import { EventCard, EventItem } from "../../src/components/EventCard";
import { useAuth } from "../../src/auth/AuthContext";
import { colors, spacing, typography } from "../../src/theme/tokens";

export default function EventsScreen() {
  const { user, isLoading, api, requestCode, verifyCode } = useAuth();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [authOpen, setAuthOpen] = useState(false);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [selected, setSelected] = useState<EventItem | null>(null);
  const [pendingEvent, setPendingEvent] = useState<EventItem | null>(null);

  const load = useCallback(async () => {
    try { setEvents(await api<EventItem[]>("/api/events")); setError(""); }
    catch (loadError: any) { setError(loadError?.message || "Events are unavailable right now."); }
  }, [api]);
  // Initial list data is fetched asynchronously when this screen mounts.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);
  const refresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const buy = (event: EventItem) => {
    setSelected(event);
    if (!user) { setPendingEvent(event); setAuthOpen(true); return; }
    setCheckoutOpen(true);
  };

  return <SafeAreaView style={styles.screen}>
    <FlatList
      data={events}
      numColumns={2}
      columnWrapperStyle={styles.eventRow}
      keyExtractor={(event) => event.id}
      renderItem={({ item, index }) => <Animated.View entering={FadeInDown.delay(Math.min(index, 5) * 70).duration(350)}><EventCard event={item} onBuy={buy} /></Animated.View>}
      contentContainerStyle={styles.list}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.orange} />}
      ListHeaderComponent={<View style={styles.header}>
        <View style={styles.brandRow}><View style={styles.logo}><Text style={styles.logoText}>E</Text></View><View style={styles.brandCopy}><Text style={styles.brand}>EVENTPASS</Text><Text style={styles.kicker}>SOUTH AFRICA · LIVE CULTURE</Text></View>
          <Pressable accessibilityRole="button" accessibilityLabel={user ? `Signed in as ${user.email}` : "Sign in"} onPress={() => { if (!user) setAuthOpen(true); }} style={[styles.accountButton, user && styles.avatar]}><Text style={styles.accountLabel}>{user ? (user.email?.[0]?.toUpperCase() || "E") : "Sign in"}</Text></Pressable>
        </View>
        <Text style={styles.heading}>Find your{ "\n" }next moment.</Text>
        <Text style={styles.subheading}>Live music, culture, and nights worth remembering.</Text>
        <View style={styles.sectionRow}><Text style={styles.sectionTitle}>Curated for you</Text><Text style={styles.eventCount}>{events.length} EVENTS</Text></View>
        {!!error && <Text style={styles.error}>{error}</Text>}
        {!isLoading && !events.length && !error && <Text style={styles.empty}>No upcoming events yet. Pull down to refresh.</Text>}
      </View>}
      ListFooterComponent={<View style={{ height: 110 }} />}
    />
    <AuthModal visible={authOpen} contextMessage={pendingEvent ? "Sign in to finalize your purchase." : undefined} onClose={() => { setAuthOpen(false); setPendingEvent(null); }} requestCode={requestCode} verifyCode={verifyCode}
      onAuthenticated={() => { if (pendingEvent) { setSelected(pendingEvent); setCheckoutOpen(true); setPendingEvent(null); } }} />
    {user && <CheckoutSheet visible={checkoutOpen} event={selected} user={user} onClose={() => setCheckoutOpen(false)} />}
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, list: { paddingBottom: 18 }, eventRow: { gap: 10, paddingHorizontal: 14 }, header: { paddingHorizontal: spacing.lg, paddingTop: 14, paddingBottom: 24 }, brandRow: { flexDirection: "row", alignItems: "center", marginBottom: 31 }, logo: { width: 38, height: 38, borderRadius: 14, backgroundColor: colors.orange, alignItems: "center", justifyContent: "center" }, logoText: { color: colors.text, fontSize: 22, fontWeight: "800" }, brandCopy: { marginLeft: 10, flex: 1 }, brand: { color: colors.text, fontSize: 12, fontWeight: "800", letterSpacing: 2.4 }, kicker: { color: colors.muted, fontSize: 8, fontWeight: "700", letterSpacing: 1.1, marginTop: 3 }, accountButton: { minWidth: 44, height: 40, paddingHorizontal: 12, borderRadius: 15, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: colors.border, backgroundColor: "rgba(255,255,255,0.05)" }, avatar: { width: 42, paddingHorizontal: 0, borderRadius: 21, backgroundColor: "rgba(255,107,0,0.2)" }, accountLabel: { color: colors.text, fontWeight: "700", fontSize: 12 }, heading: { ...typography.title, color: colors.text, fontSize: 34, lineHeight: 39, letterSpacing: -1.2 }, subheading: { color: colors.secondary, fontSize: 14, lineHeight: 21, marginTop: 10, maxWidth: 300 }, sectionRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 30, marginBottom: 17 }, sectionTitle: { ...typography.heading, color: colors.text, fontSize: 18 }, eventCount: { color: colors.muted, fontSize: 9, letterSpacing: 1.2, fontWeight: "700" }, error: { color: colors.danger, fontSize: 13, marginBottom: 12 }, empty: { color: colors.secondary, paddingVertical: 18, fontSize: 13 },
});
