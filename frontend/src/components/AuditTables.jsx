import React from "react";
import { Database, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";
import { shortId, timeAgo, fmtINR } from "../lib/api";

const statusStyle = {
  PENDING: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  SUCCESS: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
  ESCALATED: "text-rose-400 bg-rose-400/10 border-rose-400/30",
  DUPLICATE_BLOCKED: "text-white bg-white/10 border-white/30",
  SDK_ERROR: "text-rose-400 bg-rose-400/10 border-rose-400/30",
};

const Table = ({ title, sub, rows, columns, testId }) => (
  <div
    className="glass-panel rounded-2xl overflow-hidden"
    data-testid={testId}
  >
    <div className="px-5 py-4 border-b border-white/10 bg-zinc-950/50 flex items-center justify-between">
      <div>
        <div className="flex items-center gap-2">
          <Database size={14} className="text-white" />
          <span className="text-[10px] font-bold tracking-[0.22em] text-white uppercase">
            SQLite · {title}
          </span>
        </div>
        <div className="text-sm text-zinc-400 mt-0.5">{sub}</div>
      </div>
      <span className="text-xs font-mono-ui text-zinc-500">
        {rows.length} rows
      </span>
    </div>
    <div className="overflow-x-auto scroll-thin">
      <table className="w-full text-left">
        <thead className="bg-zinc-900/50">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className="px-4 py-3 text-[10px] font-bold tracking-[0.18em] text-zinc-300 uppercase border-b border-white/10"
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-8 text-center text-sm text-zinc-500"
              >
                No records yet — trigger the pipeline or a failure scenario.
              </td>
            </tr>
          ) : (
            rows.map((r, i) => (
              <motion.tr
                key={r.reservation_id || r.execution_id || i}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="border-b border-white/5 hover:bg-zinc-800/50"
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className="px-4 py-3 font-mono-ui text-xs text-zinc-400"
                  >
                    {c.render ? c.render(r) : (r[c.key] ?? "—")}
                  </td>
                ))}
              </motion.tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  </div>
);

export default function AuditTables({ reservations, executors, onRefresh }) {
  return (
    <section className="space-y-6" data-testid="audit-section">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] font-bold tracking-[0.22em] text-white uppercase">
            Immutable Audit State
          </div>
          <h3 className="text-2xl font-heading font-bold text-white">
            Reading from idempotency.db (WAL enabled)
          </h3>
        </div>
        <button
          onClick={onRefresh}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold border border-white/10 bg-zinc-900 text-white hover:border-white transition-colors"
          data-testid="refresh-audit"
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      <Table
        testId="table-reservations"
        title="action_reservations"
        sub="Pre-claimed PENDING locks — atomic UPSERTs guarantee single-writer."
        rows={reservations}
        columns={[
          {
            key: "reservation_id",
            label: "Reservation",
            render: (r) => shortId(r.reservation_id, 26),
          },
          {
            key: "event_id",
            label: "Event",
            render: (r) => shortId(r.event_id, 14),
          },
          { key: "action", label: "Action" },
          {
            key: "status",
            label: "Status",
            render: (r) => (
              <span
                className={`text-[10px] font-bold tracking-[0.14em] uppercase px-2 py-0.5 rounded-full border ${statusStyle[r.status] || "text-zinc-400 bg-zinc-800 border-zinc-700"}`}
              >
                {r.status}
              </span>
            ),
          },
          { key: "worker_id", label: "Worker" },
          {
            key: "claimed_at",
            label: "Claimed",
            render: (r) => timeAgo(r.claimed_at),
          },
        ]}
      />

      <Table
        testId="table-executors"
        title="executor_states"
        sub="Write-once execution log. Duplicate execution_ids fail on PK."
        rows={executors}
        columns={[
          {
            key: "execution_id",
            label: "Execution",
            render: (r) => shortId(r.execution_id, 22),
          },
          {
            key: "reservation_id",
            label: "Reservation",
            render: (r) => shortId(r.reservation_id, 22),
          },
          {
            key: "razorpay_ref",
            label: "Razorpay Ref",
            render: (r) => shortId(r.razorpay_ref, 22),
          },
          {
            key: "outcome",
            label: "Outcome",
            render: (r) => (
              <span
                className={`text-[10px] font-bold tracking-[0.14em] uppercase px-2 py-0.5 rounded-full border ${statusStyle[r.outcome] || "text-zinc-400 bg-zinc-800 border-zinc-700"}`}
              >
                {r.outcome}
              </span>
            ),
          },
          {
            key: "amount_paise",
            label: "Amount",
            render: (r) => fmtINR(r.amount_paise),
          },
          {
            key: "latency_ms",
            label: "Latency",
            render: (r) => `${r.latency_ms} ms`,
          },
          {
            key: "created_at",
            label: "When",
            render: (r) => timeAgo(r.created_at),
          },
        ]}
      />
    </section>
  );
}
