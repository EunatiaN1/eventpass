import { motion } from "framer-motion";
import {
  BookOpen,
  Calendar,
  ExternalLink,
  LogOut,
  ScanLine,
  Share2,
  Sliders,
  Ticket,
  Mail,
} from "lucide-react";
import { Button } from "./Button";

const NAV_ITEMS = [
  { id: "events", label: "Events & Buy", icon: Calendar },
  { id: "campaigns", label: "Social Resale", icon: Share2 },
  { id: "tickets", label: "My Tickets", icon: Ticket, gated: true },
  { id: "organizer", label: "Organizer & Ledger", icon: Sliders },
  { id: "checkin", label: "Gate Scanner", icon: ScanLine },
];

export function Navbar({ activeTab, onSelectTab, auth, onOpenAuth, onSignOut }) {
  return (
    <header className="sticky top-0 z-30 px-4 sm:px-6 pt-4">
      <div className="mx-auto max-w-7xl backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl px-5 py-3.5 flex flex-wrap items-center justify-between gap-4">
        {/* Brand + Solana Devnet glowing pill */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-[#FF6B00] to-[#FF9100] shadow-[0_8px_24px_-6px_rgba(255,107,0,0.65)]">
            <Ticket className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <span className="text-lg font-bold tracking-tight text-white">EventPass</span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#00E676]/10 text-[#00E676] border border-[#00E676]/30">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00E676] opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00E676] shadow-[0_0_8px_#00E676]" />
                </span>
                Solana Devnet
              </span>
            </div>
          </div>
        </div>

        {/* Center Navigation Pills */}
        <nav className="flex flex-wrap items-center gap-1.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <Button
                key={item.id}
                variant={isActive ? "primary" : "ghost"}
                size="sm"
                onClick={() => onSelectTab(item.id)}
                className={isActive ? "" : "text-white/70"}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
              </Button>
            );
          })}
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-white/60 hover:text-white rounded-xl hover:bg-white/5 transition-colors"
          >
            <BookOpen className="w-3.5 h-3.5" />
            API Docs
            <ExternalLink className="w-3 h-3" />
          </a>
        </nav>

        {/* Right Auth Action */}
        <div className="flex items-center gap-2">
          {auth.isAuthenticated ? (
            <div className="flex items-center gap-2">
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex max-w-[220px] items-center gap-2 rounded-2xl border border-white/10 bg-white/[.05] px-2.5 py-1.5 text-xs font-medium text-white"
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#FF6B00] to-[#FF9100] text-[11px] font-bold text-white shadow-[0_4px_14px_-5px_rgba(255,107,0,.8)]">
                  {(auth.email || auth.wallet || "E").slice(0, 1).toUpperCase()}
                </span>
                <span className="max-w-[150px] truncate">{auth.email || `${auth.wallet?.slice(0, 6)}…`}</span>
              </motion.div>
              <Button variant="glass" size="sm" onClick={onSignOut} title="Sign Out">
                <LogOut className="w-3.5 h-3.5" />
              </Button>
            </div>
          ) : (
            <Button variant="glass" size="md" onClick={() => onOpenAuth()}>
              <Mail className="w-4 h-4 text-[#FF8A35]" />
              <span>Sign In</span>
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
