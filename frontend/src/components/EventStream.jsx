import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play, Pause, StepForward, Radio } from "lucide-react";
import { fmtINR, timeAgo, shortId } from "../lib/api";

const failureColor = {
  BANK_DEGRADATION: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  MERCHANT_CHECKOUT_REGRESSION:
    "text-violet-400 bg-violet-400/10 border-violet-400/30",
  NETWORK_LATENCY: "text-white bg-white/10 border-white/30",
  CARD_DECLINED: "text-rose-400 bg-rose-400/10 border-rose-400/30",
  FRAUD_HOLD: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
};

export default function EventStream({
  events,
  selectedId,
  onSelect,
  autoStream,
  setAutoStream,
  onManualNext,
}) {
  return (
    <section
      className="glass-panel rounded-2xl overflow-hidden flex flex-col h-full"
      data-testid="event-stream"
    >
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-zinc-950/50 backdrop-blur-xl sticky top-0 z-10">
        <div>
          <div className="flex items-center gap-2">
            <span className="pulse-dot inline-block w-2 h-2 rounded-full bg-white text-white" />
            <span className="text-[10px] font-bold tracking-[0.22em] text-white uppercase">
              Live
            </span>
          </div>
          <h3 className="text-lg font-heading font-bold text-white">
            Failed Payment Events
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoStream(!autoStream)}
            className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-bold border transition-colors ${
              autoStream
                ? "bg-white text-zinc-900 border-white"
                : "bg-zinc-900/50 text-white border-white/10 hover:border-white"
            }`}
            data-testid="toggle-auto-stream"
          >
            {autoStream ? <Pause size={12} /> : <Play size={12} />}
            {autoStream ? "Pause" : "Auto"}
          </button>
          <button
            onClick={onManualNext}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-bold border bg-zinc-900/50 text-white border-white/10 hover:border-white transition-colors"
            data-testid="manual-next"
          >
            <StepForward size={12} /> Next
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto scroll-thin p-3 space-y-2 max-h-[600px]">
        <AnimatePresence initial={false}>
          {events.length === 0 && (
            <div className="text-sm text-zinc-500 p-6">
              Waiting for events…
            </div>
          )}
          {events.map((e) => {
            const isSel = e.event_id === selectedId;
            return (
              <motion.button
                layout
                key={e.event_id}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                whileHover={{ x: 2 }}
                onClick={() => onSelect(e)}
                className={`w-full text-left bg-zinc-900/50 border rounded-xl p-4 border-l-4 transition-colors glass-panel-hover ${
                  isSel
                    ? "border-white border-l-white bg-white/10 shadow-[0_6px_20px_-8px_rgba(255,255,255,0.3)]"
                    : "border-white/5 border-l-transparent hover:border-white hover:border-l-white"
                }`}
                data-testid={`event-${e.event_id}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <Radio size={14} className="text-white flex-shrink-0" />
                    <span className="font-mono-ui text-sm text-white truncate">
                      {e.event_id}
                    </span>
                  </div>
                  <span className="font-heading font-bold text-white">
                    {fmtINR(e.amount_paise)}
                  </span>
                </div>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <span
                    className={`inline-block text-[10px] font-bold tracking-[0.14em] uppercase px-2 py-0.5 rounded-full border ${
                      failureColor[e.failure_code] ||
                      "text-zinc-300 bg-zinc-800 border-zinc-700"
                    }`}
                  >
                    {(e.failure_code || "UNKNOWN").replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-zinc-500">
                    {e.method?.toUpperCase()} · {e.bank} ·{" "}
                    {timeAgo(e.occurred_at)}
                  </span>
                </div>
                <p className="mt-2 text-xs text-zinc-400 line-clamp-1">
                  {e.failure_note}
                </p>
                <p className="mt-1 text-[10px] text-zinc-500 font-mono-ui">
                  order {shortId(e.order_id, 14)}
                </p>
              </motion.button>
            );
          })}
        </AnimatePresence>
      </div>
    </section>
  );
}
