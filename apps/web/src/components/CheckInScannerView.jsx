import { CheckCircle2, ScanLine, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "./Button";

export function CheckInScannerView({ events, prefill, onScan }) {
  const [eventId, setEventId] = useState(prefill?.eventId || events[0]?.id || "");
  const [qrToken, setQrToken] = useState(prefill?.token || "");
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (prefill?.eventId) setEventId(prefill.eventId);
    if (prefill?.token) setQrToken(prefill.token);
  }, [prefill]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const res = await onScan({
      event_id: eventId || events[0]?.id,
      qr_token: qrToken.trim(),
      scanner_id: "GateScanner-Main-01",
    });
    if (res) setResult(res);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">Gate Check-In Scanner</h1>
        <p className="text-sm text-white/70 mt-2">
          Verifies cryptographic signature, event match, credential version (rejects old seller
          QRs after resale), refund status, and prevents duplicate entry.
        </p>
      </div>

      {result && (
        <div
          className={`backdrop-blur-md bg-white/5 border rounded-3xl p-6 flex items-start gap-4 ${
            result.accepted ? "border-[#00E676]/45" : "border-red-500/45"
          }`}
        >
          {result.accepted ? (
            <CheckCircle2 className="w-7 h-7 text-[#00E676] shrink-0" />
          ) : (
            <XCircle className="w-7 h-7 text-red-400 shrink-0" />
          )}
          <div>
            <div
              className={`text-xs font-bold uppercase tracking-wider ${
                result.accepted ? "text-[#00E676]" : "text-red-300"
              }`}
            >
              {result.result}
            </div>
            <p className="text-sm text-white mt-1">{result.reason}</p>
          </div>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="backdrop-blur-md bg-white/5 border border-white/10 shadow-2xl rounded-3xl p-8 space-y-5"
      >
        <div>
          <label className="block text-xs font-medium text-white/70 mb-2">Gate Event</label>
          <select
            value={eventId || events[0]?.id || ""}
            onChange={(e) => setEventId(e.target.value)}
            className="w-full rounded-2xl bg-black/50 border border-white/15 px-4 py-3 text-sm text-white focus:outline-none focus:border-[#FF6B00]"
          >
            {events.map((ev) => (
              <option key={ev.id} value={ev.id} className="bg-[#0A0A0A]">
                {ev.title}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-white/70 mb-2">
            Signed QR Credential Token
          </label>
          <textarea
            rows={4}
            required
            value={qrToken}
            onChange={(e) => setQrToken(e.target.value)}
            placeholder="Paste epv1... token from My Tickets"
            className="w-full rounded-2xl bg-black/50 border border-white/15 px-4 py-3 text-xs font-mono text-white placeholder:text-white/30 focus:outline-none focus:border-[#FF6B00]"
          />
        </div>

        <Button type="submit" variant="primary" fullWidth size="lg">
          <ScanLine className="w-4 h-4" />
          Scan & Validate Ticket
        </Button>
      </form>
    </div>
  );
}
