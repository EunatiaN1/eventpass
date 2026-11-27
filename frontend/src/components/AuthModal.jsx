import { AnimatePresence, motion } from "framer-motion";
import { Lock, Mail, Sparkles, Wallet, X } from "lucide-react";
import { useState } from "react";
import { Button } from "./Button";

export function PhantomGhostIcon({ className = "w-4 h-4" }) {
  return (
    <svg viewBox="0 0 128 128" fill="none" className={className} aria-hidden="true">
      <path
        d="M64 14C34.2 14 14 37.8 14 67.6c0 17.5 6.8 34.4 17.7 42.4 5.7 4.2 12.7-1.7 14.3-8.6 1.1-4.8 4.4-5.4 6.5-1.4 3.2 6.1 10.6 7.8 15.6 1.5 3.1-3.9 6.7-3.9 9.8 0 5 6.3 12.4 4.6 15.6-1.5 2.1-4 5.4-3.4 6.5 1.4 1.6 6.9 8.6 12.8 14.3 8.6C107.2 102 114 85.1 114 67.6 114 37.8 93.8 14 64 14Z"
        fill="currentColor"
      />
      <circle cx="49" cy="59" r="7" fill="#0A0A0A" />
      <circle cx="77" cy="59" r="7" fill="#0A0A0A" />
    </svg>
  );
}

const DEMO_WALLETS = [
  {
    label: "Buyer Wallet (Demo)",
    address: "BuyerWalletDemo222222222222222222222222222",
  },
  {
    label: "Seller Wallet (Demo)",
    address: "SellerWalletDemo11111111111111111111111111",
  },
  {
    label: "Organizer Cape Town",
    address: "OrgWalletCapeTown111111111111111111111111",
  },
];

export function AuthModal({ isOpen, contextMessage, onClose, onAuthenticate }) {
  const [mode, setMode] = useState("choice"); // "choice" | "email"
  const [email, setEmail] = useState("");
  const [selectedWallet, setSelectedWallet] = useState(DEMO_WALLETS[0].address);

  const handleWalletConnect = () => {
    onAuthenticate({
      method: "phantom",
      wallet: selectedWallet,
      label: DEMO_WALLETS.find((w) => w.address === selectedWallet)?.label || "Phantom Wallet",
    });
  };

  const handleEmailSubmit = (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    // Derive a deterministic Devnet wallet address for the authenticated email user
    const clean = email.trim().toLowerCase().replace(/[^a-z0-9]/g, "");
    const derivedWallet = `Email${clean.slice(0, 12).padEnd(12, "0")}DevnetPass1111111111`;
    onAuthenticate({
      method: "email",
      email: email.trim(),
      wallet: derivedWallet,
      label: email.trim(),
    });
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 16 }}
            transition={{ type: "spring", stiffness: 360, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-md backdrop-blur-md bg-[#121212]/90 border border-white/10 shadow-2xl rounded-3xl p-8 overflow-hidden"
          >
            {/* Subtle ambient top glow */}
            <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-48 w-72 rounded-full bg-[#FF6B00]/20 blur-3xl" />

            <div className="relative flex items-start justify-between gap-4 mb-6">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#FF6B00]/15 border border-[#FF6B00]/30 text-[#FF6B00]">
                  <Lock className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-xl font-bold tracking-tight text-white">
                    Sign in to finalize your purchase
                  </h2>
                  <p className="text-xs text-white/60 mt-0.5">
                    {contextMessage || "Secure your Metaplex Core pass & verified checkout"}
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close modal">
                <X className="w-4 h-4" />
              </Button>
            </div>

            {mode === "choice" ? (
              <div className="relative space-y-4">
                <div className="rounded-2xl bg-white/5 border border-white/10 p-4 space-y-3">
                  <div className="flex items-center justify-between text-xs text-white/70">
                    <span className="flex items-center gap-1.5 font-medium">
                      <PhantomGhostIcon className="w-4 h-4 text-[#AB9FF2]" />
                      Phantom / Solana Devnet Wallet
                    </span>
                    <span className="text-[#00E676] font-medium">Instant</span>
                  </div>
                  <select
                    value={selectedWallet}
                    onChange={(e) => setSelectedWallet(e.target.value)}
                    className="w-full rounded-xl bg-black/50 border border-white/10 px-3 py-2.5 text-xs text-white/90 focus:outline-none focus:border-[#FF6B00]"
                  >
                    {DEMO_WALLETS.map((w) => (
                      <option key={w.address} value={w.address} className="bg-[#0A0A0A]">
                        {w.label} — {w.address.slice(0, 12)}…
                      </option>
                    ))}
                  </select>
                  <Button variant="primary" fullWidth size="lg" onClick={handleWalletConnect}>
                    <Wallet className="w-4 h-4" />
                    Connect Wallet
                  </Button>
                </div>

                <div className="relative flex items-center py-1">
                  <div className="flex-grow border-t border-white/10" />
                  <span className="mx-3 text-[11px] uppercase tracking-widest text-white/40">
                    or
                  </span>
                  <div className="flex-grow border-t border-white/10" />
                </div>

                <Button
                  variant="glass"
                  fullWidth
                  size="lg"
                  onClick={() => setMode("email")}
                >
                  <Mail className="w-4 h-4 text-white/80" />
                  Sign in with Email
                </Button>

                <p className="text-[11px] text-center text-white/45 pt-1 flex items-center justify-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[#00E676]" />
                  Solana Devnet custody & on-platform ZAR checkout protected
                </p>
              </div>
            ) : (
              <form onSubmit={handleEmailSubmit} className="relative space-y-4">
                <div>
                  <label className="block text-xs font-medium text-white/70 mb-2">
                    Email Address
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@eventpass.co.za"
                    className="w-full rounded-2xl bg-black/50 border border-white/15 px-4 py-3 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-[#FF6B00]"
                  />
                </div>
                <Button type="submit" variant="primary" fullWidth size="lg">
                  <Mail className="w-4 h-4" />
                  Continue with Email
                </Button>
                <Button
                  variant="ghost"
                  fullWidth
                  size="sm"
                  onClick={() => setMode("choice")}
                >
                  ← Back to wallet options
                </Button>
              </form>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
