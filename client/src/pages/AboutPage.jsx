import { LayersIcon } from "../components/Icons";

// Static page — no data fetching. Explains what the system is and how the
// architecture fits together. Content mirrors ARCHITECTURE.md at a high level.

const PIPELINE = [
    {
        num: "01",
        title: "Classify",
        agent: "Orchestrator · gpt-4o-mini",
        body: "The uploaded PDF or image is rasterised and a lightweight classifier decides which structural element the drawing depicts — foundation, slab, beam, or column. Every later stage is specialised per element type.",
    },
    {
        num: "02",
        title: "Transcribe",
        agent: "Specialist vision agent · gpt-4o",
        body: "A vision model reads the drawing at high detail with an element-specific prompt: bar callouts, cover, grades, schedules. It emits a phased report and flags every field the drawing left missing or unverifiable.",
    },
    {
        num: "03",
        title: "Resolve",
        agent: "Validator agent · gpt-4o-mini",
        body: "You fill in the missing fields — or type “assume” and the validator supplies standards-compliant defaults from IS-code tables. Invalid answers are rejected with an explanation of the expected value.",
    },
    {
        num: "04",
        title: "Verdict",
        agent: "Reasoning model · o4-mini + RAG",
        body: "The relevant IS 456 / SP 34 clauses are retrieved from a vector index, reranked by a cross-encoder, and diversified with MMR. A reasoning model then produces a citation-backed compliance verdict where every row is tagged with its source.",
    },
];

const RAG_STAGES = [
    { k: "Embed", v: "BAAI/bge-large-en-v1.5, one focused query per compliance row" },
    { k: "Retrieve", v: "ChromaDB cosine search, filtered by element type" },
    { k: "Rerank", v: "Cross-encoder bge-reranker-base scores each candidate" },
    { k: "Diversify", v: "MMR trims to the top passages without paraphrase pile-up" },
    { k: "Reason", v: "o4-mini writes the verdict, citing clause numbers" },
];

const STACK = [
    { k: "Frontend", v: "React 19 + Vite + Tailwind CSS, static SPA" },
    { k: "API", v: "FastAPI — auth, uploads, job orchestration" },
    { k: "Worker", v: "RQ background worker — vision, RAG, and reasoning run off-request" },
    { k: "Broker", v: "Redis queues the jobs; job state lives in Postgres" },
    { k: "Data", v: "Supabase — Postgres, JWT auth, row-level security" },
    { k: "Vectors", v: "ChromaDB embedded index over SP 34 / IS-code markdown" },
    { k: "Models", v: "gpt-4o (vision), gpt-4o-mini (classify/validate), o4-mini (reasoning)" },
];

function DiagramBox({ label, sub, accent }) {
    return (
        <div
            className={`border px-3 py-2.5 text-center rounded-[3px] ${
                accent
                    ? "border-[var(--color-accent)] bg-[var(--color-accent-glow)]"
                    : "border-[var(--color-border-medium)] bg-[var(--color-bg-card)]"
            }`}
        >
            <p className={`text-xs font-semibold ${accent ? "text-[var(--color-accent-light)]" : "text-[var(--color-text-primary)]"}`}>
                {label}
            </p>
            {sub && <p className="label-mono mt-1 normal-case tracking-normal">{sub}</p>}
        </div>
    );
}

function DiagramArrow({ label }) {
    return (
        <div className="flex flex-col items-center justify-center py-1" aria-hidden>
            <span className="label-mono mb-0.5">{label}</span>
            <svg width="12" height="20" viewBox="0 0 12 20" fill="none" stroke="var(--color-text-muted)" strokeWidth="1.5">
                <path d="M6 1v15" /><path d="m2 13 4 4 4-4" />
            </svg>
        </div>
    );
}

export default function AboutPage() {
    return (
        <>
            <header className="mb-8 pb-6 border-b border-[var(--color-border-subtle)]">
                <div className="flex items-baseline gap-3 mb-2">
                    <span className="label-mono">/about</span>
                    <span className="label-mono text-[var(--color-text-faint)]">·</span>
                    <span className="label-mono">system architecture</span>
                </div>
                <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
                    How the Compliance Engine works
                </h1>
                <p className="text-sm text-[var(--color-text-secondary)] mt-2 max-w-2xl leading-relaxed">
                    The engine audits Indian RCC structural drawings against IS 456:2000 and SP 34.
                    It is a workflow over multiple specialised AI agents — vision, validation, and
                    retrieval-augmented reasoning — glued together by a job queue so the browser
                    never waits on a model call.
                </p>
            </header>

            {/* Pipeline */}
            <section className="mb-10">
                <div className="flex items-center gap-2 mb-5">
                    <LayersIcon size={14} className="text-[var(--color-accent)]" />
                    <h2 className="text-base font-semibold text-[var(--color-text-primary)]">The four-stage pipeline</h2>
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                    {PIPELINE.map((s) => (
                        <div key={s.num} className="panel p-5">
                            <div className="flex items-baseline gap-3 mb-2">
                                <span className="mono text-[10px] tracking-[0.18em] text-[var(--color-accent)]">{s.num}</span>
                                <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{s.title}</h3>
                            </div>
                            <p className="label-mono mb-2.5 normal-case tracking-wider">{s.agent}</p>
                            <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">{s.body}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* System diagram */}
            <section className="mb-10">
                <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-5">System topology</h2>
                <div className="panel p-6">
                    <div className="max-w-md mx-auto">
                        <DiagramBox label="Browser" sub="React SPA — uploads, polls job progress" />
                        <DiagramArrow label="HTTPS + Bearer JWT" />
                        <DiagramBox label="FastAPI web process" sub="auth · rate limits · enqueue jobs · serve job status" accent />
                        <DiagramArrow label="Redis (RQ) enqueue" />
                        <DiagramBox label="Background worker" sub="vision agent · RAG retrieval · reasoning model" accent />
                        <div className="grid grid-cols-3 gap-3 mt-6">
                            <DiagramBox label="Supabase" sub="Postgres · auth · reports & jobs" />
                            <DiagramBox label="ChromaDB" sub="IS-code vector index" />
                            <DiagramBox label="OpenAI" sub="gpt-4o · o4-mini" />
                        </div>
                    </div>
                    <p className="text-[11px] text-[var(--color-text-muted)] mt-6 leading-relaxed text-center max-w-lg mx-auto">
                        Generate requests return immediately with a job id; the browser polls a plain
                        database-backed status endpoint while the worker does the heavy lifting.
                        Job state survives worker restarts because it lives in Postgres, not Redis.
                    </p>
                </div>
            </section>

            {/* RAG */}
            <section className="mb-10">
                <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-2">
                    Retrieval, not recall
                </h2>
                <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed max-w-2xl mb-5">
                    The final verdict never relies on the model&apos;s memory of Indian standards. Every
                    clause it cites is retrieved from an indexed corpus of SP 34 and IS-code text through
                    a multi-stage pipeline:
                </p>
                <div className="border border-[var(--color-border-subtle)] rounded-[4px] divide-y divide-[var(--color-border-subtle)]">
                    {RAG_STAGES.map((s, i) => (
                        <div key={s.k} className="grid grid-cols-[90px_1fr] gap-4 px-4 py-3 bg-[var(--color-bg-card)]">
                            <span className="mono text-[10px] uppercase tracking-wider text-[var(--color-accent-light)] pt-0.5">
                                {String(i + 1).padStart(2, "0")} {s.k}
                            </span>
                            <span className="text-xs text-[var(--color-text-secondary)]">{s.v}</span>
                        </div>
                    ))}
                </div>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-3 leading-relaxed">
                    When retrieval fails or comes back low-confidence, the report says so — an amber
                    banner tells you the verdict may be incomplete rather than silently guessing.
                </p>
            </section>

            {/* Stack */}
            <section className="mb-10">
                <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-5">Technology stack</h2>
                <div className="grid md:grid-cols-2 gap-px bg-[var(--color-border-subtle)] border border-[var(--color-border-subtle)] rounded-[4px] overflow-hidden">
                    {STACK.map((s) => (
                        <div key={s.k} className="bg-[var(--color-bg-card)] px-4 py-3">
                            <p className="mono text-[10px] uppercase tracking-wider text-[var(--color-accent-light)] mb-1">{s.k}</p>
                            <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">{s.v}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* Trust */}
            <section className="mb-4">
                <div className="panel p-5">
                    <p className="label-mono mb-2">A note on trust</p>
                    <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed max-w-2xl">
                        Every compliance row in the final report is tagged with its provenance —
                        read from the drawing, provided by you, assumed with your permission, or
                        not provided at all. Reports are stored per account with row-level security,
                        and the engine is a review aid: it does not replace sign-off by a licensed
                        structural engineer.
                    </p>
                </div>
            </section>
        </>
    );
}
