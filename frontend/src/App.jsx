import React, { useCallback, useEffect, useRef, useState } from "react";
import "@/App.css";
import { Toaster } from "sonner";
import { motion } from "framer-motion";
import { Activity, Github, ShieldCheck } from "lucide-react";

import Hero3D from "@/components/Hero3D";
import KpiBar from "@/components/KpiBar";
import EventStream from "@/components/EventStream";
import PipelineViz from "@/components/PipelineViz";
import FailurePanel from "@/components/FailurePanel";
import AuditTables from "@/components/AuditTables";
import { api } from "@/lib/api";

function Header() {
  return (
    <header
      className="sticky top-0 z-30 glass-panel border-b-0 rounded-b-2xl mx-4 mt-2"
      data-testid="app-header"
    >
      <div className="max-w-[1440px] mx-auto flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-white flex items-center justify-center text-white glow-white">
            <ShieldCheck size={18} />
          </div>
          <div>
            <div className="text-[10px] font-bold tracking-[0.22em] text-white uppercase">
              Razorpay Buildathon
            </div>
            <div className="font-heading font-black text-white text-lg leading-none">
              Revenue Resilience AI
            </div>
          </div>
        </div>
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-zinc-400">
          <a
            href="#pipeline"
            className="hover:text-white transition-colors"
          >
            Pipeline
          </a>
          <a href="#audit" className="hover:text-white transition-colors">
            Audit
          </a>
          <a
            href="#failures"
            className="hover:text-white transition-colors"
          >
            Failure Injection
          </a>
        </nav>
        <div className="flex items-center gap-3">
          <span className="hidden md:inline-flex items-center gap-1 text-xs font-mono-ui text-zinc-500">
            <span className="pulse-dot inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 text-emerald-500" />{" "}
            backend·healthy
          </span>
          <a
            href="https://razorpay.com"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full bg-white text-zinc-900 hover:bg-zinc-200 transition-colors"
          >
            <Github size={12} /> Console v1
          </a>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden grain">
      <div className="max-w-[1440px] mx-auto px-8 pt-12 pb-6 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="lg:col-span-6"
        >
          <span className="inline-flex items-center gap-2 text-[11px] font-bold tracking-[0.22em] uppercase text-white px-3 py-1 rounded-full border border-white/25 bg-white/10">
            <Activity size={12} /> Live Operator Console
          </span>
          <h1 className="mt-5 text-4xl sm:text-5xl lg:text-6xl font-heading font-black tracking-tight text-white leading-[1.02]">
            Recover the revenue
            <br />
            payments quietly lose.
          </h1>
          <p className="mt-5 text-[15px] leading-relaxed text-zinc-400 max-w-xl">
            A probabilistic{" "}
            <span className="font-bold text-white">LLM Diagnosis</span>{" "}
            layer proposes, a deterministic{" "}
            <span className="font-bold text-white">Policy Gate</span>{" "}
            approves, and the{" "}
            <span className="font-bold text-white">Razorpay Executor</span>{" "}
            acts — all guarded by a WAL-enabled SQLite for strict at-most-once
            execution.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a
              href="#pipeline"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-full bg-white text-zinc-900 font-bold text-sm hover:bg-zinc-200 transition-colors glow-white"
            >
              See the pipeline
            </a>
            <a
              href="#failures"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-full bg-zinc-900/50 text-white font-bold text-sm border border-white/10 hover:border-white transition-colors backdrop-blur-md"
            >
              Prove the guarantees
            </a>
          </div>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.1 }}
          className="lg:col-span-6"
        >
          <Hero3D />
        </motion.div>
      </div>
    </section>
  );
}

export default function App() {
  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [autoStream, setAutoStream] = useState(false);
  const [reservations, setReservations] = useState([]);
  const [executors, setExecutors] = useState([]);
  const [metrics, setMetrics] = useState({});

  const refreshState = useCallback(async () => {
    try {
      const [r, e, m] = await Promise.all([
        api.reservations(),
        api.executors(),
        api.metrics(),
      ]);
      setReservations(r);
      setExecutors(e);
      setMetrics(m);
    } catch (err) {
      // ignore transient errors
    }
  }, []);

  const loadEvents = useCallback(async () => {
    const list = await api.listEvents();
    setEvents(list.reverse());
    if (!selected && list.length) setSelected(list[0]);
  }, [selected]);

  useEffect(() => {
    loadEvents();
    refreshState();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const t = setInterval(refreshState, 4000);
    return () => clearInterval(t);
  }, [refreshState]);

  const runFor = useCallback(
    async (event) => {
      if (!event) return;
      setSelected(event);
      setRunning(true);
      setPipelineResult(null);
      // stagger visuals: reveal stages one-by-one
      try {
        const res = await api.runPipeline(event);
        // simulate stage reveals for wow-effect
        setPipelineResult({ diagnosis: res.diagnosis });
        await new Promise((r) => setTimeout(r, 550));
        setPipelineResult((p) => ({ ...p, decision: res.decision }));
        await new Promise((r) => setTimeout(r, 550));
        setPipelineResult((p) => ({
          ...p,
          execution: res.execution,
          trace: res.trace,
        }));
      } finally {
        setRunning(false);
        refreshState();
      }
    },
    [refreshState],
  );

  const nextEventRef = useRef(null);
  nextEventRef.current = async () => {
    const e = await api.newEvent();
    setEvents((prev) => [e, ...prev].slice(0, 60));
    await runFor(e);
  };

  useEffect(() => {
    if (!autoStream) return;
    const t = setInterval(() => nextEventRef.current?.(), 6000);
    return () => clearInterval(t);
  }, [autoStream]);

  return (
    <div className="App">
      <Toaster position="top-right" richColors closeButton />
      <Header />
      <Hero />

      <main className="max-w-[1440px] mx-auto px-8 pb-24 space-y-10">
        <KpiBar metrics={metrics} />

        <section
          id="pipeline"
          className="grid grid-cols-1 lg:grid-cols-12 gap-6"
        >
          <div className="lg:col-span-4">
            <EventStream
              events={events}
              selectedId={selected?.event_id}
              onSelect={(e) => runFor(e)}
              autoStream={autoStream}
              setAutoStream={setAutoStream}
              onManualNext={() => nextEventRef.current?.()}
            />
          </div>
          <div className="lg:col-span-8">
            <PipelineViz
              selected={selected}
              result={pipelineResult}
              running={running}
            />
          </div>
        </section>

        <section
          id="failures"
          className="grid grid-cols-1 lg:grid-cols-12 gap-6"
        >
          <div className="lg:col-span-5">
            <FailurePanel onScenarioComplete={refreshState} />
          </div>
          <div className="lg:col-span-7">
            <div className="h-full bg-zinc-900 border border-white/5 rounded-2xl p-8 text-white overflow-hidden relative glass-panel">
              <div className="absolute -right-20 -top-20 w-72 h-72 rounded-full bg-white/20 blur-3xl" />
              <div className="absolute -left-16 -bottom-16 w-72 h-72 rounded-full bg-violet-500/10 blur-3xl" />
              <div className="relative">
                <div className="text-[10px] font-bold tracking-[0.22em] uppercase text-zinc-300">
                  Guarantees
                </div>
                <h3 className="mt-1 text-3xl font-heading font-black leading-tight text-white">
                  At-most-once execution,
                  <br /> even under race conditions.
                </h3>
                <ul className="mt-5 space-y-3 text-sm text-zinc-300">
                  <li>
                    <span className="font-bold text-zinc-200">Atomic UPSERT</span>{" "}
                    — pre-claimed PENDING locks in SQLite before the expensive
                    LLM ever runs.
                  </li>
                  <li>
                    <span className="font-bold text-zinc-200">
                      Deterministic policy gate
                    </span>{" "}
                    — hard confidence floor + economic thresholds + safety
                    gates.
                  </li>
                  <li>
                    <span className="font-bold text-zinc-200">
                      WAL journal mode
                    </span>{" "}
                    — durable concurrent readers/writers, zero lost writes.
                  </li>
                  <li>
                    <span className="font-bold text-zinc-200">
                      Executor idempotency
                    </span>{" "}
                    — PK constraint blocks duplicate SDK calls.
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <section id="audit">
          <AuditTables
            reservations={reservations}
            executors={executors}
            onRefresh={refreshState}
          />
        </section>

        <footer className="pt-10 border-t border-white/10 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-xs text-zinc-500">
          <div>
            <span className="font-heading font-bold text-zinc-300">
              Revenue Resilience AI
            </span>{" "}
            · Operator Console — Razorpay Buildathon 2026
          </div>
          <div className="font-mono-ui">
            idempotency.db · WAL · at-most-once
          </div>
        </footer>
      </main>
    </div>
  );
}
