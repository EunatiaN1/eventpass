import { useCallback, useEffect, useState } from "react";
import { FlatList, Pressable, SafeAreaView, Share, StyleSheet, Text, TextInput, View } from "react-native";
import { ArrowUpRight, Ticket } from "lucide-react-native";
import { AuthModal } from "../../src/components/AuthModal";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { useAuth } from "../../src/auth/AuthContext";
import { colors, radius, spacing, typography } from "../../src/theme/tokens";

type TicketRow = { id: string; event_id: string; event_title: string; event_date?: string; status: string; original_price_zar: number; resale_enabled: boolean; active_listing?: unknown };
type Campaign = { id: string; slug: string; title: string; event_title: string; available_count: number; share_path: string };

export default function ResaleScreen() {
  const { user, api, requestCode, verifyCode } = useAuth();
  const [tickets, setTickets] = useState<TicketRow[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [authOpen, setAuthOpen] = useState(false);
  const [priceByTicket, setPriceByTicket] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setCampaigns(await api<Campaign[]>("/api/campaigns"));
      if (user) {
        const rows = await api<TicketRow[]>(`/api/tickets?owner_wallet=${encodeURIComponent(user.wallet)}`);
        setTickets(rows);
        setPriceByTicket((current) => Object.fromEntries(rows.map((t) => [t.id, current[t.id] || String(t.original_price_zar)])));
      }
    } catch (e: any) { setError(e?.message || "Resale is unavailable right now."); }
  }, [api, user]);
  // Public campaigns and the signed-in user's listings are fetched on entry.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [user, load]);

  const listTicket = async (ticket: TicketRow) => {
    if (!user) { setAuthOpen(true); return; }
    setBusyId(ticket.id); setError(""); setMessage("");
    try {
      const price = Number(priceByTicket[ticket.id] || ticket.original_price_zar);
      const result = await api<Campaign>("/api/campaigns", { method: "POST", body: JSON.stringify({ seller_wallet: user.wallet, title: `${ticket.event_title} resale`, items: [{ ticket_id: ticket.id, asking_price_zar: price }] }) });
      setMessage(`Your ticket is listed. Share code: ${result.slug}`);
      await load();
    } catch (e: any) { setError(e?.message || "This ticket could not be listed."); }
    finally { setBusyId(""); }
  };

  const eligible = tickets.filter((t) => ["issued", "sold"].includes(t.status) && !t.active_listing && t.resale_enabled);
  return <SafeAreaView style={styles.screen}>
    <FlatList data={eligible} keyExtractor={(t) => t.id} contentContainerStyle={styles.list} renderItem={({ item }) => <GlassCard style={styles.ticketCard}>
      <View style={styles.ticketHead}><Ticket size={17} color={colors.orangeSoft} /><Text style={styles.eventTitle} numberOfLines={1}>{item.event_title}</Text></View>
      <Text style={styles.ticketMeta}>Original price · R{item.original_price_zar}</Text>
      <TextInput keyboardType="number-pad" value={priceByTicket[item.id] || String(item.original_price_zar)} onChangeText={(v) => setPriceByTicket((prev) => ({ ...prev, [item.id]: v.replace(/\D/g, "") }))} placeholder="Asking price (ZAR)" placeholderTextColor={colors.muted} style={styles.input} />
      <PrimaryButton onPress={() => listTicket(item)} loading={busyId === item.id} disabled={!!busyId}>List for Resale</PrimaryButton>
    </GlassCard>} ListHeaderComponent={<View style={styles.header}>
      <Text style={styles.eyebrow}>PASS IT ON</Text><Text style={styles.title}>Resale, thoughtfully.</Text><Text style={styles.subtitle}>List eligible tickets at the organizer’s capped price and share a private campaign link.</Text>
      {!!user && <Text style={styles.wallet}>ACCOUNT · {user.email}</Text>}
      {!!error && <Text style={styles.error}>{error}</Text>}{!!message && <Text style={styles.message}>{message}</Text>}
      <Text style={styles.section}>Your eligible tickets</Text>
      {user && eligible.length === 0 && <Text style={styles.empty}>No tickets are currently eligible to list.</Text>}
      {!user && <View style={styles.emptyBox}><Text style={styles.empty}>Sign in with your email to manage your resale tickets.</Text><Pressable onPress={() => setAuthOpen(true)}><Text style={styles.link}>Continue with email</Text></Pressable></View>}
      {campaigns.length > 0 && <Text style={styles.section}>Live campaigns</Text>}
      {campaigns.map((campaign) => <Pressable key={campaign.id} onPress={() => Share.share({ message: `${campaign.title}\n${campaign.share_path}` })} style={styles.campaign}>
        <View style={{ flex: 1 }}><Text style={styles.campaignTitle}>{campaign.title}</Text><Text style={styles.campaignSub}>{campaign.available_count} ticket(s) available · {campaign.slug}</Text></View><ArrowUpRight size={17} color={colors.orangeSoft} />
      </Pressable>)}
    </View>} ListFooterComponent={<View style={{ height: 110 }} />} />
    <AuthModal visible={authOpen} contextMessage="Sign in to list tickets for resale." onClose={() => setAuthOpen(false)} requestCode={requestCode} verifyCode={verifyCode} />
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, list: { padding: spacing.lg, paddingBottom: 20 }, header: { paddingTop: 15, paddingBottom: 15 }, eyebrow: { color: colors.orangeSoft, fontWeight: "800", fontSize: 10, letterSpacing: 1.7 }, title: { ...typography.title, color: colors.text, marginTop: 8, fontSize: 29 }, subtitle: { color: colors.secondary, fontSize: 13, lineHeight: 20, marginTop: 8 }, wallet: { color: colors.muted, marginTop: 14, fontSize: 10 }, section: { ...typography.heading, color: colors.text, fontSize: 17, marginTop: 28, marginBottom: 13 }, error: { color: colors.danger, marginTop: 12, fontSize: 12 }, message: { color: colors.emerald, marginTop: 12, fontSize: 12 }, emptyBox: { padding: 18, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, alignItems: "center", gap: 12 }, empty: { color: colors.secondary, fontSize: 12, lineHeight: 18 }, link: { color: colors.orangeSoft, fontSize: 12, fontWeight: "700" }, ticketCard: { marginBottom: 14 }, ticketHead: { flexDirection: "row", alignItems: "center", gap: 9 }, eventTitle: { color: colors.text, fontSize: 14, fontWeight: "700", flex: 1 }, ticketMeta: { color: colors.secondary, fontSize: 11, marginTop: 9, marginBottom: 12 }, input: { height: 48, borderRadius: 14, borderWidth: 1, borderColor: colors.border, backgroundColor: "rgba(0,0,0,0.35)", paddingHorizontal: 13, color: colors.text, marginBottom: 12 }, campaign: { marginBottom: 12, padding: 16, borderRadius: 18, borderColor: colors.border, borderWidth: 1, backgroundColor: colors.surface, flexDirection: "row", alignItems: "center", gap: 10 }, campaignTitle: { color: colors.text, fontSize: 13, fontWeight: "700", flex: 1 }, campaignSub: { color: colors.muted, fontSize: 10, marginTop: 3 },
});
