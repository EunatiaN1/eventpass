import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, CheckCircle2, Copy, ShieldCheck, Sparkles, Ticket, Wallet, X } from "lucide-react";
import { useState } from "react";
import { Button } from "./Button";

export function CampaignView({
  campaigns,
  activeCampaignDetail,
  onOpenCampaign,
  onBackToList,
  onRequireAuth,
  auth,
  api,
  onNotify,
  onRefresh,
}) {
  const [fiatModal, setFiatModal] = useState(null); // { listing }
  const [paymentMethod, setPaymentMethod] = useState("card");
  const [checkoutPending, setCheckoutPending] = useState(null);
  const [x402Modal, setX402Modal] = useState(null); // { listingId, challenge }

  const copyLink = (slug) => {
    const url = `${window.location.origin}/c/${slug}`;
    navigator.clipboard?.writeText(url).catch(() => {});
    onNotify(`Copied shareable link: ${url}`);
  };

  const handleBuyZarClick = (listing) => {
    onRequireAuth("Sign in to finalize your purchase and reserve this pass.", () => {
      setCheckoutPending(null);
      setFiatModal(listing);
    });
  };

  const handleBuyX402Click = async (listing) => {
    onRequireAuth("Sign in to initiate x402 stablecoin settlement on Solana Devnet.", async () => {
      const resp = await fetch(`/api/listings/${listing.id}/purchase-x402`);
      setX402Modal({
        listingId: listing.id,
        status: resp.status,
        headers: {
          Network: resp.headers.get("Network"),
          Asset: resp.headers.get("Asset"),
          payTo: resp.headers.get("payTo"),
          Amount: resp.headers.get("Amount"),
        },
      });
    });
  };

  const startFiatCheckout = async () => {
    try {
      const res = await api("/api/checkout/initiate", {
        method: "POST",
        body: JSON.stringify({
          listing_id: fiatModal.id,
          buyer_wallet: auth.wallet,
          payment_method: paymentMethod,
        }),
      });
      setCheckoutPending(res);
      onRefresh();
    } catch (err) {
      onNotify(err.message, true);
    }
  };

  const confirmDemoCheckout = async (outcome) => {
    try {
      const res = await api("/api/checkout/confirm-demo", {
        method: "POST",
        body: JSON.stringify({
          payment_reference: checkoutPending.payment_reference,
          simulate_outcome: outcome,
        }),
      });
      setFiatModal(null);
      setCheckoutPending(null);
      onNotify(res.message || res.status, outcome === "failed");
      onRefresh();
    } catch (err) {
      onNotify(err.message, true);
    }
  };

  const submitX402Signature = async () => {
    try {
      const res = await api(`/api/listings/${x402Modal.listingId}/purchase-x402`, {
        headers: { "PAYMENT-SIGNATURE": `devnet-usdc-sig-${Date.now()}` },
      });
      setX402Modal(null);
      onNotify(`x402 settled (${res.amount_usdc_micro} USDC micro-units). Pass transferred!`);
      onRefresh();
    } catch (err) {
      onNotify(err.message, true);
    }
  };

  if (!activeCampaignDetail) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Social Resale Campaigns
          </h1>
          <p className="text-sm text-white/70 mt-2">
            One live authoritative inventory shared across EventPass and external social links.
            5% platform fee, 95% seller proceeds.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {campaigns.map((c, idx) => (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.06 }}
              whileHover={{ y: -4 }}
              className="backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl p-6 flex flex-col justify-between gap-5"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-lg font-bold tracking-tight text-white">{c.title}</h2>
                  <span
                    className={`px-3 py-1 rounded-full text-[11px] font-semibold border ${
                      c.status === "active"
                        ? "bg-[#00E676]/15 text-[#00E676] border-[#00E676]/30"
                        : "bg-white/10 text-white/70 border-white/15"
                    }`}
                  >
                    {c.status}
                  </span>
                </div>
                <div className="text-xs text-white/70 space-y-1.5">
                  <div>
                    <strong className="text-white/90">Event:</strong> {c.event_title}
                  </div>
                  <div>
                    <strong className="text-white/90">Link:</strong>{" "}
                    <code className="text-[#FF6B00]">{c.share_path}</code>
                  </div>
                  <div>
                    <strong className="text-white/90">Availability:</strong> {c.available_count}{" "}
                    available / {c.total_count} total ({c.sold_count} sold)
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2.5">
                <Button variant="primary" size="sm" onClick={() => onOpenCampaign(c.slug)}>
                  Open Campaign
                </Button>
                <Button variant="glass" size="sm" onClick={() => copyLink(c.slug)}>
                  <Copy className="w-3.5 h-3.5" />
                  Copy Link
                </Button>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    );
  }

  const { campaign, event, available_count, total_count, listings } = activeCampaignDetail;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <Button variant="glass" size="sm" onClick={onBackToList}>
            <ArrowLeft className="w-3.5 h-3.5" />
            All Campaigns
          </Button>
          <h1 className="text-3xl font-bold tracking-tight text-white pt-1">{campaign.title}</h1>
          <p className="text-sm text-white/70">
            {event.title} · {event.venue} ·{" "}
            {new Date(event.event_date).toLocaleString("en-ZA", {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="px-3.5 py-1.5 rounded-full text-xs font-semibold bg-[#00E676]/15 text-[#00E676] border border-[#00E676]/30">
            {campaign.status}
          </span>
          <Button variant="glass" size="md" onClick={() => copyLink(campaign.slug)}>
            <Copy className="w-4 h-4" />
            Share / Copy Link
          </Button>
        </div>
      </div>

      {/* Live Inventory Banner */}
      <div className="backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl p-6 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="text-base font-bold tracking-tight text-white">
            Live Campaign Inventory: {available_count} of {total_count} passes available
          </div>
          <p className="text-xs text-white/70">
            Organizer Resale Cap: R{event.max_resale_price_zar || "—"} · Buying 1 pass keeps
            remaining passes live. QR credentials stay hidden until verified settlement.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-[#00E676]/10 text-[#00E676] border border-[#00E676]/30">
            <ShieldCheck className="w-3.5 h-3.5" />
            On-Platform Checkout Only
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-white/5 text-white/80 border border-white/15">
            5% Fee / 95% Seller Proceeds
          </span>
        </div>
      </div>

      {/* Individual Ticket Listings */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {listings.map((l, idx) => (
          <motion.div
            key={l.id}
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.06 }}
            whileHover={{ y: -4 }}
            className="backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl p-6 flex flex-col justify-between gap-5"
          >
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2 text-base font-bold tracking-tight text-white">
                  <Ticket className="w-4 h-4 text-[#FF6B00]" />
                  {l.ticket_id}
                </span>
                <span
                  className={`px-3 py-1 rounded-full text-[11px] font-semibold border ${
                    l.status === "active"
                      ? "bg-[#00E676]/15 text-[#00E676] border-[#00E676]/30"
                      : "bg-white/10 text-white/60 border-white/15"
                  }`}
                >
                  {l.status}
                </span>
              </div>

              <div className="text-xs text-white/70 space-y-1.5">
                <div>Tier: {l.tier}</div>
                <div>
                  Original: R{l.original_price_zar} →{" "}
                  <strong className="text-white text-sm">Resale: R{l.asking_price_zar}</strong>
                </div>
                <div>
                  Fee disclosure: R{l.marketplace_fee_zar} (5%) · R{l.seller_proceeds_zar} to
                  seller
                </div>
              </div>
              <div className="rounded-2xl bg-black/40 border border-white/5 px-3 py-2 text-[11px] font-mono text-white/55 truncate">
                {l.asset_address}
              </div>
            </div>

            {l.status === "active" ? (
              <div className="flex flex-col gap-2.5">
                <Button variant="primary" fullWidth onClick={() => handleBuyZarClick(l)}>
                  Buy Pass · R{l.asking_price_zar}
                </Button>
                <Button variant="glass" fullWidth onClick={() => handleBuyX402Click(l)}>
                  <Sparkles className="w-3.5 h-3.5 text-[#00E676]" />
                  Pay via x402 (Solana USDC)
                </Button>
              </div>
            ) : (
              <div className="text-xs text-white/50 text-center py-2">
                Unavailable ({l.status})
              </div>
            )}
          </motion.div>
        ))}
      </div>

      {/* ZAR Unified Checkout Modal */}
      <AnimatePresence>
        {fiatModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setFiatModal(null)}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 16 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-lg backdrop-blur-md bg-[#121212]/95 border border-white/10 shadow-2xl rounded-3xl p-8 space-y-5"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-xl font-bold tracking-tight text-white">
                    Unified EventPass Checkout
                  </h2>
                  <p className="text-xs text-white/70 mt-1">
                    Resale price R{fiatModal.asking_price_zar} ZAR (R{fiatModal.marketplace_fee_zar}{" "}
                    fee included).
                  </p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setFiatModal(null)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>

              {!checkoutPending ? (
                <>
                  <div>
                    <label className="block text-xs font-medium text-white/70 mb-2">
                      Select On-Platform Payment Method
                    </label>
                    <select
                      value={paymentMethod}
                      onChange={(e) => setPaymentMethod(e.target.value)}
                      className="w-full rounded-2xl bg-black/50 border border-white/15 px-4 py-3 text-sm text-white focus:outline-none focus:border-[#FF6B00]"
                    >
                      <option value="card">Bank Card (Paystack)</option>
                      <option value="payfast">PayFast</option>
                      <option value="eft">EFT (Unique Reference & Bank Verification)</option>
                      <option value="payflex">Payflex (4x Interest-Free Instalments)</option>
                      <option value="eventpass_wallet">EventPass Wallet</option>
                    </select>
                  </div>
                  <Button variant="primary" fullWidth size="lg" onClick={startFiatCheckout}>
                    Reserve Pass & Initiate Payment
                  </Button>
                </>
              ) : (
                <div className="space-y-4">
                  <div className="rounded-2xl bg-white/5 border border-white/10 p-4 text-xs space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[#00E676] font-semibold">Reservation Locked</span>
                      <code className="text-white/80">{checkoutPending.payment_reference}</code>
                    </div>
                    <p className="text-white/60">
                      Ownership never transfers before server-to-server payment verification.
                    </p>
                    {checkoutPending.instructions?.eft_bank_details && (
                      <pre className="rounded-xl bg-black/60 p-3 text-[11px] text-white/80 overflow-x-auto">
                        {JSON.stringify(checkoutPending.instructions.eft_bank_details, null, 2)}
                      </pre>
                    )}
                    {checkoutPending.instructions?.payflex_schedule && (
                      <pre className="rounded-xl bg-black/60 p-3 text-[11px] text-white/80 overflow-x-auto">
                        {JSON.stringify(checkoutPending.instructions.payflex_schedule, null, 2)}
                      </pre>
                    )}
                  </div>
                  <div className="flex gap-3">
                    <Button
                      variant="emerald"
                      fullWidth
                      onClick={() => confirmDemoCheckout("success")}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      Simulate Verified Settlement
                    </Button>
                    <Button
                      variant="danger"
                      fullWidth
                      onClick={() => confirmDemoCheckout("failed")}
                    >
                      Simulate Failed
                    </Button>
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* x402 Modal */}
      <AnimatePresence>
        {x402Modal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setX402Modal(null)}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 16 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-lg backdrop-blur-md bg-[#121212]/95 border border-white/10 shadow-2xl rounded-3xl p-8 space-y-5"
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                    HTTP {x402Modal.status} Payment Required
                  </span>
                  <h2 className="text-xl font-bold tracking-tight text-white mt-2">
                    x402 Solana Devnet Challenge
                  </h2>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setX402Modal(null)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <pre className="rounded-2xl bg-black/60 border border-white/10 p-4 text-xs text-[#00E676] overflow-x-auto">
                {JSON.stringify(x402Modal.headers, null, 2)}
              </pre>
              <Button variant="primary" fullWidth size="lg" onClick={submitX402Signature}>
                <Wallet className="w-4 h-4" />
                Sign & Submit PAYMENT-SIGNATURE
              </Button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
