import { AnimatePresence, motion } from "framer-motion";
import { CreditCard, LoaderCircle, X, Zap } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useState } from "react";
import { Button } from "./Button";
import { QrCodeMatrix } from "./QrCodeMatrix";

const METHODS = [
  { id: "eft", label: "EFT" },
  { id: "card", label: "Card" },
  { id: "x402", label: "x402 · Crypto" },
];

function formatZar(value) {
  return `R${Number(value || 0).toLocaleString("en-ZA")}`;
}

export function CheckoutModal({ event, quantity, order, api, onConfirm, onCancel, onClose }) {
  const [method, setMethod] = useState("eft");
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [error, setError] = useState("");
  const [usdcAmount, setUsdcAmount] = useState("0.00");
  const reference = order?.order_reference || "demo";
  const ticket = order?.tickets?.[0];

  useEffect(() => {
    if (!order || method !== "x402") return;
    let cancelled = false;
    api(`/api/checkout/config?amount_zar=${encodeURIComponent(order.total_zar)}`)
      .then((config) => {
        if (!cancelled) {
          setUsdcAmount(config.amount_usdc || "0.00");
        }
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [api, method, order]);

  const simulatePayment = async () => {
    if (!ticket) return;
    setBusy(true);
    setError("");
    try {
      const delay = method === "card" ? 2000 : method === "x402" ? 3000 : 0;
      await onConfirm(ticket.id, method, delay);
      setReceipt({ method, ticket });
    } catch (err) {
      setError(err.message || "The simulated checkout could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  const demoReference = `EVENTPASS-DEMO:${reference}`;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={receipt || busy ? undefined : onCancel}
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/75 backdrop-blur-sm p-0 sm:p-4"
      >
        <motion.section
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 24, scale: 0.98 }}
          transition={{ type: "spring", stiffness: 340, damping: 30 }}
          onClick={(eventClick) => eventClick.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-labelledby="checkout-title"
          className="relative max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-t-[2rem] sm:rounded-[2rem] border border-white/10 bg-[#111111]/95 p-6 shadow-2xl backdrop-blur-2xl sm:p-8"
        >
          <div className="pointer-events-none absolute -top-28 left-1/2 h-48 w-72 -translate-x-1/2 rounded-full bg-[#FF6B00]/15 blur-3xl" />
          {receipt ? (
            <div className="relative space-y-5 text-center">
              <div className="flex justify-end">
                <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close receipt">
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <motion.div
                initial={{ scale: 0.4, opacity: 0, rotate: -18 }}
                animate={{ scale: 1, opacity: 1, rotate: 0 }}
                transition={{ type: "spring", stiffness: 220, damping: 14 }}
                className="mx-auto flex h-16 w-16 items-center justify-center rounded-full border border-[#00E676]/40 bg-[#00E676]/15 text-[#00E676] shadow-[0_0_45px_-8px_rgba(0,230,118,.65)]"
              >
                <motion.svg viewBox="0 0 24 24" className="h-9 w-9" fill="none">
                  <motion.path
                    d="m5 12.5 4.5 4.5L19 7"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ duration: 0.45, delay: 0.12 }}
                  />
                </motion.svg>
              </motion.div>
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-[.24em] text-[#00E676]">
                  Simulation receipt
                </span>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">
                  Demo checkout complete · {receipt.method === "x402" ? "x402" : receipt.method.toUpperCase()}
                </h2>
                <p className="mt-2 text-sm text-white/60">{event.title}</p>
              </div>
              <div className="inline-flex rounded-2xl bg-white p-3 shadow-xl">
                <QrCodeMatrix value={receipt.ticket.qr_token} size={9} />
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[.04] p-4 text-left">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-white/55">Order reference</span>
                  <span className="font-mono text-xs text-white/85">{order.order_reference}</span>
                </div>
                <div className="mt-2 flex items-center justify-between text-sm">
                  <span className="text-white/55">Total</span>
                  <span className="font-semibold text-white">{formatZar(order.total_zar)}</span>
                </div>
              </div>
              <p className="rounded-xl border border-amber-300/15 bg-amber-300/[.06] px-3 py-2 text-xs text-amber-100/75">
                Test simulation only. No money was moved and no blockchain payment was verified.
              </p>
              <Button variant="primary" size="lg" fullWidth onClick={onClose}>
                Done
              </Button>
            </div>
          ) : (
            <div className="relative space-y-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[.24em] text-[#FF8A35]">
                    Simulated checkout · Demo only
                  </p>
                  <h2 id="checkout-title" className="mt-1 text-2xl font-semibold tracking-tight text-white">
                    Complete Your Purchase
                  </h2>
                  <p className="mt-1 text-sm text-white/55">{event.title} · {quantity} ticket{quantity > 1 ? "s" : ""}</p>
                </div>
                <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy} aria-label="Close checkout">
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="flex rounded-2xl border border-white/10 bg-black/35 p-1">
                {METHODS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    disabled={busy}
                    onClick={() => { setMethod(item.id); setError(""); }}
                    className={`flex-1 rounded-xl px-2 py-2.5 text-xs font-semibold transition-colors ${
                      method === item.id
                        ? "bg-white/10 text-white shadow-inner"
                        : "text-white/45 hover:text-white/75"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {method === "eft" && (
                <div className="space-y-4">
                  <div className="rounded-2xl border border-white/10 bg-white/[.045] p-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-white/50">EFT demo</p>
                    <p className="mt-2 text-sm text-white/75">No bank transfer is requested for this demo.</p>
                  </div>
                  <Button variant="primary" size="lg" fullWidth disabled={busy || !ticket} onClick={simulatePayment}>
                    {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                    Complete EFT demo · {formatZar(order?.total_zar)}
                  </Button>
                </div>
              )}

              {method === "card" && (
                <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); simulatePayment(); }}>
                  <div className="rounded-2xl border border-white/10 bg-white/[.045] p-4 text-xs text-white/55">
                    Demo card fields stay in this browser and are never sent to the server.
                  </div>
                  <label className="block text-xs text-white/60">Card number
                    <input value="4242 4242 4242 4242" readOnly autoComplete="off" inputMode="numeric" className="mt-1.5 w-full rounded-xl border border-white/10 bg-black/45 px-3.5 py-3 text-sm text-white/75 outline-none" />
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="block text-xs text-white/60">Expiry
                      <input value="12/30" readOnly autoComplete="off" className="mt-1.5 w-full rounded-xl border border-white/10 bg-black/45 px-3.5 py-3 text-sm text-white/75 outline-none" />
                    </label>
                    <label className="block text-xs text-white/60">CVV
                      <input value="123" readOnly autoComplete="off" inputMode="numeric" className="mt-1.5 w-full rounded-xl border border-white/10 bg-black/45 px-3.5 py-3 text-sm text-white/75 outline-none" />
                    </label>
                  </div>
                  <label className="block text-xs text-white/60">Name on card
                    <input value="EventPass Test User" readOnly autoComplete="off" className="mt-1.5 w-full rounded-xl border border-white/10 bg-black/45 px-3.5 py-3 text-sm text-white/75 outline-none" />
                  </label>
                  <Button type="submit" variant="primary" size="lg" fullWidth disabled={busy || !ticket}>
                    {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <CreditCard className="h-4 w-4" />}
                    {busy ? "Simulating card authorization…" : `Pay ${formatZar(order?.total_zar)}`}
                  </Button>
                </form>
              )}

              {method === "x402" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[.045] p-4">
                    <div>
                      <p className="text-[10px] uppercase tracking-widest text-white/45">Demo amount only</p>
                      <p className="mt-1 text-xl font-semibold text-white">${usdcAmount} <span className="text-xs text-white/45">USDC</span></p>
                      <p className="mt-1 text-xs text-white/50">No network payment</p>
                    </div>
                    <div className="rounded-xl bg-white p-2"><QRCodeSVG value={demoReference} size={112} level="M" /></div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-black/30 p-3">
                    <p className="text-[10px] uppercase tracking-wider text-white/40">Demo reference</p>
                    <p className="mt-1 break-all font-mono text-[11px] text-white/75">{reference}</p>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-white/45"><Zap className="h-3.5 w-3.5 text-[#00E676]" /> The QR code is a demo reference; it will not open a wallet.</div>
                  <Button variant="primary" size="lg" fullWidth disabled={busy || !ticket} onClick={simulatePayment}>
                    {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                    {busy ? "Completing demo…" : "Complete x402 demo"}
                  </Button>
                </div>
              )}

              {error && <p role="alert" className="rounded-xl border border-red-400/20 bg-red-400/10 px-3 py-2 text-xs text-red-200">{error}</p>}
              <p className="text-center text-[10px] leading-relaxed text-white/35">Demo only. No money moves, no wallet opens, and no blockchain transaction is submitted or verified.</p>
              {!ticket && <div className="flex items-center justify-center gap-2 text-xs text-white/50"><LoaderCircle className="h-3.5 w-3.5 animate-spin" /> Preparing your test order…</div>}
            </div>
          )}
        </motion.section>
      </motion.div>
    </AnimatePresence>
  );
}
