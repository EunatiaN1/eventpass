import { useCallback, useEffect, useState } from "react";
import { FlatList, Pressable, SafeAreaView, StyleSheet, Text, View } from "react-native";
import QRCode from "react-native-qrcode-svg";
import { LockKeyhole, Ticket as TicketIcon } from "lucide-react-native";
import { useFocusEffect } from "expo-router";
import { AuthModal } from "../../src/components/AuthModal";
import { useAuth } from "../../src/auth/AuthContext";
import { colors, radius, spacing, typography } from "../../src/theme/tokens";

type TicketRow = { id: string; status: string; event_id: string; event_title: string; event_date: string; event_venue: string; owner_wallet: string; tier?: string; original_price_zar: number };
type Credential = { qr_token: string };

export default function TicketsScreen() {
  const { user, isLoading, api, requestCode, verifyCode } = useAuth();
  const [tickets, setTickets] = useState<TicketRow[]>([]);
  const [authOpen, setAuthOpen] = useState(false);
  const [authDismissed, setAuthDismissed] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!user) return;
    try { setTickets(await api<TicketRow[]>(`/api/tickets?owner_wallet=${encodeURIComponent(user.wallet)}`)); setError(""); }
    catch (e: any) { setError(e?.message || "Tickets could not be loaded."); }
  }, [api, user]);
  useFocusEffect(useCallback(() => {
    if (user) void load();
    return undefined;
  }, [user, load]));
  const showAuth = authOpen || (!user && !isLoading && !authDismissed);

  return <SafeAreaView style={styles.screen}>
    <FlatList data={user ? tickets : []} keyExtractor={(t) => t.id} contentContainerStyle={styles.list} renderItem={({ item }) => <TicketPass ticket={item} api={api} />}
      ListHeaderComponent={<View style={styles.header}><Text style={styles.eyebrow}>YOUR EVENTPASS</Text><Text style={styles.title}>My Tickets</Text><Text style={styles.subtitle}>Every pass, ready when the night is.</Text>{!!user && <Text style={styles.wallet} numberOfLines={1}>ACCOUNT · {user.email}</Text>}{!!error && <Text style={styles.error}>{error}</Text>}</View>}
      ListEmptyComponent={user ? <View style={styles.empty}><TicketIcon size={24} color={colors.muted} /><Text style={styles.emptyText}>Your tickets will appear here after checkout.</Text></View> : <View style={styles.empty}><LockKeyhole size={24} color={colors.orangeSoft} /><Text style={styles.emptyText}>Sign in to view your digital passes.</Text><Pressable onPress={() => setAuthOpen(true)}><Text style={styles.link}>Continue with email</Text></Pressable></View>}
      ListFooterComponent={<View style={{ height: 110 }} />} />
    <AuthModal visible={showAuth} contextMessage="Sign in to view your tickets." onClose={() => { setAuthOpen(false); setAuthDismissed(true); }} requestCode={requestCode} verifyCode={verifyCode} />
  </SafeAreaView>;
}

function TicketPass({ ticket, api }: { ticket: TicketRow; api: <T>(path: string, options?: any) => Promise<T> }) {
  const [credential, setCredential] = useState("");
  useEffect(() => { let active = true; api<Credential>(`/api/tickets/${encodeURIComponent(ticket.id)}/credential`).then((r) => { if (active) setCredential(r.qr_token); }).catch(() => {}); return () => { active = false; }; }, [api, ticket.id]);
  const date = ticket.event_date ? new Date(ticket.event_date).toLocaleDateString("en-ZA", { weekday: "short", day: "numeric", month: "short", year: "numeric" }) : "Event date pending";
  return <View style={styles.pass}>
    <View style={styles.passTop}><View style={styles.passLabel}><TicketIcon size={14} color={colors.orangeSoft} /><Text style={styles.passEyebrow}>ADMISSION PASS</Text></View><Text style={styles.status}>{ticket.status.toUpperCase()}</Text></View>
    <Text style={styles.eventTitle}>{ticket.event_title}</Text><Text style={styles.passMeta}>{date}</Text><Text style={styles.passMeta}>{ticket.event_venue}</Text>
    <View style={styles.dashLine}><View style={styles.notchLeft} /><View style={styles.dash} /><View style={styles.notchRight} /></View>
    <View style={styles.passBottom}><View style={styles.passInfo}><Text style={styles.metaLabel}>TICKET ID</Text><Text style={styles.ticketId}>{ticket.id}</Text><Text style={[styles.metaLabel, { marginTop: 14 }]}>WALLET</Text><Text style={styles.walletText} numberOfLines={1}>{ticket.owner_wallet}</Text></View>
      <View style={styles.qrBox}>{credential ? <QRCode value={credential} size={92} backgroundColor="#FFFFFF" color="#111111" /> : <Text style={styles.qrLoading}>QR</Text>}</View>
    </View>
  </View>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, list: { padding: spacing.lg, paddingBottom: 20 }, header: { paddingTop: 15, paddingBottom: 25 }, eyebrow: { color: colors.orangeSoft, fontWeight: "800", fontSize: 10, letterSpacing: 1.7 }, title: { ...typography.title, color: colors.text, marginTop: 8 }, subtitle: { color: colors.secondary, marginTop: 7, fontSize: 13 }, wallet: { color: colors.muted, marginTop: 15, fontSize: 10, letterSpacing: 0.7 }, error: { color: colors.danger, marginTop: 12 }, empty: { marginTop: 38, padding: 24, alignItems: "center", gap: 13, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border }, emptyText: { color: colors.secondary, textAlign: "center", fontSize: 13 }, link: { color: colors.orangeSoft, fontWeight: "700" }, pass: { marginBottom: 18, padding: 20, borderRadius: 24, borderWidth: 1, borderColor: colors.border, backgroundColor: "rgba(255,255,255,0.055)" }, passTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" }, passLabel: { flexDirection: "row", gap: 7, alignItems: "center" }, passEyebrow: { color: colors.orangeSoft, fontSize: 9, letterSpacing: 1.1, fontWeight: "800" }, status: { color: colors.emerald, fontSize: 8, fontWeight: "800", letterSpacing: 1 }, eventTitle: { color: colors.text, fontWeight: "800", fontSize: 21, letterSpacing: -0.5, marginTop: 19 }, passMeta: { color: colors.secondary, fontSize: 12, marginTop: 5 }, dashLine: { flexDirection: "row", alignItems: "center", marginHorizontal: -20, marginTop: 21, marginBottom: 17 }, dash: { flex: 1, height: 1, borderStyle: "dashed", borderWidth: 1, borderColor: "rgba(255,255,255,0.18)" }, notchLeft: { width: 12, height: 24, borderTopRightRadius: 12, borderBottomRightRadius: 12, backgroundColor: colors.background }, notchRight: { width: 12, height: 24, borderTopLeftRadius: 12, borderBottomLeftRadius: 12, backgroundColor: colors.background }, passBottom: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" }, passInfo: { flex: 1, paddingRight: 10 }, metaLabel: { color: colors.muted, fontSize: 8, fontWeight: "800", letterSpacing: 1.1 }, ticketId: { color: colors.text, fontSize: 11, marginTop: 5, fontWeight: "700" }, walletText: { color: colors.secondary, fontSize: 9, marginTop: 5 }, qrBox: { width: 118, height: 118, backgroundColor: "#fff", borderRadius: 13, alignItems: "center", justifyContent: "center" }, qrLoading: { color: "#111", fontWeight: "800" },
});
