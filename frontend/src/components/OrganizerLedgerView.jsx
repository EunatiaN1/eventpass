import { BookOpen, RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "./Button";

export function OrganizerLedgerView({ events, ledger, onToggleResale }) {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">
          Organizer Controls & Double-Entry Ledger
        </h1>
        <p className="text-sm text-white/70 mt-2">
          Manage event resale policies and audit balanced debits/credits, 3-business-day payouts,
          and Solana Devnet outbox jobs.
        </p>
      </div>

      {/* Organizer Controls */}
      <div className="backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-base font-bold tracking-tight">
          <ShieldCheck className="w-5 h-5 text-[#FF6B00]" />
          Event Resale Policies
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-white/10 text-white/50">
                <th className="py-3 pr-4">Event</th>
                <th className="py-3 pr-4">Primary</th>
                <th className="py-3 pr-4">Resale Cap</th>
                <th className="py-3 pr-4">Status</th>
                <th className="py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {events.map((ev) => (
                <tr key={ev.id}>
                  <td className="py-3.5 pr-4">
                    <div className="font-semibold text-white">{ev.title}</div>
                    <div className="text-white/50">{ev.timezone}</div>
                  </td>
                  <td className="py-3.5 pr-4">R{ev.ticket_price_zar}</td>
                  <td className="py-3.5 pr-4">R{ev.max_resale_price_zar || "—"}</td>
                  <td className="py-3.5 pr-4">
                    <span
                      className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                        ev.resale_enabled
                          ? "bg-[#00E676]/15 text-[#00E676] border-[#00E676]/30"
                          : "bg-red-500/15 text-red-300 border-red-500/30"
                      }`}
                    >
                      {ev.resale_enabled ? "Enabled" : "Disabled"}
                    </span>
                  </td>
                  <td className="py-3.5">
                    <Button
                      variant="glass"
                      size="sm"
                      onClick={() => onToggleResale(ev.id, !ev.resale_enabled)}
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      {ev.resale_enabled ? "Pause Resale" : "Enable Resale"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Double-Entry Ledger */}
      <div className="backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-base font-bold tracking-tight">
            <BookOpen className="w-5 h-5 text-[#00E676]" />
            Immutable Double-Entry Ledger
          </div>
          <span className="text-xs text-white/60">
            {ledger?.journals?.length || 0} Journals · {ledger?.entries?.length || 0} Entries
          </span>
        </div>

        {!ledger?.entries?.length ? (
          <p className="text-xs text-white/60">
            No journals posted yet. Complete a resale checkout or 75% refund to inspect balanced
            debits and credits.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-white/50">
                  <th className="py-2.5 pr-4">Journal</th>
                  <th className="py-2.5 pr-4">Account</th>
                  <th className="py-2.5 pr-4">Direction</th>
                  <th className="py-2.5">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {ledger.entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="py-2.5 pr-4 font-mono text-white/70">
                      {entry.journal_id.slice(0, 8)}…
                    </td>
                    <td className="py-2.5 pr-4 font-mono">{entry.account_code}</td>
                    <td className="py-2.5 pr-4">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                          entry.direction === "debit"
                            ? "bg-sky-500/15 text-sky-300"
                            : "bg-[#00E676]/15 text-[#00E676]"
                        }`}
                      >
                        {entry.direction}
                      </span>
                    </td>
                    <td className="py-2.5 font-semibold text-white">{entry.amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
