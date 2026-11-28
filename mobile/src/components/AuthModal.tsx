import { ArrowLeft, Mail, ShieldCheck, X } from "lucide-react-native";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import Animated, { FadeInDown, FadeInUp } from "react-native-reanimated";
import { colors, radius, spacing, typography } from "../theme/tokens";
import { EventPassUser } from "../auth/AuthContext";
import { GlassCard } from "./GlassCard";
import { PrimaryButton } from "./PrimaryButton";

type AuthModalProps = {
  visible: boolean;
  contextMessage?: string;
  onClose: () => void;
  requestCode: (email: string) => Promise<{ dev_sandbox_otp?: string }>;
  verifyCode: (email: string, code: string) => Promise<EventPassUser>;
  onAuthenticated?: (user: EventPassUser) => Promise<void> | void;
};

export function AuthModal({ visible, contextMessage, onClose, requestCode, verifyCode, onAuthenticated }: AuthModalProps) {
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [digits, setDigits] = useState(["", "", "", "", "", ""]);
  const [cooldown, setCooldown] = useState(0);
  const [sandboxCode, setSandboxCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const refs = useRef<({ focus: () => void } | null)[]>([]);

  useEffect(() => {
    if (cooldown < 1) return undefined;
    const timer = setTimeout(() => setCooldown((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const dispatch = async () => {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const response = await requestCode(email);
      setSandboxCode(response?.dev_sandbox_otp || "");
      setDigits(["", "", "", "", "", ""]);
      setStep("code"); setCooldown(60);
      setTimeout(() => refs.current[0]?.focus(), 180);
    } catch (requestError: any) {
      setError(requestError?.message || "We couldn't send your code. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const updateDigit = (index: number, value: string) => {
    const numeric = value.replace(/\D/g, "");
    if (!numeric) {
      const next = [...digits]; next[index] = ""; setDigits(next); return;
    }
    const next = [...digits];
    [...numeric].slice(0, 6 - index).forEach((digit, offset) => { next[index + offset] = digit; });
    setDigits(next); setError("");
    refs.current[Math.min(index + numeric.length, 5)]?.focus();
  };

  const dismiss = (force = false) => {
    if (busy && !force) return;
    setStep("email"); setDigits(["", "", "", "", "", ""]); setError(""); setCooldown(0); setSandboxCode("");
    onClose();
  };

  const verify = async () => {
    const code = digits.join("");
    if (busy || code.length !== 6) return;
    setBusy(true); setError("");
    try {
      const user = await verifyCode(email, code);
      await onAuthenticated?.(user);
      dismiss(true);
    } catch (verifyError: any) {
      setError(verifyError?.message || "Invalid code. Check the 6 digits and try again.");
      setDigits(["", "", "", "", "", ""]);
      refs.current[0]?.focus();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="fade" statusBarTranslucent onRequestClose={() => dismiss()}>
      <View style={styles.overlay}>
        <Pressable style={StyleSheet.absoluteFill} onPress={() => dismiss()} />
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.avoid}>
          <Animated.View entering={FadeInUp.duration(240)} style={styles.sheetWrap}>
            <GlassCard style={styles.sheet} contentStyle={styles.sheetContent} intensity={70}>
              <View style={styles.topRow}>
                {step === "code" ? (
                  <Pressable onPress={() => { setStep("email"); setError(""); }} style={styles.backButton}>
                    <ArrowLeft size={18} color={colors.secondary} />
                  </Pressable>
                ) : <View style={styles.iconWrap}><Mail size={20} color={colors.orangeSoft} /></View>}
                <Pressable onPress={() => dismiss()} disabled={busy} hitSlop={10} style={styles.closeButton}>
                  <X size={19} color={colors.secondary} />
                </Pressable>
              </View>

              <Animated.View key={step} entering={FadeInDown.duration(220)}>
                <Text style={styles.title}>{step === "email" ? "Welcome to EventPass" : "Check your email"}</Text>
                <Text style={styles.subtitle}>
                  {step === "email"
                    ? "Enter your email to sign in or create an account."
                    : `We sent a 6-digit code to ${email}. Enter it below to securely log in.`}
                </Text>
                {!!contextMessage && step === "email" && <Text style={styles.context}>{contextMessage}</Text>}

                {step === "email" ? (
                  <View style={styles.form}>
                    <View style={styles.emailInputWrap}>
                      <Mail size={18} color={colors.muted} />
                      <TextInput
                        value={email}
                        onChangeText={(value) => { setEmail(value); setError(""); }}
                        keyboardType="email-address"
                        autoCapitalize="none"
                        autoCorrect={false}
                        autoComplete="email"
                        placeholder="you@example.com"
                        placeholderTextColor={colors.muted}
                        style={styles.emailInput}
                      />
                    </View>
                    {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
                    <PrimaryButton onPress={dispatch} disabled={busy || !email.includes("@")}>
                      {busy ? <ActivityIndicator color={colors.text} /> : "Send Login Code"}
                    </PrimaryButton>
                    <View style={styles.privacyRow}>
                      <ShieldCheck size={15} color={colors.emerald} />
                      <Text style={styles.privacy}>Password-free sign-in. Your session is encrypted on this device.</Text>
                    </View>
                  </View>
                ) : (
                  <View style={styles.form}>
                    <View style={styles.codeRow}>
                      {digits.map((digit, index) => (
                        <TextInput
                          key={index}
                          ref={(element) => { refs.current[index] = element; }}
                          value={digit}
                          onChangeText={(value) => updateDigit(index, value)}
                          onKeyPress={({ nativeEvent }) => {
                            if (nativeEvent.key === "Backspace" && !digit && index > 0) refs.current[index - 1]?.focus();
                          }}
                          keyboardType="number-pad"
                          textContentType={index === 0 ? "oneTimeCode" : "none"}
                          autoComplete={index === 0 ? "sms-otp" : "off"}
                          maxLength={index === 0 ? 6 : 1}
                          selectTextOnFocus
                          style={[styles.codeBox, !!digit && styles.codeBoxFilled]}
                          accessibilityLabel={`Verification digit ${index + 1}`}
                        />
                      ))}
                    </View>
                    {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
                    {!!sandboxCode && (
                      <Text style={styles.sandboxCode}>Local development code: <Text style={styles.sandboxDigits}>{sandboxCode}</Text></Text>
                    )}
                    <PrimaryButton onPress={verify} disabled={busy || digits.some((digit) => !digit)}>
                      {busy ? <ActivityIndicator color={colors.text} /> : "Verify & Log In"}
                    </PrimaryButton>
                    <View style={styles.resendRow}>
                      <Text style={styles.resendLabel}>Didn&apos;t receive a code?</Text>
                      {cooldown > 0 ? (
                        <Text style={styles.cooldown}>Resend in {cooldown}s</Text>
                      ) : (
                        <Pressable onPress={dispatch} disabled={busy}>
                          <Text style={styles.resend}>Resend</Text>
                        </Pressable>
                      )}
                    </View>
                  </View>
                )}
              </Animated.View>
            </GlassCard>
          </Animated.View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.68)" },
  avoid: { width: "100%", alignItems: "center" },
  sheetWrap: { width: "100%", maxWidth: 520 },
  sheet: { borderTopLeftRadius: 32, borderTopRightRadius: 32, borderBottomLeftRadius: 0, borderBottomRightRadius: 0, borderBottomWidth: 0 },
  sheetContent: { paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: Platform.OS === "ios" ? 42 : 28 },
  topRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  iconWrap: { width: 44, height: 44, borderRadius: 16, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,107,0,0.14)", borderWidth: 1, borderColor: "rgba(255,107,0,0.3)" },
  backButton: { width: 42, height: 42, borderRadius: 15, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
  closeButton: { width: 38, height: 38, alignItems: "center", justifyContent: "center", marginLeft: "auto" },
  title: { ...typography.heading, fontSize: 25, lineHeight: 31, color: colors.text },
  subtitle: { ...typography.body, color: colors.secondary, marginTop: 8 },
  context: { ...typography.caption, color: colors.orangeSoft, marginTop: 12 },
  form: { marginTop: spacing.lg, gap: 16 },
  emailInputWrap: { minHeight: 56, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: "rgba(0,0,0,0.45)", paddingHorizontal: 16, flexDirection: "row", alignItems: "center", gap: 12 },
  emailInput: { color: colors.text, fontSize: 15, flex: 1, paddingVertical: 14 },
  error: { color: colors.orangeSoft, fontSize: 13, marginTop: -7 },
  privacyRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 7 },
  privacy: { color: colors.muted, fontSize: 11, flexShrink: 1, textAlign: "center" },
  codeRow: { flexDirection: "row", justifyContent: "space-between", gap: 7 },
  codeBox: { flex: 1, height: 54, borderRadius: 14, borderWidth: 1, borderColor: colors.border, backgroundColor: "rgba(0,0,0,0.42)", color: colors.text, fontSize: 21, fontWeight: "700", textAlign: "center", padding: 0 },
  codeBoxFilled: { borderColor: "rgba(255,107,0,0.55)", backgroundColor: "rgba(255,107,0,0.08)" },
  sandboxCode: { textAlign: "center", color: "#F5D28C", borderWidth: 1, borderColor: "rgba(245,210,140,0.15)", backgroundColor: "rgba(245,210,140,0.06)", padding: 11, borderRadius: 12, fontSize: 12 },
  sandboxDigits: { color: "#F5D28C", fontWeight: "800", letterSpacing: 3 },
  resendRow: { flexDirection: "row", justifyContent: "center", gap: 5, alignItems: "center" },
  resendLabel: { color: colors.muted, fontSize: 12 },
  cooldown: { color: colors.muted, fontSize: 12 },
  resend: { color: colors.orangeSoft, fontSize: 12, fontWeight: "700" },
});
