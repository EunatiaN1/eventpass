import { motion } from "framer-motion";
import { Calendar, CheckCircle2, QrCode, RotateCcw, Share2, ShieldAlert } from "lucide-react";
import { Button } from "./Button";
import { QrCodeMatrix } from "./QrCodeMatrix";

const STATUS_BADGES = {
  issued: "bg-[#00E676]/15 text-[#00E676] border-[#00E676]/30",
  listed: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  reserved: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  sold: "bg-purple-500/15 text-purple-300 border-purple-500/30",
  checked_in: "bg-[#00E676]/20 text-[#00E676] border-[#00E676]/40",
  refunded: "bg-red-500/15 text-red-300 border-red-500/30",
};

export function TicketPassCard({
  ticket,
  index,
  isSelected,
  onToggleSelect,
  onViewQr,
  onRefund,
  onCancelListing,
}) {
  const isRefunded = ticket.status === "refunded";

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3 }}
      whileHover={{ y: -4 }}
      className="relative flex flex-col backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl overflow-hidden"
    >
      {/* Top Pass Header */}
      <div className="p-6 pb-5 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="text-[11px] uppercase tracking-widest text-white/50 font-semibold">
              {ticket.tier} · v{ticket.credential_version}
            </span>
            <h3 className="text-lg font-bold tracking-tight text-white mt-0.5">
              {ticket.event_title}
            </h3>
          </div>
          <span
            className={`px-3 py-1 rounded-full text-[11px] font-semibold border ${
              STATUS_BADGES[ticket.status] || "bg-white/10 text-white/70 border-white/15"
            }`}
          >
            {ticket.status}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-white/70">
          <span className="inline-flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-[#FF6B00]" />
            {ticket.event_date
              ? new Date(ticket.event_date).toLocaleDateString("en-ZA", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })
              : "—"}
          </span>
          <span>Original: R{ticket.original_price_zar}</span>
          <span>Cap: R{ticket.max_resale_price_zar || "—"}</span>
        </div>

        <div className="rounded-2xl bg-black/40 border border-white/5 px-3.5 py-2 text-[11px] font-mono text-white/60 truncate">
          Asset: {ticket.asset_address}
        </div>
      </div>

      {/* Perforated Divider with Side Notches */}
      <div className="relative flex items-center px-6 py-2">
        <div className="ticket-notch-left" />
        <div className="w-full border-t border-dashed border-white/20" />
        <div className="ticket-notch-right" />
      </div>

      {/* Bottom Pass Body: Scannable White QR Block + Actions */}
      <div className="p-6 pt-4 flex flex-col gap-5 flex-1 justify-between">
        <div className="flex items-center gap-5">
          {isRefunded ? (
            <div className="flex h-28 w-28 shrink-0 items-center justify-center rounded-2xl bg-red-500/10 border border-red-500/25 text-red-300 text-xs text-center p-2">
              <div>
                <ShieldAlert className="w-6 h-6 mx-auto mb-1" />
                Revoked
              </div>
            </div>
          ) : (
            <div className="shrink-0">
              <QrCodeMatrix value={`${ticket.id}:v${ticket.credential_version}`} size={9} />
            </div>
          )}

          <div className="space-y-2 text-xs text-white/70 flex-1">
            <div className="font-mono text-white/90 text-[11px]">ID: {ticket.id}</div>
            {["issued", "sold"].includes(ticket.status) && ticket.resale_enabled && (
              <label className="flex items-center gap-2 cursor-pointer select-none rounded-xl bg-white/5 border border-white/10 px-3 py-2 hover:bg-white/10 transition-colors">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={(e) => onToggleSelect(ticket.id, e.target.checked)}
                  className="accent-[#FF6B00] w-4 h-4"
                />
                <span className="text-white/90 font-medium flex items-center gap-1.5">
                  <Share2 className="w-3.5 h-3.5 text-[#FF6B00]" />
                  Select for Resale
                </span>
              </label>
            )}
            {ticket.refund_eligible ? (
              <div className="text-[11px] text-[#00E676] flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                Eligible for 75% refund (R{ticket.refund_amount_zar})
              </div>
            ) : (
              <div className="text-[11px] text-white/45">{ticket.refund_window_reason}</div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-2.5">
          {!isRefunded && (
            <Button variant="glass" size="sm" onClick={() => onViewQr(ticket.id)}>
              <QrCode className="w-3.5 h-3.5 text-[#00E676]" />
              Full QR Pass
            </Button>
          )}
          {ticket.refund_eligible && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => onRefund(ticket.id, ticket.refund_amount_zar)}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              75% Refund (R{ticket.refund_amount_zar})
            </Button>
          )}
          {ticket.active_listing && ticket.active_listing.status === "active" && (
            <Button
              variant="glass"
              size="sm"
              onClick={() => onCancelListing(ticket.active_listing.id)}
            >
              Cancel Listing
            </Button>
          )}
        </div>
      </div>
    </motion.div>
  );
}
