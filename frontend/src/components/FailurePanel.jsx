import React, { useState } from "react";
import { motion } from "framer-motion";
import { Zap, GitFork, TimerReset, Copy } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

const scenarios = [
  {
    key: "concurrent",
    icon: GitFork,
    title: "Concurrent Webhooks",
    proof: "SQLite atomic UPSERT elects exactly one winner",
    action: api.failure.concurrent,
    testId: "trigger-concurrent",
  },
  {
    key: "stale",
    icon: TimerReset,
    title: "Stale Reservation",
    proof: "Crashed worker → next attempt STOP_AND_ESCALATE",
    action: api.failure.stale,
    testId: "trigger-stale",
  },
  {
    key: "duplicate",
    icon: Copy,
    title: "Duplicate Executor Call",
    proof: "PK constraint blocks 2nd write · at-most-once",
    action: api.failure.duplicate,
    testId: "trigger-duplicate",
  },
];

export default function FailurePanel({ onScenarioComplete }) {
  const [busyKey, setBusyKey] = useState(null);
  const [lastResult, setLastResult] = useState(null);

  const run = async (s) => {
    setBusyKey(s.key);
    try {
      const res = await s.action();
      setLastResult({ scenario: s.title, ...res });
      toast.success(`${s.title} → scenario proven`, {
        description: res.explanation,
      });
      onScenarioComplete?.();
    } catch (e) {
      toast.error(`Failed: ${s.title}`);
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <section
      className="glass-panel rounded-2xl p-6"
      data-testid="failure-panel"
    >
      <div className="flex items-center gap-2 mb-1">
        <Zap size={14} className="text-white" />
        <span className="text-[10px] font-bold tracking-[0.22em] text-white uppercase">
          Failure Injection
        </span>
      </div>
      <h3 className="text-xl font-heading font-bold text-white">
        Prove the guarantees, live.
      </h3>
      <p className="text-sm text-zinc-400 mt-1">
        Each button triggers a real scripted scenario against SQLite{" "}
        <span className="font-mono-ui">idempotency.db</span>.
      </p>

      <div className="mt-5 space-y-3">
        {scenarios.map((s) => {
          const Icon = s.icon;
          const busy = busyKey === s.key;
          return (
            <motion.button
              key={s.key}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.98 }}
              disabled={busy}
              onClick={() => run(s)}
              className="w-full text-left bg-zinc-900 border border-white/10 hover:border-white hover:bg-zinc-800 transition-colors text-white rounded-xl p-4 flex items-start gap-3 disabled:opacity-70 disabled:cursor-not-allowed hover:shadow-[0_10px_30px_-10px_rgba(255,255,255,0.15)]"
              data-testid={s.testId}
            >
              <div className="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center flex-shrink-0">
                <Icon size={18} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-heading font-bold">{s.title}</span>
                  <span className="text-[10px] font-bold tracking-[0.18em] uppercase opacity-80">
                    {busy ? "Running…" : "Trigger"}
                  </span>
                </div>
                <p className="text-xs mt-1 opacity-80">{s.proof}</p>
              </div>
            </motion.button>
          );
        })}
      </div>

      {lastResult && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-5 bg-zinc-900/50 border border-white/5 rounded-xl p-4"
          data-testid="scenario-output"
        >
          <div className="text-[10px] font-bold tracking-[0.22em] text-zinc-500 uppercase mb-1">
            Latest outcome — {lastResult.scenario}
          </div>
          <div className="text-xs text-zinc-400">{lastResult.explanation}</div>
          <pre className="mt-3 text-[10px] font-mono-ui text-zinc-300 whitespace-pre-wrap max-h-40 overflow-auto scroll-thin">
            {JSON.stringify(lastResult, null, 2)}
          </pre>
        </motion.div>
      )}
    </section>
  );
}
