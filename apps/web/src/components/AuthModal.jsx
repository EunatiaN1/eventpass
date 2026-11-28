import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, LoaderCircle, LockKeyhole, Mail, ShieldCheck, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "./Button";

const EMPTY_CODE = ["", "", "", "", "", ""];

export function AuthModal({ isOpen, contextMessage, onClose, onRequestOtp, onVerifyOtp }) {
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [digits, setDigits] = useState(EMPTY_CODE);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [resendSeconds, setResendSeconds] = useState(0);
  const [developmentCode, setDevelopmentCode] = useState("");
  const inputRefs = useRef([]);

  useEffect(() => {
    if (!isOpen) return;
    setStep("email");
    setEmail("");
    setDigits(EMPTY_CODE);
    setError("");
    setBusy(false);
    setResendSeconds(0);
    setDevelopmentCode("");
  }, [isOpen]);

  useEffect(() => {
    if (!resendSeconds) return undefined;
    const timer = window.setTimeout(() => setResendSeconds((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendSeconds]);

  useEffect(() => {
    if (step === "verify") inputRefs.current[0]?.focus();
  }, [step]);

  const sendCode = async (event, resend = false) => {
    event?.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await onRequestOtp(email);
      setStep("verify");
      setDigits(EMPTY_CODE);
      setResendSeconds(60);
      setDevelopmentCode(result?.dev_sandbox_otp || "");
      if (resend) inputRefs.current[0]?.focus();
    } catch (requestError) {
      setError(requestError.message || "We couldn't send your code. Check your email and try again.");
    } finally {
      setBusy(false);
    }
  };

  const updateFromInput = (index, rawValue) => {
    const numbers = rawValue.replace(/\D/g, "");
    if (!numbers) {
      const next = [...digits];
      next[index] = "";
      setDigits(next);
      return;
    }

    const next = [...digits];
    for (let offset = 0; offset < numbers.length && index + offset < 6; offset += 1) {
      next[index + offset] = numbers[offset];
    }
    setDigits(next);
    setError("");
    const focusIndex = Math.min(index + numbers.length, 5);
    inputRefs.current[focusIndex]?.focus();
  };

  const handleKeyDown = (index, event) => {
    if (event.key === "Backspace" && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    } else if (event.key === "ArrowLeft" && index > 0) {
      inputRefs.current[index - 1]?.focus();
    } else if (event.key === "ArrowRight" && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handlePaste = (event) => {
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pasted) return;
    event.preventDefault();
    const next = [...EMPTY_CODE];
    [...pasted].forEach((digit, index) => { next[index] = digit; });
    setDigits(next);
    setError("");
    inputRefs.current[Math.min(pasted.length, 5)]?.focus();
  };

  const verifyCode = async (event) => {
    event.preventDefault();
    if (busy || digits.some((digit) => !digit)) return;
    setBusy(true);
    setError("");
    try {
      await onVerifyOtp(email, digits.join(""));
    } catch (verifyError) {
      setError(verifyError.message || "Invalid code. Check the 6 digits and try again.");
      setDigits(EMPTY_CODE);
      inputRefs.current[0]?.focus();
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={busy ? undefined : onClose}
          className="fixed inset-0 z-[60] flex items-end justify-center bg-black/75 p-0 backdrop-blur-md sm:items-center sm:p-4"
        >
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 330, damping: 28 }}
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="auth-title"
            className="relative w-full max-w-md overflow-hidden rounded-t-[2rem] border border-white/10 bg-[#111111]/95 p-6 shadow-2xl backdrop-blur-2xl sm:rounded-[2rem] sm:p-8"
          >
            <div className="pointer-events-none absolute -top-28 left-1/2 h-48 w-72 -translate-x-1/2 rounded-full bg-[#FF6B00]/20 blur-3xl" />
            <div className="relative mb-7 flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[#FF6B00]/30 bg-[#FF6B00]/15 text-[#FF8A35]">
                  {step === "email" ? <Mail className="h-5 w-5" /> : <LockKeyhole className="h-5 w-5" />}
                </div>
                <div>
                  <h2 id="auth-title" className="text-xl font-semibold tracking-tight text-white">
                    {step === "email" ? "Welcome to EventPass" : "Check your email"}
                  </h2>
                  <p className="mt-1 max-w-[280px] text-xs leading-relaxed text-white/55">
                    {step === "email"
                      ? "Enter your email to sign in or create an account."
                      : `We sent a 6-digit code to ${email}. Enter it below to securely log in.`}
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close sign-in">
                <X className="h-4 w-4" />
              </Button>
            </div>

            <AnimatePresence mode="wait" initial={false}>
              {step === "email" ? (
                <motion.form
                  key="email-step"
                  initial={{ opacity: 0, x: 16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -16 }}
                  transition={{ duration: 0.2 }}
                  onSubmit={sendCode}
                  className="relative space-y-4"
                >
                  {contextMessage && <p className="rounded-xl border border-white/10 bg-white/[.04] px-3.5 py-2.5 text-xs text-white/60">{contextMessage}</p>}
                  <label className="block text-xs font-medium text-white/70" htmlFor="auth-email">Email address</label>
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
                    <input
                      id="auth-email"
                      type="email"
                      autoComplete="email"
                      required
                      autoFocus
                      value={email}
                      onChange={(event) => { setEmail(event.target.value); setError(""); }}
                      placeholder="you@example.com"
                      className="w-full rounded-2xl border border-white/12 bg-black/45 py-3.5 pl-11 pr-4 text-sm text-white outline-none transition-colors placeholder:text-white/30 focus:border-[#FF6B00]/70 focus:ring-2 focus:ring-[#FF6B00]/10"
                    />
                  </div>
                  {error && <p role="alert" className="text-xs font-medium text-[#FF9A62]">{error}</p>}
                  <Button type="submit" variant="primary" fullWidth size="lg" disabled={busy || !email.trim()}>
                    {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                    {busy ? "Sending your code…" : "Send Login Code"}
                  </Button>
                  <p className="flex items-center justify-center gap-1.5 pt-1 text-center text-[11px] text-white/40">
                    <ShieldCheck className="h-3.5 w-3.5 text-[#00E676]" /> Password-free sign-in with a one-time code
                  </p>
                </motion.form>
              ) : (
                <motion.form
                  key="verify-step"
                  initial={{ opacity: 0, x: 16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -16 }}
                  transition={{ duration: 0.2 }}
                  onSubmit={verifyCode}
                  className="relative space-y-5"
                >
                  <button
                    type="button"
                    onClick={() => { setStep("email"); setDigits(EMPTY_CODE); setError(""); }}
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-white/55 transition-colors hover:text-white"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" /> Change email
                  </button>
                  <div className="flex justify-between gap-2" onPaste={handlePaste}>
                    {digits.map((digit, index) => (
                      <input
                        key={index}
                        ref={(element) => { inputRefs.current[index] = element; }}
                        aria-label={`Verification digit ${index + 1}`}
                        type="text"
                        inputMode="numeric"
                        autoComplete={index === 0 ? "one-time-code" : "off"}
                        pattern="[0-9]*"
                        maxLength={index === 0 ? 6 : 1}
                        value={digit}
                        onChange={(event) => updateFromInput(index, event.target.value)}
                        onKeyDown={(event) => handleKeyDown(index, event)}
                        className="h-12 min-w-0 flex-1 rounded-xl border border-white/12 bg-black/45 text-center font-mono text-xl font-semibold text-white outline-none transition-all focus:border-[#FF6B00]/80 focus:ring-2 focus:ring-[#FF6B00]/15"
                      />
                    ))}
                  </div>
                  {error && <p role="alert" className="text-center text-xs font-medium text-[#FF9A62]">{error}</p>}
                  {developmentCode && (
                    <p className="rounded-xl border border-amber-300/15 bg-amber-300/[.06] px-3 py-2 text-center text-xs text-amber-100/80">
                      Local development code: <span className="font-mono font-bold tracking-widest">{developmentCode}</span>
                    </p>
                  )}
                  <Button type="submit" variant="primary" fullWidth size="lg" disabled={busy || digits.some((digit) => !digit)}>
                    {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                    {busy ? "Verifying code…" : "Verify & Log In"}
                  </Button>
                  <div className="text-center text-xs text-white/45">
                    Didn&apos;t receive a code?{" "}
                    {resendSeconds > 0 ? (
                      <span className="text-white/35">Resend in {resendSeconds}s</span>
                    ) : (
                      <button type="button" disabled={busy} onClick={(event) => sendCode(event, true)} className="font-semibold text-[#FF9A62] hover:text-[#FFB177] disabled:opacity-50">
                        Resend
                      </button>
                    )}
                  </div>
                </motion.form>
              )}
            </AnimatePresence>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
