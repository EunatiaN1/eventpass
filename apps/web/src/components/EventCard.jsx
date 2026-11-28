import { motion } from "framer-motion";
import { Calendar, MapPin, ShieldCheck, Sparkles, Ticket } from "lucide-react";
import { useState } from "react";
import { Button } from "./Button";

const EVENT_IMAGES = {
  "evt-ct-electronic-2026":
    "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?auto=format&fit=crop&w=1200&q=80",
  "evt-afrofuture-jhb-2026":
    "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=1200&q=80",
  "evt-soweto-jazz-2026":
    "https://images.unsplash.com/photo-1511192336575-5a79af67a629?auto=format&fit=crop&w=1200&q=80",
};

const FALLBACK_IMAGE =
  "https://images.unsplash.com/photo-1540039155733-5bb30b53aa14?auto=format&fit=crop&w=1200&q=80";

export function EventCard({ event, index, onBuy }) {
  const [quantity, setQuantity] = useState(2);
  const imageUrl = EVENT_IMAGES[event.id] || FALLBACK_IMAGE;

  const formattedDate = new Date(event.event_date).toLocaleDateString("en-ZA", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.35 }}
      whileHover={{ y: -6 }}
      className="group relative flex flex-col overflow-hidden backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl"
    >
      {/* Top 55% Visual Hero Image with Gradient Overlay & Floating Metadata */}
      <div className="relative h-64 w-full overflow-hidden">
        <img
          src={imageUrl}
          alt={event.title}
          className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/45 to-black/15" />

        {/* Top Badges */}
        <div className="absolute top-4 left-4 right-4 flex items-center justify-between gap-2">
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold backdrop-blur-md border ${
              event.resale_enabled
                ? "bg-[#00E676]/15 text-[#00E676] border-[#00E676]/35"
                : "bg-red-500/20 text-red-300 border-red-500/35"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                event.resale_enabled ? "bg-[#00E676]" : "bg-red-400"
              }`}
            />
            {event.resale_enabled ? "Resale Protected" : "Resale Paused"}
          </span>

          <span className="px-3.5 py-1 rounded-full text-xs font-bold bg-black/60 backdrop-blur-md border border-white/15 text-white">
            R{event.ticket_price_zar} ZAR
          </span>
        </div>

        {/* Floating Event Title, Date & Venue over Image Gradient */}
        <div className="absolute bottom-4 left-6 right-6">
          <h2 className="text-xl font-bold tracking-tight text-white leading-snug mb-2">
            {event.title}
          </h2>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-white/80">
            <span className="inline-flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-[#FF6B00]" />
              {formattedDate}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-[#00E676]" />
              {event.venue}
            </span>
          </div>
        </div>
      </div>

      {/* Bottom Details + Prominent Full-Width Action */}
      <div className="flex flex-1 flex-col justify-between p-6 gap-5">
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-white/70">
              <Ticket className="w-3 h-3 text-[#FF6B00]" />
              {event.issued_tickets_count} Issued
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-white/70">
              <Sparkles className="w-3 h-3 text-[#00E676]" />
              {event.active_resale_count} On Resale
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-white/70">
              <ShieldCheck className="w-3 h-3 text-white/60" />
              Cap R{event.max_resale_price_zar || "—"}
            </span>
          </div>

          <p className="text-xs text-white/70 leading-relaxed">
            {event.refund_window?.eligible ? (
              <span>
                <strong className="text-[#00E676]">75% Refund Protection:</strong> Open until{" "}
                {new Date(event.refund_window.cutoff_at_local).toLocaleDateString("en-ZA", {
                  day: "numeric",
                  month: "short",
                })}{" "}
                ({event.timezone})
              </span>
            ) : (
              <span className="text-amber-300/90">
                75% Refund Window closed (within 15-day event cutoff)
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <div className="flex items-center rounded-2xl bg-white/5 border border-white/10 px-3 py-2">
            <span className="text-[11px] text-white/50 mr-2">Qty</span>
            <input
              type="number"
              min={1}
              max={10}
              value={quantity}
              onChange={(e) => setQuantity(Math.max(1, Math.min(10, Number(e.target.value) || 1)))}
              className="w-10 bg-transparent text-sm font-semibold text-white text-center focus:outline-none"
            />
          </div>
          <Button
            variant="primary"
            fullWidth
            size="lg"
            onClick={() => onBuy(event, quantity)}
          >
            Buy Tickets · R{event.ticket_price_zar * quantity}
          </Button>
        </div>
      </div>
    </motion.article>
  );
}
