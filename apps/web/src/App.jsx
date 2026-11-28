import { AnimatePresence, motion } from "framer-motion";
import { Lock, Share2, Sparkles, Ticket, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AuthModal } from "./components/AuthModal";
import { Button } from "./components/Button";
import { CampaignView } from "./components/CampaignView";
import { CheckoutModal } from "./components/CheckoutModal";
import { CheckInScannerView } from "./components/CheckInScannerView";
import { EventCard } from "./components/EventCard";
import { Layout } from "./components/Layout";
import { OrganizerLedgerView } from "./components/OrganizerLedgerView";
import { QrCodeMatrix } from "./components/QrCodeMatrix";
import { TicketPassCard } from "./components/TicketPassCard";
import { useAuth } from "./contexts/AuthContext";
import { apiUrl } from "./lib/apiUrl";

export default function App() {
  const [activeTab, setActiveTab] = useState(() => {
    const match = window.location.pathname.match(/^\/c\/([a-zA-Z0-9_-]+)$/);
    return match ? "campaigns" : "events";
  });
  const [activeCampaignSlug, setActiveCampaignSlug] = useState(() => {
    const match = window.location.pathname.match(/^\/c\/([a-zA-Z0-9_-]+)$/);
    return match ? match[1] : null;
  });

  const { auth, requestCode, verifyCode, signOut } = useAuth();
  const [authModal, setAuthModal] = useState({
    isOpen: false,
    contextMessage: "",
    pendingAction: null,
  });

  const [events, setEvents] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [campaignDetail, setCampaignDetail] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [ledger, setLedger] = useState(null);

  const [selectedForResale, setSelectedForResale] = useState(new Set());
  const [qrModal, setQrModal] = useState(null);
  const [campaignModalOpen, setCampaignModalOpen] = useState(false);
  const [campaignTitle, setCampaignTitle] = useState("Friends Can't Make It — Verified Resale");
  const [campaignPrice, setCampaignPrice] = useState(550);
  const [scannerPrefill, setScannerPrefill] = useState(null);
  const [toast, setToast] = useState(null);
  const [checkout, setCheckout] = useState(null);
  const [checkoutComplete, setCheckoutComplete] = useState(false);

  const notify = useCallback((message, isError = false) => {
    setToast({ message, isError });
    clearTimeout(notify._t);
    notify._t = setTimeout(() => setToast(null), 4500);
  }, []);

  const api = useCallback(async (path, options = {}) => {
    const res = await fetch(apiUrl(path), {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!res.ok) {
      throw new Error(data?.detail || `HTTP ${res.status}`);
    }
    return data;
  }, []);

  const loadData = useCallback(async () => {
    try {
      if (activeTab === "events") {
        setEvents(await api("/api/events"));
      } else if (activeTab === "campaigns") {
        setCampaigns(await api("/api/campaigns"));
        if (activeCampaignSlug) {
          setCampaignDetail(await api(`/api/campaigns/${activeCampaignSlug}`));
        } else {
          setCampaignDetail(null);
        }
      } else if (activeTab === "tickets") {
        if (auth.isAuthenticated && auth.wallet) {
          setTickets(
            await api(`/api/tickets?owner_wallet=${encodeURIComponent(auth.wallet)}`)
          );
        }
      } else if (activeTab === "organizer") {
        const [ev, ldg] = await Promise.all([api("/api/events"), api("/api/ledger")]);
        setEvents(ev);
        setLedger(ldg);
      } else if (activeTab === "checkin") {
        setEvents(await api("/api/events"));
      }
    } catch (err) {
      notify(err.message, true);
    }
  }, [activeTab, activeCampaignSlug, auth.isAuthenticated, auth.wallet, api, notify]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const openAuthModal = (contextMessage = "", pendingAction = null) => {
    setAuthModal({ isOpen: true, contextMessage, pendingAction });
  };

  const requireAuth = (contextMessage, action) => {
    if (auth.isAuthenticated && auth.wallet) {
      action(auth);
      return;
    }
    openAuthModal(contextMessage, action);
  };

  const handleVerifyOtp = async (email, code) => {
    const nextAuth = await verifyCode(email, code);
    const pending = authModal.pendingAction;
    setAuthModal({ isOpen: false, contextMessage: "", pendingAction: null });
    notify(`Signed in as ${nextAuth.email}`);
    if (pending) await pending(nextAuth);
    return nextAuth;
  };

  const handleSignOut = async () => {
    try {
      await signOut();
    } catch (err) {
      notify(err.message || "Unable to sign out.", true);
    }
    setTickets([]);
    setSelectedForResale(new Set());
    notify("Signed out securely.");
  };

  const selectTab = (tab, slug = null) => {
    setActiveTab(tab);
    setActiveCampaignSlug(slug);
    if (tab === "campaigns" && slug) {
      window.history.replaceState(null, "", `/c/${slug}`);
    } else if (window.location.pathname.startsWith("/c/")) {
      window.history.replaceState(null, "", "/");
    }
    if (tab === "tickets" && !auth.isAuthenticated) {
      openAuthModal("Sign in to unlock your digital passes, QR credentials, and resale options.");
    }
  };

  const handleBuyPrimary = (event, quantity) => {
    requireAuth(
      `Sign in to finalize your purchase of ${quantity} ticket(s) for ${event.title}.`,
      async (currentAuth) => {
        try {
          const order = await api(`/api/events/${event.id}/purchase-primary`, {
            method: "POST",
            body: JSON.stringify({
              buyer_wallet: currentAuth.wallet,
              quantity,
              tier: "General Admission",
              payment_method: "eft",
            }),
          });
          setCheckoutComplete(false);
          setCheckout({ event, quantity, order });
        } catch (err) {
          notify(err.message, true);
        }
      }
    );
  };

  const handleConfirmMockPayment = async (ticketId, paymentMethod, delayMs) => {
    if (delayMs) await new Promise((resolve) => setTimeout(resolve, delayMs));
    await api(`/api/checkout/${encodeURIComponent(checkout.order.order_reference)}/method?payment_method=${paymentMethod}`, {
      method: "PATCH",
    });
    const result = await api("/api/webhooks/mock-success", {
      method: "POST",
      body: JSON.stringify({ ticket_id: ticketId, payment_method: paymentMethod }),
    });
    setCheckoutComplete(true);
    return result;
  };

  const closeCheckout = () => {
    const completed = checkoutComplete;
    setCheckout(null);
    setCheckoutComplete(false);
    if (completed) selectTab("tickets");
  };

  const handleViewQr = async (ticketId) => {
    try {
      const cred = await api(`/api/tickets/${ticketId}/credential`);
      setQrModal(cred);
    } catch (err) {
      notify(err.message, true);
    }
  };

  const handleRefund = async (ticketId, amount) => {
    if (
      !window.confirm(
        `Claim 75% unsold-ticket refund of R${amount}? This revokes the ticket QR permanently.`
      )
    ) {
      return;
    }
    try {
      const res = await api(`/api/tickets/${ticketId}/refund`, {
        method: "POST",
        body: JSON.stringify({ requester_wallet: auth.wallet }),
      });
      notify(res.message);
      loadData();
    } catch (err) {
      notify(err.message, true);
    }
  };

  const handleCancelListing = async (listingId) => {
    try {
      await api(`/api/listings/${listingId}/cancel`, {
        method: "POST",
        body: JSON.stringify({ seller_wallet: auth.wallet }),
      });
      notify("Resale listing cancelled.");
      loadData();
    } catch (err) {
      notify(err.message, true);
    }
  };

  const handleOpenCreateCampaign = () => {
    requireAuth("Sign in to list tickets on a shareable social resale campaign.", () => {
      const selected = tickets.filter((t) => selectedForResale.has(t.id));
      if (!selected.length) {
        notify("Select at least one eligible ticket first.", true);
        return;
      }
      setCampaignPrice(selected[0].max_resale_price_zar || selected[0].original_price_zar);
      setCampaignModalOpen(true);
    });
  };

  const handleCreateCampaignSubmit = async (e) => {
    e.preventDefault();
    try {
      const items = Array.from(selectedForResale).map((ticket_id) => ({
        ticket_id,
        asking_price_zar: Number(campaignPrice),
      }));
      const res = await api("/api/campaigns", {
        method: "POST",
        body: JSON.stringify({
          seller_wallet: auth.wallet,
          title: campaignTitle,
          items,
        }),
      });
      setSelectedForResale(new Set());
      setCampaignModalOpen(false);
      notify(`Social resale campaign published at ${res.share_path}`);
      selectTab("campaigns", res.slug);
    } catch (err) {
      notify(err.message, true);
    }
  };

  const handleToggleResale = async (eventId, enabled) => {
    try {
      await api(`/api/events/${eventId}/resale-config`, {
        method: "PATCH",
        body: JSON.stringify({ resale_enabled: enabled }),
      });
      notify(`Resale ${enabled ? "enabled" : "paused"} for event.`);
      loadData();
    } catch (err) {
      notify(err.message, true);
    }
  };

  const handleGateScan = async (payload) => {
    try {
      return await api("/api/check-in", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    } catch (err) {
      notify(err.message, true);
      return null;
    }
  };

  return (
    <Layout
      activeTab={activeTab}
      onSelectTab={(tab) => selectTab(tab, null)}
      auth={auth}
      onOpenAuth={() => openAuthModal()}
      onSignOut={handleSignOut}
      toast={toast}
    >
      {/* 1. Events & Buy Tab */}
      {activeTab === "events" && (
        <div className="space-y-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-[#FF6B00]">
                <Sparkles className="w-3.5 h-3.5" />
                Verified Primary & Social Resale
              </span>
              <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mt-1.5">
                Curated Live Experiences
              </h1>
              <p className="text-sm text-white/70 mt-2 max-w-2xl">
                Every pass is minted individually on Solana Devnet with organizer price-cap
                protection, 75% unsold-ticket refund security, and instant QR rotation on resale.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {events.map((ev, idx) => (
              <EventCard key={ev.id} event={ev} index={idx} onBuy={handleBuyPrimary} />
            ))}
          </div>
        </div>
      )}

      {/* 2. Social Resale Tab */}
      {activeTab === "campaigns" && (
        <CampaignView
          campaigns={campaigns}
          activeCampaignDetail={campaignDetail}
          onOpenCampaign={(slug) => selectTab("campaigns", slug)}
          onBackToList={() => selectTab("campaigns", null)}
          onRequireAuth={requireAuth}
          auth={auth}
          api={api}
          onNotify={notify}
          onRefresh={loadData}
        />
      )}

      {/* 3. My Tickets Tab (Auth Gated) */}
      {activeTab === "tickets" && (
        <>
          {!auth.isAuthenticated ? (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="mx-auto max-w-lg backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl p-8 text-center space-y-5 mt-8"
            >
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#FF6B00]/15 border border-[#FF6B00]/30 text-[#FF6B00]">
                <Lock className="w-7 h-7" />
              </div>
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-white">
                  Your Digital Passes Are Protected
                </h2>
                <p className="text-sm text-white/70 mt-2">
                  Sign in with your email to view your EventPass tickets, QR entry credentials, and social resale tools.
                </p>
              </div>
              <Button
                variant="primary"
                size="lg"
                fullWidth
                onClick={() => openAuthModal("Sign in to unlock My Tickets and digital entry passes.")}
              >
                Sign In with Email
              </Button>
            </motion.div>
          ) : (
            <div className="space-y-8">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <h1 className="text-3xl font-bold tracking-tight text-white">My Digital Passes</h1>
                  <p className="text-sm text-white/70 mt-2">
                    Signed in as <code className="text-[#00E676]">{auth.email}</code>
                  </p>
                </div>
                {tickets.some((t) => ["issued", "sold"].includes(t.status) && t.resale_enabled) && (
                  <Button variant="primary" size="lg" onClick={handleOpenCreateCampaign}>
                    <Share2 className="w-4 h-4" />
                    List for Resale ({selectedForResale.size} selected)
                  </Button>
                )}
              </div>

              {tickets.length === 0 ? (
                <div className="backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl p-8 text-center space-y-4">
                  <Ticket className="w-8 h-8 text-white/40 mx-auto" />
                  <p className="text-sm text-white/70">
                    No passes held by this account yet. Grab tickets from Events & Buy to add a pass to your account.
                  </p>
                  <Button variant="primary" onClick={() => selectTab("events")}>
                    Browse Events
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {tickets.map((ticket, idx) => (
                    <TicketPassCard
                      key={ticket.id}
                      ticket={ticket}
                      index={idx}
                      isSelected={selectedForResale.has(ticket.id)}
                      onToggleSelect={(id, checked) => {
                        const next = new Set(selectedForResale);
                        if (checked) next.add(id);
                        else next.delete(id);
                        setSelectedForResale(next);
                      }}
                      onViewQr={handleViewQr}
                      onRefund={handleRefund}
                      onCancelListing={handleCancelListing}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* 4. Organizer & Ledger Tab */}
      {activeTab === "organizer" && (
        <OrganizerLedgerView
          events={events}
          ledger={ledger}
          onToggleResale={handleToggleResale}
        />
      )}

      {/* 5. Gate Check-In Scanner Tab */}
      {activeTab === "checkin" && (
        <CheckInScannerView
          events={events}
          prefill={scannerPrefill}
          onScan={handleGateScan}
        />
      )}

      {/* Unified Auth Modal */}
      <AuthModal
        isOpen={authModal.isOpen}
        contextMessage={authModal.contextMessage}
        onClose={() => setAuthModal({ isOpen: false, contextMessage: "", pendingAction: null })}
        onRequestOtp={requestCode}
        onVerifyOtp={handleVerifyOtp}
      />

      {checkout && (
        <CheckoutModal
          event={checkout.event}
          quantity={checkout.quantity}
          order={checkout.order}
          api={api}
          onConfirm={handleConfirmMockPayment}
          onClose={closeCheckout}
        />
      )}

      {/* Full QR Pass Modal */}
      <AnimatePresence>
        {qrModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setQrModal(null)}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 16 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md backdrop-blur-md bg-[#121212]/95 border border-white/10 shadow-2xl rounded-3xl p-8 text-center space-y-5"
            >
              <div className="flex items-start justify-between text-left">
                <div>
                  <span className="text-[11px] font-semibold uppercase tracking-widest text-[#00E676]">
                    Credential Version v{qrModal.credential_version}
                  </span>
                  <h2 className="text-xl font-bold tracking-tight text-white mt-1">
                    Admission QR Pass
                  </h2>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setQrModal(null)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>

              <QrCodeMatrix value={qrModal.qr_token} size={13} />

              <div className="rounded-2xl bg-black/60 border border-white/10 p-3 text-[11px] font-mono text-white/75 break-all text-left">
                {qrModal.qr_token}
              </div>

              <div className="flex gap-2.5">
                <Button
                  variant="primary"
                  fullWidth
                  onClick={() => {
                    setScannerPrefill({
                      eventId: qrModal.event_id,
                      token: qrModal.qr_token,
                    });
                    setQrModal(null);
                    selectTab("checkin");
                  }}
                >
                  Test in Gate Scanner
                </Button>
                <Button
                  variant="glass"
                  onClick={() => {
                    navigator.clipboard?.writeText(qrModal.qr_token).catch(() => {});
                    notify("Copied signed QR token.");
                  }}
                >
                  Copy
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create Social Resale Campaign Modal */}
      <AnimatePresence>
        {campaignModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setCampaignModalOpen(false)}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 16 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md backdrop-blur-md bg-[#121212]/95 border border-white/10 shadow-2xl rounded-3xl p-8 space-y-5"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-xl font-bold tracking-tight text-white">
                    Publish Social Resale Campaign
                  </h2>
                  <p className="text-xs text-white/70 mt-1">
                    {selectedForResale.size} pass(es) · 5% EventPass fee · 95% seller proceeds
                  </p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setCampaignModalOpen(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>

              <form onSubmit={handleCreateCampaignSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-white/70 mb-1.5">
                    Campaign Title
                  </label>
                  <input
                    required
                    value={campaignTitle}
                    onChange={(e) => setCampaignTitle(e.target.value)}
                    className="w-full rounded-2xl bg-black/50 border border-white/15 px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#FF6B00]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-white/70 mb-1.5">
                    Asking Price Per Pass (ZAR)
                  </label>
                  <input
                    type="number"
                    required
                    min={1}
                    value={campaignPrice}
                    onChange={(e) => setCampaignPrice(e.target.value)}
                    className="w-full rounded-2xl bg-black/50 border border-white/15 px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#FF6B00]"
                  />
                </div>
                <Button type="submit" variant="primary" fullWidth size="lg">
                  Publish & Generate Share Link
                </Button>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </Layout>
  );
}
