import { CameraView, useCameraPermissions } from "expo-camera";
import { useFocusEffect, useIsFocused } from "expo-router";
import { BlurView } from "expo-blur";
import { Check, CircleAlert, LockKeyhole, ScanLine, ShieldCheck, TicketCheck } from "lucide-react-native";
import { useCallback, useRef, useState } from "react";
import { Pressable, SafeAreaView, ScrollView, StyleSheet, Text, View } from "react-native";
import Animated, { FadeInDown, ZoomIn } from "react-native-reanimated";
import { AuthModal } from "../../src/components/AuthModal";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { useAuth } from "../../src/auth/AuthContext";
import { colors, radius, spacing, typography } from "../../src/theme/tokens";

type EventItem = { id: string; title: string; event_date?: string };
type CheckInResult = {
  accepted: boolean;
  result: string;
  reason: string;
  ticket_id?: string;
  owner_wallet?: string;
  credential_version?: number;
};

export default function GateScreen() {
  const { user, isLoading, api, requestCode, verifyCode } = useAuth();
  const isFocused = useIsFocused();
  const [permission, requestPermission] = useCameraPermissions();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [eventId, setEventId] = useState("");
  const [result, setResult] = useState<CheckInResult | null>(null);
  const [requestError, setRequestError] = useState("");
  const [busy, setBusy] = useState(false);
  const [authDismissed, setAuthDismissed] = useState(false);
  const scannerLocked = useRef(false);

  const loadEvents = useCallback(async () => {
    if (!user) return;
    try {
      const nextEvents = await api<EventItem[]>("/api/events");
      setEvents(nextEvents);
      setEventId((current) => current || nextEvents[0]?.id || "");
      setRequestError("");
    } catch (error: any) {
      setRequestError(error?.message || "Events could not be loaded.");
    }
  }, [api, user]);

  useFocusEffect(useCallback(() => {
    void loadEvents();
    return undefined;
  }, [loadEvents]));

  const submitScan = async ({ data }: { data: string }) => {
    if (scannerLocked.current || busy) return;
    scannerLocked.current = true;
    setBusy(true);
    setResult(null);
    setRequestError("");
    try {
      const response = await api<CheckInResult>("/api/check-in", {
        method: "POST",
        body: JSON.stringify({
          qr_token: data,
          event_id: eventId,
          scanner_id: "GateScanner-Mobile",
        }),
      });
      setResult(response);
    } catch (error: any) {
      setRequestError(error?.message || "The credential could not be checked.");
    } finally {
      setBusy(false);
    }
  };

  const showAuth = !user && !isLoading && !authDismissed;
  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.page}>
        <View style={styles.header}>
          <View style={styles.brandRow}>
            <View style={styles.brandMark}><ScanLine size={18} color={colors.orangeSoft} /></View>
            <View style={styles.brandCopy}>
              <Text style={styles.eyebrow}>EVENTPASS · OPERATIONS</Text>
              <Text style={styles.title}>Gate Scanner</Text>
            </View>
            <View style={styles.liveBadge}><View style={styles.liveDot} /><Text style={styles.liveText}>DEVNET</Text></View>
          </View>
          <Text style={styles.subtitle}>Verify each pass at the door. Every scan is recorded once against the selected event.</Text>
        </View>

        {!user ? (
          <GlassCard style={styles.lockCard}>
            <View style={styles.lockIcon}><LockKeyhole size={21} color={colors.orangeSoft} /></View>
            <Text style={styles.cardTitle}>Staff sign-in required</Text>
            <Text style={styles.bodyText}>Sign in with your EventPass email before scanning admission passes.</Text>
            <PrimaryButton onPress={() => setAuthDismissed(false)}>Sign in with email</PrimaryButton>
          </GlassCard>
        ) : (
          <Animated.View entering={FadeInDown.duration(280)}>
            <View style={styles.sectionHeading}>
              <Text style={styles.sectionLabel}>SCANNING FOR</Text>
              <Text style={styles.operator} numberOfLines={1}>{user.email}</Text>
            </View>

            {events.length > 0 ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.eventChoices}>
                {events.map((event) => {
                  const active = event.id === eventId;
                  return (
                    <Pressable key={event.id} onPress={() => { setEventId(event.id); setResult(null); scannerLocked.current = false; }} style={[styles.eventChip, active && styles.eventChipActive]}>
                      <Text numberOfLines={1} style={[styles.eventChipText, active && styles.eventChipTextActive]}>{event.title}</Text>
                    </Pressable>
                  );
                })}
              </ScrollView>
            ) : (
              <Text style={styles.inlineError}>{requestError || "No events are available for check-in."}</Text>
            )}

            <View style={styles.cameraFrame}>
              <BlurView intensity={50} tint="dark" style={StyleSheet.absoluteFill} />
              {permission?.granted && eventId && isFocused ? (
                <CameraView
                  style={StyleSheet.absoluteFill}
                  facing="back"
                  barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
                  onBarcodeScanned={result || busy ? undefined : submitScan}
                />
              ) : (
                <View style={styles.permissionState}>
                  <View style={styles.permissionIcon}><ScanLine size={25} color={colors.orangeSoft} /></View>
                  <Text style={styles.cardTitle}>{permission?.granted === false ? "Camera access is needed" : "Preparing scanner"}</Text>
                  <Text style={styles.bodyText}>The camera is used only to read an EventPass QR admission credential.</Text>
                  {permission?.granted === false && <PrimaryButton onPress={requestPermission} style={styles.permissionButton}>Enable camera</PrimaryButton>}
                  {!permission && <View style={styles.loading}><Text style={styles.muted}>Checking camera permission…</Text></View>}
                </View>
              )}
              {permission?.granted && !!eventId && !result && (
                <View pointerEvents="none" style={styles.scanOverlay}>
                  <View style={styles.scanCornerTopLeft} /><View style={styles.scanCornerTopRight} />
                  <View style={styles.scanCornerBottomLeft} /><View style={styles.scanCornerBottomRight} />
                  <View style={styles.scanInstruction}><Text style={styles.scanInstructionText}>Align the QR code inside the frame</Text></View>
                </View>
              )}
              {busy && <View style={styles.cameraBusy}><Text style={styles.busyText}>Verifying pass…</Text></View>}
            </View>

            {!!requestError && <Text accessibilityRole="alert" style={styles.inlineError}>{requestError}</Text>}
            {result && (
              <Animated.View entering={ZoomIn.duration(220)}>
                <GlassCard style={[styles.resultCard, result.accepted ? styles.resultAccepted : styles.resultRejected]}>
                  <View style={[styles.resultIcon, result.accepted ? styles.resultIconAccepted : styles.resultIconRejected]}>
                    {result.accepted ? <Check size={23} color={colors.emerald} /> : <CircleAlert size={23} color={colors.danger} />}
                  </View>
                  <View style={styles.resultCopy}>
                    <Text style={[styles.resultTitle, result.accepted ? styles.good : styles.bad]}>{result.accepted ? "Admit guest" : result.result.replaceAll("_", " ")}</Text>
                    <Text style={styles.resultReason}>{result.reason}</Text>
                    {!!result.ticket_id && <Text style={styles.resultTicket}>{result.ticket_id}</Text>}
                  </View>
                  {result.accepted && <TicketCheck size={20} color={colors.emerald} />}
                </GlassCard>
                <PrimaryButton secondary onPress={() => { setResult(null); scannerLocked.current = false; }}>Scan next pass</PrimaryButton>
              </Animated.View>
            )}

            <View style={styles.securityNote}>
              <ShieldCheck size={15} color={colors.emerald} />
              <Text style={styles.securityText}>Signed QR credentials · single-use check-in</Text>
            </View>
          </Animated.View>
        )}
        <View style={{ height: 110 }} />
      </ScrollView>

      <AuthModal
        visible={showAuth}
        contextMessage="Sign in to access the gate scanner."
        onClose={() => setAuthDismissed(true)}
        requestCode={requestCode}
        verifyCode={verifyCode}
        onAuthenticated={() => setAuthDismissed(false)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  page: { paddingHorizontal: spacing.lg, paddingTop: 15 },
  header: { marginBottom: 22 },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 11 },
  brandMark: { width: 43, height: 43, borderRadius: 15, backgroundColor: "rgba(255,107,0,0.12)", borderWidth: 1, borderColor: "rgba(255,107,0,0.28)", alignItems: "center", justifyContent: "center" },
  brandCopy: { flex: 1 },
  eyebrow: { color: colors.orangeSoft, fontSize: 8, fontWeight: "800", letterSpacing: 1.5 },
  title: { ...typography.title, color: colors.text, fontSize: 28, marginTop: 3 },
  liveBadge: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 10, paddingVertical: 7, borderRadius: radius.pill, borderWidth: 1, borderColor: "rgba(0,230,118,0.22)", backgroundColor: "rgba(0,230,118,0.07)" },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.emerald },
  liveText: { color: colors.emerald, fontSize: 8, fontWeight: "800", letterSpacing: 1 },
  subtitle: { color: colors.secondary, fontSize: 13, lineHeight: 19, marginTop: 12, maxWidth: 360 },
  sectionHeading: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 10, marginBottom: 12 },
  sectionLabel: { color: colors.muted, fontSize: 9, letterSpacing: 1.1, fontWeight: "800" },
  operator: { color: colors.secondary, fontSize: 10, flex: 1, textAlign: "right" },
  eventChoices: { gap: 8, paddingBottom: 15 },
  eventChip: { maxWidth: 240, paddingHorizontal: 14, paddingVertical: 10, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface },
  eventChipActive: { borderColor: "rgba(255,107,0,0.5)", backgroundColor: "rgba(255,107,0,0.12)" },
  eventChipText: { color: colors.secondary, fontSize: 11, fontWeight: "600" },
  eventChipTextActive: { color: colors.text },
  cameraFrame: { height: 370, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, backgroundColor: "#151515", overflow: "hidden", marginBottom: 14 },
  permissionState: { flex: 1, alignItems: "center", justifyContent: "center", padding: 26, backgroundColor: "rgba(10,10,10,0.82)" },
  permissionIcon: { width: 58, height: 58, borderRadius: 20, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,107,0,0.12)", marginBottom: 16 },
  cardTitle: { color: colors.text, fontSize: 17, fontWeight: "700", textAlign: "center" },
  bodyText: { color: colors.secondary, fontSize: 12, lineHeight: 18, textAlign: "center", marginTop: 8 },
  permissionButton: { alignSelf: "stretch", marginTop: 18 },
  loading: { marginTop: 16 },
  muted: { color: colors.muted, fontSize: 12 },
  scanOverlay: { ...StyleSheet.absoluteFill, alignItems: "center", justifyContent: "center" },
  scanCornerTopLeft: { position: "absolute", width: 47, height: 47, top: "22%", left: "12%", borderTopWidth: 3, borderLeftWidth: 3, borderColor: colors.orangeSoft, borderTopLeftRadius: 16 },
  scanCornerTopRight: { position: "absolute", width: 47, height: 47, top: "22%", right: "12%", borderTopWidth: 3, borderRightWidth: 3, borderColor: colors.orangeSoft, borderTopRightRadius: 16 },
  scanCornerBottomLeft: { position: "absolute", width: 47, height: 47, bottom: "22%", left: "12%", borderBottomWidth: 3, borderLeftWidth: 3, borderColor: colors.orangeSoft, borderBottomLeftRadius: 16 },
  scanCornerBottomRight: { position: "absolute", width: 47, height: 47, bottom: "22%", right: "12%", borderBottomWidth: 3, borderRightWidth: 3, borderColor: colors.orangeSoft, borderBottomRightRadius: 16 },
  scanInstruction: { position: "absolute", bottom: 20, paddingHorizontal: 14, paddingVertical: 9, borderRadius: radius.pill, backgroundColor: "rgba(0,0,0,0.68)" },
  scanInstructionText: { color: colors.text, fontSize: 10, fontWeight: "600" },
  cameraBusy: { ...StyleSheet.absoluteFill, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(0,0,0,0.62)" },
  busyText: { color: colors.text, fontWeight: "700" },
  inlineError: { color: colors.danger, fontSize: 12, lineHeight: 17, marginBottom: 12 },
  resultCard: { flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 12 },
  resultAccepted: { borderColor: "rgba(0,230,118,0.28)" },
  resultRejected: { borderColor: "rgba(255,120,110,0.26)" },
  resultIcon: { width: 43, height: 43, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  resultIconAccepted: { backgroundColor: "rgba(0,230,118,0.1)" },
  resultIconRejected: { backgroundColor: "rgba(255,120,110,0.1)" },
  resultCopy: { flex: 1 },
  resultTitle: { fontSize: 14, fontWeight: "800", textTransform: "capitalize" },
  good: { color: colors.emerald },
  bad: { color: colors.danger },
  resultReason: { color: colors.secondary, fontSize: 11, lineHeight: 15, marginTop: 3 },
  resultTicket: { color: colors.muted, fontSize: 9, fontFamily: "monospace", marginTop: 4 },
  securityNote: { flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 7, marginTop: 17 },
  securityText: { color: colors.muted, fontSize: 10 },
  lockCard: { padding: 22, alignItems: "center", gap: 12, marginTop: 15 },
  lockIcon: { width: 50, height: 50, borderRadius: 18, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,107,0,0.12)" },
});
