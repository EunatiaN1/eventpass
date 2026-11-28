import { BlurView } from "expo-blur";
import * as Crypto from "expo-crypto";
import * as Clipboard from "expo-clipboard";
import QRCode from "react-native-qrcode-svg";
import { ArrowLeft, CheckCircle2, Copy, CreditCard, Landmark, WalletCards } from "lucide-react-native";
import { useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import Animated, { FadeInDown, ZoomIn } from "react-native-reanimated";
import { EventPassUser, useAuth } from "../auth/AuthContext";
import { colors, spacing, typography } from "../theme/tokens";
import { EventItem } from "./EventCard";
import { GlassCard } from "./GlassCard";
import { PrimaryButton } from "./PrimaryButton";

type Ticket = { id: string; qr_token?: string; tier?: string; event_id: string };
type Order = { order_reference: string; total_zar: number; tickets: Ticket[] };
type Props = { visible: boolean; event: EventItem | null; user: EventPassUser; onClose: () => void };
type Method = "eft" | "card" | "x402";
type Config = { x402_pay_to_address: string; network: string; usdc_mint: string; amount_usdc: string };

const METHODS: { id: Method; label: string; icon: typeof Landmark }[] = [
  { id: "eft", label: "EFT", icon: Landmark },
  { id: "card", label: "Card", icon: CreditCard },
  { id: "x402", label: "x402", icon: WalletCards },
];
const BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
async function createSolanaReference() {
  const bytes = await Crypto.getRandomBytesAsync(32);
  let value = BigInt(`0x${Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("")}`);
  let encoded = "";
  while (value > 0n) { const remainder = Number(value % 58n); encoded = BASE58[remainder] + encoded; value /= 58n; }
  for (let i = 0; i < bytes.length && bytes[i] === 0; i += 1) encoded = `1${encoded}`;
  return encoded;
}

export function CheckoutSheet({ visible, event, user, onClose }: Props) {
  const { api } = useAuth();
  const [method, setMethod] = useState<Method>("eft");
  const [order, setOrder] = useState<Order | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [solanaReference, setSolanaReference] = useState("");

  const startOrder = async () => {
    if (!event || !user.wallet || busy) return;
    setBusy(true); setError("");
    try {
      const result = await api<Order>(`/api/events/${encodeURIComponent(event.id)}/purchase-primary`, {
        method: "POST",
        body: JSON.stringify({ buyer_wallet: user.wallet, quantity: 1, tier: "General Admission", payment_method: method }),
      });
      setOrder(result);
      await api(`/api/checkout/${encodeURIComponent(result.order_reference)}/method?payment_method=${method}`, { method: "PATCH" });
      if (method === "x402") {
        const [checkoutConfig, reference] = await Promise.all([
          api<Config>(`/api/checkout/config?amount_zar=${result.total_zar}`), createSolanaReference(),
        ]);
        setConfig(checkoutConfig); setSolanaReference(reference);
      }
    } catch (requestError: any) {
      setError(requestError?.message || "Checkout could not start. Please try again.");
    } finally { setBusy(false); }
  };

  const switchMethod = async (next: Method) => {
    if (next === method || busy) return;
    setError(""); setConfig(null); setSolanaReference("");
    if (!order) { setMethod(next); return; }
    setBusy(true);
    try {
      await api(`/api/checkout/${encodeURIComponent(order.order_reference)}/method?payment_method=${next}`, { method: "PATCH" });
      setMethod(next);
      if (next === "x402") {
        const [checkoutConfig, reference] = await Promise.all([
          api<Config>(`/api/checkout/config?amount_zar=${order.total_zar}`), createSolanaReference(),
        ]);
        setConfig(checkoutConfig); setSolanaReference(reference);
      }
    } catch (requestError: any) {
      setError(requestError?.message || "Payment method could not be changed.");
    } finally { setBusy(false); }
  };

  const confirmSimulation = async () => {
    if (!order || busy) return;
    setBusy(true); setError("");
    try {
      if (method === "card") await new Promise((resolve) => setTimeout(resolve, 2000));
      if (method === "x402") await new Promise((resolve) => setTimeout(resolve, 3000));
      await api("/api/webhooks/mock-success", {
        method: "POST",
        body: JSON.stringify({ ticket_id: order.tickets[0].id, payment_method: method }),
      });
      setReceipt(true);
    } catch (requestError: any) {
      setError(requestError?.message || "We couldn't complete the simulation. Try again.");
    } finally { setBusy(false); }
  };

  const copyDetails = async () => {
    const reference = `EVT-${order?.tickets[0]?.id || "ticket"}`;
    await Clipboard.setStringAsync(`EventPass Treasury\nBank: FNB\nAccount: 62000000000\nBranch: 250655\nReference: ${reference}`);
    setCopied(true); setTimeout(() => setCopied(false), 1800);
  };

  const dismiss = () => {
    if (busy) return;
    setMethod("eft"); setOrder(null); setConfig(null); setReceipt(false); setError(""); setSolanaReference("");
    onClose();
  };

  if (!event) return null;
  const qrValue = order?.tickets[0]?.qr_token || order?.tickets[0]?.id || "";
  const transferUrl = config && order
    ? `solana:${config.x402_pay_to_address}?amount=${encodeURIComponent(config.amount_usdc)}&spl-token=${config.usdc_mint}&reference=${encodeURIComponent(solanaReference)}`
    : "";

  return (
    <Modal visible={visible} transparent animationType="slide" statusBarTranslucent onRequestClose={dismiss}>
      <View style={styles.overlay}>
        <BlurView intensity={50} tint="dark" style={StyleSheet.absoluteFill} />
        <Pressable style={StyleSheet.absoluteFill} onPress={dismiss} />
        <Animated.View entering={FadeInDown.duration(240)} style={styles.wrap}>
          <GlassCard style={styles.sheet} contentStyle={styles.content} intensity={50}>
            <View style={styles.handle} />
            {receipt ? (
              <ScrollView contentContainerStyle={styles.receipt}>
                <Animated.View entering={ZoomIn.duration(500)} style={styles.successCircle}><CheckCircle2 size={46} color={colors.emerald} /></Animated.View>
                <Text style={styles.title}>Payment Successful</Text>
                <Text style={styles.subtitle}>Payment Successful via {method === "x402" ? "x402" : method.toUpperCase()}</Text>
                <Text style={styles.simulationNotice}>Test simulation only · No funds were moved</Text>
                <View style={styles.qrBox}><QRCode value={qrValue || "eventpass-demo"} size={176} backgroundColor="#FFFFFF" color="#111111" /></View>
                <Text style={styles.ticketId}>Digital pass · {order?.tickets[0]?.id}</Text>
                <Text style={styles.muted}>{event.title} · {event.venue}</Text>
                <PrimaryButton onPress={dismiss} style={styles.action}>Done</PrimaryButton>
              </ScrollView>
            ) : (
              <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.inner}>
                <View style={styles.headerRow}>
                  <View><Text style={styles.eyebrow}>SECURE CHECKOUT SIMULATION</Text><Text style={styles.title}>Complete Your Purchase</Text></View>
                  <Pressable onPress={onClose} style={styles.close}><ArrowLeft size={18} color={colors.secondary} /></Pressable>
                </View>
                <View style={styles.orderRow}><Text style={styles.muted} numberOfLines={1}>{event.title}</Text><Text style={styles.total}>R{event.ticket_price_zar}</Text></View>
                <View style={styles.tabs}>{METHODS.map(({ id, label, icon: Icon }) => (
                  <Pressable key={id} disabled={busy} onPress={() => void switchMethod(id)} style={[styles.tab, method === id && styles.tabActive, busy && styles.tabDisabled]}>
                    <Icon size={16} color={method === id ? colors.orangeSoft : colors.muted} /><Text style={[styles.tabLabel, method === id && styles.tabLabelActive]}>{label}</Text>
                  </Pressable>
                ))}</View>

                {!order ? (
                  <View style={styles.panel}>
                    <Text style={styles.panelTitle}>Ready when you are</Text>
                    <Text style={styles.muted}>We’ll reserve your ticket and open the {method === "x402" ? "Devnet payment" : method.toUpperCase()} simulation.</Text>
                    {method === "card" && <Text style={styles.simulationNotice}>Demo only: card values stay on this screen and are never sent.</Text>}
                    <PrimaryButton onPress={startOrder} disabled={busy} loading={busy} style={styles.action}>Continue · R{event.ticket_price_zar}</PrimaryButton>
                  </View>
                ) : method === "eft" ? (
                  <View style={styles.panel}>
                    <Text style={styles.panelTitle}>EventPass Treasury</Text>
                    <Detail label="Beneficiary" value="EventPass Treasury" /><Detail label="Bank" value="FNB" /><Detail label="Account number" value="62000000000" /><Detail label="Branch code" value="250655" /><Detail label="Reference" value={`EVT-${order.tickets[0].id}`} />
                    <PrimaryButton secondary onPress={copyDetails} style={styles.copy}><Copy size={16} color={colors.secondary} />{copied ? "Copied" : "Copy Details"}</PrimaryButton>
                    <PrimaryButton onPress={confirmSimulation} disabled={busy} loading={busy} style={styles.action}>Simulate EFT Payment Received</PrimaryButton>
                    <Text style={styles.simulationNotice}>Demo simulation only. This does not verify a bank transfer.</Text>
                  </View>
                ) : method === "card" ? (
                  <View style={styles.panel}>
                    <Text style={styles.panelTitle}>Card details · demo only</Text>
                    <View style={styles.cardVisual}><Text style={styles.cardEyebrow}>EVENTPASS</Text><Text style={styles.cardNumber}>4242  4242  4242  4242</Text><Text style={styles.cardExpiry}>12/30  ·  TEST CARD</Text></View>
                    <TextInput editable={false} value="EVENTPASS TESTER" style={styles.input} />
                    <View style={styles.cardFields}><TextInput editable={false} value="12/30" style={[styles.input, styles.smallInput]} /><TextInput editable={false} value="123" style={[styles.input, styles.smallInput]} /></View>
                    <PrimaryButton onPress={confirmSimulation} disabled={busy} loading={busy} style={styles.action}>Pay R{order.total_zar}</PrimaryButton>
                    <Text style={styles.simulationNotice}>Demo only. No card data is collected or transmitted.</Text>
                  </View>
                ) : (
                  <View style={styles.panel}>
                    <Text style={styles.panelTitle}>Payment Request</Text>
                    <Detail label="Amount" value={`${config?.amount_usdc ?? "…"} USDC`} /><Detail label="Network" value="Solana Devnet" /><Detail label="Pay to" value={config?.x402_pay_to_address || "Loading public destination…"} />
                    {transferUrl ? <View style={styles.qrBox}><QRCode value={transferUrl} size={166} backgroundColor="#FFFFFF" color="#111111" /></View> : null}
                    <PrimaryButton onPress={confirmSimulation} disabled={busy || !config} loading={busy} style={styles.action}>Verify x402 Payment</PrimaryButton>
                    <Text style={styles.simulationNotice}>3-second verification simulation. No blockchain settlement occurs.</Text>
                  </View>
                )}
                {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
                {busy && order && <ActivityIndicator style={styles.spinner} color={colors.orange} />}
              </ScrollView>
            )}
          </GlassCard>
        </Animated.View>
      </View>
    </Modal>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return <View style={styles.detail}><Text style={styles.detailLabel}>{label}</Text><Text selectable style={styles.detailValue}>{value}</Text></View>;
}

const styles = StyleSheet.create({
  overlay: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.36)" }, wrap: { width: "100%", maxWidth: 560, alignSelf: "center" },
  sheet: { maxHeight: "94%", borderBottomLeftRadius: 0, borderBottomRightRadius: 0, borderTopLeftRadius: 30, borderTopRightRadius: 30 }, content: { padding: 0 }, handle: { width: 40, height: 4, borderRadius: 4, backgroundColor: "rgba(255,255,255,0.24)", alignSelf: "center", marginTop: 12 },
  inner: { padding: spacing.lg, paddingBottom: 36 }, headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 15 }, eyebrow: { color: colors.orangeSoft, fontSize: 9, letterSpacing: 1.5, fontWeight: "800", marginBottom: 7 }, title: { ...typography.heading, color: colors.text }, close: { width: 40, height: 40, borderRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }, orderRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12, paddingVertical: 16, borderBottomWidth: 1, borderColor: colors.border, marginBottom: 16 }, muted: { ...typography.caption, color: colors.secondary }, total: { color: colors.text, fontWeight: "800", fontSize: 17 },
  tabs: { flexDirection: "row", gap: 8, marginBottom: 17 }, tab: { flex: 1, flexDirection: "row", gap: 7, alignItems: "center", justifyContent: "center", minHeight: 44, borderRadius: 15, borderWidth: 1, borderColor: colors.border, backgroundColor: "rgba(255,255,255,0.035)" }, tabActive: { borderColor: "rgba(255,107,0,0.5)", backgroundColor: "rgba(255,107,0,0.12)" }, tabDisabled: { opacity: 0.7 }, tabLabel: { color: colors.muted, fontWeight: "700", fontSize: 12 }, tabLabelActive: { color: colors.text }, panel: { gap: 14, padding: 17, borderRadius: 22, borderWidth: 1, borderColor: colors.border, backgroundColor: "rgba(0,0,0,0.23)" }, panelTitle: { color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: 2 }, detail: { flexDirection: "row", justifyContent: "space-between", gap: 10 }, detailLabel: { color: colors.muted, fontSize: 12 }, detailValue: { color: colors.text, fontSize: 12, fontWeight: "600", maxWidth: "65%", textAlign: "right" }, action: { marginTop: 5 }, copy: { flexDirection: "row" as const },
  cardVisual: { borderRadius: 18, minHeight: 130, padding: 17, justifyContent: "space-between", backgroundColor: "#24201D", borderWidth: 1, borderColor: "rgba(255,255,255,0.12)" }, cardEyebrow: { color: colors.orangeSoft, fontSize: 10, letterSpacing: 2, fontWeight: "800" }, cardNumber: { color: colors.text, fontSize: 17, fontWeight: "700", letterSpacing: 1 }, cardExpiry: { color: colors.secondary, fontSize: 10, letterSpacing: 1 }, input: { minHeight: 48, borderRadius: 13, borderWidth: 1, borderColor: colors.border, backgroundColor: "rgba(0,0,0,0.35)", paddingHorizontal: 13, color: colors.text, fontSize: 14 }, cardFields: { flexDirection: "row", gap: 10 }, smallInput: { flex: 1 }, simulationNotice: { color: "#F3C27A", fontSize: 11, lineHeight: 16, textAlign: "center" }, error: { color: colors.danger, fontSize: 12, textAlign: "center", marginTop: 12 }, spinner: { marginTop: 12 },
  qrBox: { alignSelf: "center", padding: 14, backgroundColor: "#FFFFFF", borderRadius: 14, marginVertical: 4 }, receipt: { padding: spacing.lg, alignItems: "center", paddingBottom: 35 }, successCircle: { width: 80, height: 80, borderRadius: 40, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(0,230,118,0.12)", marginTop: 20, marginBottom: 18 }, subtitle: { color: colors.secondary, marginTop: 8, fontSize: 13 }, ticketId: { color: colors.text, fontWeight: "700", marginTop: 15 },
});
