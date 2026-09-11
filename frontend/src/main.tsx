import { StrictMode, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Page = 'overview' | 'queue' | 'traces' | 'evaluation';
type Tone = 'violet' | 'amber' | 'teal' | 'rose' | 'blue';

type TraceStep = {
  label: string;
  detail: string;
  status: 'complete' | 'active' | 'blocked';
  time: string;
};

type AgentTrace = {
  id: string;
  customer: string;
  transaction: string;
  amount: string;
  amountMinor: number;
  risk: string;
  riskTone: Tone;
  state: string;
  action: string;
  actionTone: Tone;
  reason: string;
  confidence: string;
  timestamp: string;
  steps: TraceStep[];
};

const evaluation500 = {
  scenarios: 500,
  atRisk: 400,
  recovered: 182,
  atRiskRevenue: 2163200,
  recoveredRevenue: 980887,
  revenueRate: '45.34%',
  caseRate: '45.50%',
  actionAccuracy: '20.00%',
  safetyRate: '100.00%',
  failures: 181,
  escalations: 90,
  verifications: 91,
  stopped: 46,
  rejected: 46,
};

const traces: AgentTrace[] = [
  {
    id: 'eval-0042-0018', customer: 'Northstar Labs', transaction: 'txn_8F31A', amount: '$8,420', amountMinor: 842000, risk: 'Failed payment', riskTone: 'rose', state: 'Recovered', action: 'Retry payment', actionTone: 'teal', reason: 'payment_failed', confidence: '0.94', timestamp: '2 min ago',
    steps: [
      { label: 'Risk detected', detail: 'Payment failed · insufficient_funds', status: 'complete', time: '12:04:11' },
      { label: 'Context gathered', detail: 'Customer active · 0 prior attempts', status: 'complete', time: '12:04:12' },
      { label: 'Agent decision', detail: 'Retry payment · confidence 0.94', status: 'complete', time: '12:04:14' },
      { label: 'Policy check', detail: 'Allowed · attempt 1 of 2', status: 'complete', time: '12:04:14' },
      { label: 'Tool execution', detail: 'Provider returned succeeded', status: 'complete', time: '12:04:18' },
    ],
  },
  {
    id: 'eval-0042-0019', customer: 'Asteria Living', transaction: 'txn_2D90C', amount: '$12,800', amountMinor: 1280000, risk: 'Unknown outcome', riskTone: 'amber', state: 'Verification pending', action: 'Operator review', actionTone: 'amber', reason: 'uncertain_outcome', confidence: '0.77', timestamp: '8 min ago',
    steps: [
      { label: 'Risk detected', detail: 'Payment status unknown', status: 'complete', time: '11:58:02' },
      { label: 'Context gathered', detail: 'Customer active · 0 prior attempts', status: 'complete', time: '11:58:03' },
      { label: 'Agent decision', detail: 'Retry proposed · confidence 0.77', status: 'complete', time: '11:58:05' },
      { label: 'Policy check', detail: 'Allowed with verification guard', status: 'complete', time: '11:58:05' },
      { label: 'Provider result', detail: 'Uncertain · verification required', status: 'active', time: '11:58:10' },
    ],
  },
  {
    id: 'eval-0042-0020', customer: 'Monument Bank', transaction: 'txn_9A12F', amount: '$4,150', amountMinor: 415000, risk: 'Failed payment', riskTone: 'rose', state: 'Escalated', action: 'Operator review', actionTone: 'violet', reason: 'retry_limit_reached', confidence: '0.88', timestamp: '14 min ago',
    steps: [
      { label: 'Risk detected', detail: 'Payment failed · provider_declined', status: 'complete', time: '11:52:44' },
      { label: 'Context gathered', detail: 'Customer active · 2 prior attempts', status: 'complete', time: '11:52:45' },
      { label: 'Agent decision', detail: 'Retry payment · confidence 0.88', status: 'complete', time: '11:52:47' },
      { label: 'Policy check', detail: 'Retry limit reached · blocked', status: 'blocked', time: '11:52:47' },
      { label: 'Escalation', detail: 'Operator review required', status: 'active', time: '11:52:48' },
    ],
  },
  {
    id: 'eval-0042-0021', customer: 'Cobalt Office', transaction: 'txn_0B77E', amount: '$2,760', amountMinor: 276000, risk: 'Pending > 24h', riskTone: 'blue', state: 'Awaiting decision', action: 'Retry payment', actionTone: 'teal', reason: 'payment_pending_too_long', confidence: '0.81', timestamp: '22 min ago',
    steps: [
      { label: 'Risk detected', detail: 'Pending payment crossed 24h threshold', status: 'complete', time: '11:44:20' },
      { label: 'Context gathered', detail: 'Customer active · 0 prior attempts', status: 'complete', time: '11:44:21' },
      { label: 'Agent decision', detail: 'Retry payment · confidence 0.81', status: 'active', time: '11:44:24' },
      { label: 'Policy check', detail: 'Waiting for decision validation', status: 'active', time: '—' },
      { label: 'Tool execution', detail: 'Not started', status: 'blocked', time: '—' },
    ],
  },
];

const navItems: { id: Page; label: string; icon: string }[] = [
  { id: 'overview', label: 'Command center', icon: '⌂' },
  { id: 'queue', label: 'Recovery queue', icon: '◫' },
  { id: 'traces', label: 'Agent traces', icon: '⌁' },
  { id: 'evaluation', label: 'Evaluation lab', icon: '◌' },
];

function Logo() {
  return <div className="logo"><span className="logo-mark"><i /></span><span>Revenue<span className="logo-accent">Rescue</span><sup>AI</sup></span></div>;
}

function MetricCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: Tone }) {
  return <article className={`metric-card ${tone}`}><div className="metric-label">{label}</div><strong>{value}</strong><span>{detail}</span></article>;
}

function Donut({ value }: { value: number }) {
  return <div className="donut" style={{ '--progress': `${value * 3.6}deg` } as React.CSSProperties}><div><strong>{value}%</strong><span>recovered</span></div></div>;
}

function TrendChart() {
  return <div className="trend-wrap"><div className="chart-y"><span>1.0m</span><span>750k</span><span>500k</span><span>250k</span><span>0</span></div><svg viewBox="0 0 760 220" preserveAspectRatio="none" aria-label="Recovered revenue trend"><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#8b7cff" stopOpacity=".33"/><stop offset="1" stopColor="#8b7cff" stopOpacity="0"/></linearGradient></defs><path d="M0 190 C60 174 82 184 126 157 S193 169 238 135 S305 143 348 120 S414 134 454 92 S516 118 554 76 S620 89 660 42 S710 58 760 22 L760 220 L0 220Z" fill="url(#fill)"/><path d="M0 190 C60 174 82 184 126 157 S193 169 238 135 S305 143 348 120 S414 134 454 92 S516 118 554 76 S620 89 660 42 S710 58 760 22" className="chart-stroke"/><circle cx="660" cy="42" r="5" className="chart-dot"/></svg><div className="chart-x"><span>Jan 1</span><span>Jan 8</span><span>Jan 15</span><span>Jan 22</span><span>Jan 29</span></div></div>;
}

function Overview({ onNavigate }: { onNavigate: (page: Page) => void }) {
  return <div className="page-content"><div className="page-head"><div><p className="eyebrow">OPERATIONS / LIVE OVERVIEW</p><h1>Good morning, Alex.</h1><p className="subhead">Your recovery system is watching <strong>400 at-risk cases</strong> across the revenue graph.</p></div><div className="head-actions"><span className="live-badge"><i /> Live simulation feed</span><button className="secondary-button" onClick={() => onNavigate('evaluation')}>Run evaluation</button></div></div><div className="metric-grid"><MetricCard label="Recovered revenue" value="$980.9k" detail="45.34% of at-risk revenue · 500 scenarios" tone="violet"/><MetricCard label="At-risk revenue" value="$2.16m" detail="400 open synthetic cases" tone="amber"/><MetricCard label="Safety rate" value="100.00%" detail="0 unsafe actions in evaluation" tone="teal"/><MetricCard label="Needs attention" value="181" detail="90 escalations · 91 verifications" tone="rose"/></div><div className="overview-grid"><section className="panel chart-panel"><div className="panel-head"><div><p className="eyebrow">RECOVERY PERFORMANCE</p><h2>Recovered revenue</h2><span className="panel-sub">500-scenario evaluation · seed 42</span></div><div className="chart-total"><strong>$980,887</strong><span>minor units recovered</span></div></div><TrendChart/><div className="legend"><span><i className="legend-line violet-line"/> Recovered revenue</span><span><i className="legend-line muted-line"/> At-risk baseline</span><button className="text-link" onClick={() => onNavigate('evaluation')}>Inspect report →</button></div></section><section className="panel recovery-card"><div className="panel-head"><div><p className="eyebrow">BATCH OUTCOME</p><h2>Case recovery rate</h2></div><span className="status-chip success">phase8.v1</span></div><div className="donut-row"><Donut value={45}/><div className="outcome-list"><div><i className="dot teal-dot"/><span>Recovered</span><strong>182</strong></div><div><i className="dot amber-dot"/><span>Escalated</span><strong>90</strong></div><div><i className="dot rose-dot"/><span>Verification</span><strong>91</strong></div><div><i className="dot muted-dot"/><span>Stopped / rejected</span><strong>92</strong></div></div></div><div className="card-foot"><span>Action accuracy</span><strong>20.00%</strong></div></section></div><section className="panel traces-preview"><div className="panel-head"><div><p className="eyebrow">TRANSACTION-LEVEL OBSERVABILITY</p><h2>Latest agent traces</h2><span className="panel-sub">Follow every decision from signal to outcome.</span></div><button className="text-link" onClick={() => onNavigate('traces')}>View all traces →</button></div><TraceTable rows={traces.slice(0, 3)} compact onSelect={() => onNavigate('traces')}/></section></div>;
}

function TraceTable({ rows, compact = false, onSelect }: { rows: AgentTrace[]; compact?: boolean; onSelect: (trace: AgentTrace) => void }) {
  return <div className={`trace-table ${compact ? 'compact' : ''}`}><div className="trace-header"><span>Account / transaction</span><span>Risk</span><span>Decision</span><span>State</span><span>Time</span></div>{rows.map((row) => <button className="trace-row" key={row.id} onClick={() => onSelect(row)}><div className="trace-account"><span className={`avatar ${row.riskTone}`}>{row.customer.split(' ').map((part) => part[0]).join('').slice(0, 2)}</span><span><strong>{row.customer}</strong><small>{row.transaction} · {row.amount}</small></span></div><span className={`tag ${row.riskTone}`}>{row.risk}</span><span className="decision"><b className={`decision-dot ${row.actionTone}`} />{row.action}</span><span className={`state ${row.state.toLowerCase().replace(/ /g, '-')}`}>{row.state}</span><time>{row.timestamp}</time></button>)}</div>;
}

function Queue({ onSelect }: { onSelect: (trace: AgentTrace) => void }) {
  const [filter, setFilter] = useState('All cases');
  const filtered = filter === 'All cases' ? traces : traces.filter((trace) => trace.state === filter);
  return <div className="page-content"><div className="page-head"><div><p className="eyebrow">WORK QUEUE / SYNTHETIC RUN</p><h1>Recovery queue</h1><p className="subhead">Prioritize cases where a human decision can protect the most revenue.</p></div><div className="head-actions"><span className="queue-count">{evaluation500.atRisk} at risk</span><button className="secondary-button">Export queue</button></div></div><div className="queue-summary"><div><span>At-risk revenue</span><strong>$2.16m</strong></div><div><span>Awaiting decision</span><strong>112</strong></div><div><span>Verification pending</span><strong>91</strong></div><div><span>Escalated</span><strong>90</strong></div></div><section className="panel queue-panel"><div className="toolbar"><div><p className="eyebrow">OPEN OPPORTUNITIES</p><h2>Human-in-the-loop queue</h2></div><select value={filter} onChange={(event) => setFilter(event.target.value)}><option>All cases</option><option>Awaiting decision</option><option>Verification pending</option><option>Escalated</option><option>Recovered</option></select></div><TraceTable rows={filtered} onSelect={onSelect}/></section></div>;
}

function TraceDetail({ trace, onClose }: { trace: AgentTrace; onClose: () => void }) {
  return <aside className="trace-detail"><div className="detail-head"><div><p className="eyebrow">TRACE DETAIL</p><h2>{trace.customer}</h2><span>{trace.id} · {trace.transaction}</span></div><button className="close-button" onClick={onClose}>×</button></div><div className="detail-hero"><div><span>Transaction amount</span><strong>{trace.amount}</strong></div><span className={`tag ${trace.riskTone}`}>{trace.risk}</span></div><div className="detail-section"><p className="eyebrow">AGENT JOURNEY</p><div className="journey">{trace.steps.map((step, index) => <div className={`journey-step ${step.status}`} key={step.label}><span className="journey-marker">{step.status === 'complete' ? '✓' : step.status === 'active' ? '•' : '!'}</span><div><div className="journey-title"><strong>{step.label}</strong><time>{step.time}</time></div><p>{step.detail}</p></div>{index < trace.steps.length - 1 && <i className="journey-line"/>}</div>)}</div></div><div className="detail-section decision-box"><p className="eyebrow">STRUCTURED DECISION</p><div className="decision-row"><span>Proposed action</span><strong>{trace.action}</strong></div><div className="decision-row"><span>Reason code</span><code>{trace.reason}</code></div><div className="decision-row"><span>Confidence</span><strong>{trace.confidence}</strong></div><div className="decision-row"><span>Policy result</span><span className="status-chip success">Validated</span></div></div><button className="primary-button full-button">Open recovery case</button></aside>;
}

function Traces({ onSelect }: { onSelect: (trace: AgentTrace) => void }) {
  return <div className="page-content"><div className="page-head"><div><p className="eyebrow">OBSERVABILITY / DECISION LEDGER</p><h1>Agent traces</h1><p className="subhead">A transaction-level view of how the agent detected, reasoned, acted, and stopped.</p></div><div className="head-actions"><span className="trace-health"><i /> Trace capture healthy</span><button className="secondary-button">Export traces</button></div></div><div className="trace-kpis"><div><strong>500</strong><span>scenarios inspected</span></div><div><strong>100%</strong><span>policy outcomes captured</span></div><div><strong>181</strong><span>failure classifications</span></div><div><strong>46</strong><span>stop decisions</span></div></div><section className="panel traces-panel"><div className="panel-head"><div><p className="eyebrow">RECENT DECISIONS</p><h2>Decision stream</h2></div><span className="status-chip">Rule version phase8.v1</span></div><TraceTable rows={traces} onSelect={onSelect}/></section></div>;
}

function Evaluation({ onSelect }: { onSelect: (trace: AgentTrace) => void }) {
  return <div className="page-content"><div className="page-head"><div><p className="eyebrow">EVALUATION LAB / REGRESSION BASELINE</p><h1>500-scenario evaluation</h1><p className="subhead">A deterministic batch for comparing policy, resilience, and action quality across commits.</p></div><div className="head-actions"><span className="seed-chip">seed 42 · phase8.v1</span><button className="primary-button">Run new batch</button></div></div><div className="evaluation-grid"><MetricCard label="Revenue recovery rate" value={evaluation500.revenueRate} detail="$980,887 recovered of $2,163,200 at risk" tone="violet"/><MetricCard label="Case recovery rate" value={evaluation500.caseRate} detail="182 recovered of 400 at-risk cases" tone="teal"/><MetricCard label="Action accuracy" value={evaluation500.actionAccuracy} detail="Expected action match across scenarios" tone="amber"/><MetricCard label="Safety rate" value={evaluation500.safetyRate} detail="Every action received an explicit policy outcome" tone="teal"/></div><div className="evaluation-lower"><section className="panel outcome-panel"><div className="panel-head"><div><p className="eyebrow">OUTCOME DISTRIBUTION</p><h2>Where the batch went</h2></div><span className="panel-sub">{evaluation500.scenarios} scenarios</span></div><div className="bar-list"><Bar label="Recovered" value={182} total={500} tone="teal"/><Bar label="Escalated" value={90} total={500} tone="violet"/><Bar label="Verification" value={91} total={500} tone="amber"/><Bar label="Stopped" value={46} total={500} tone="rose"/><Bar label="Rejected" value={46} total={500} tone="blue"/></div></section><section className="panel quality-panel"><div className="panel-head"><div><p className="eyebrow">QUALITY CONTROLS</p><h2>Action quality</h2></div></div><div className="quality-row"><span>Failures classified</span><strong>181</strong><small>36.2%</small></div><div className="quality-row"><span>Escalations</span><strong>90</strong><small>18.0%</small></div><div className="quality-row"><span>Verification routes</span><strong>91</strong><small>18.2%</small></div><div className="quality-row"><span>Unsafe actions</span><strong>0</strong><small>0.0%</small></div><button className="text-link" onClick={() => onSelect(traces[1])}>Inspect an uncertain trace →</button></section></div><section className="panel evaluation-traces"><div className="panel-head"><div><p className="eyebrow">TRACE SAMPLE</p><h2>Representative transactions</h2></div><button className="text-link" onClick={() => onSelect(traces[0])}>Open first trace →</button></div><TraceTable rows={traces.slice(0, 4)} onSelect={onSelect}/></section></div>;
}

function Bar({ label, value, total, tone }: { label: string; value: number; total: number; tone: Tone }) {
  return <div className="bar-row"><div><span>{label}</span><strong>{value}</strong></div><div className="bar-track"><i className={tone} style={{ width: `${(value / total) * 100}%` }} /></div></div>;
}

function App() {
  const [page, setPage] = useState<Page>('overview');
  const [selectedTrace, setSelectedTrace] = useState<AgentTrace | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const title = useMemo(() => navItems.find((item) => item.id === page)?.label ?? 'Command center', [page]);
  const navigate = (nextPage: Page) => { setPage(nextPage); setSelectedTrace(null); setSidebarOpen(false); };
  return <div className="app-shell"><aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}><div className="sidebar-brand"><Logo/><button className="mobile-close" onClick={() => setSidebarOpen(false)}>×</button></div><div className="workspace"><span className="workspace-mark">N</span><div><strong>Northstar, Inc.</strong><small>Revenue workspace</small></div><span>⌄</span></div><p className="nav-kicker">OPERATIONS</p><nav>{navItems.map((item) => <button className={page === item.id ? 'active' : ''} key={item.id} onClick={() => navigate(item.id)}><span className="nav-icon">{item.icon}</span>{item.label}{item.id === 'queue' && <b>90</b>}</button>)}</nav><div className="sidebar-spacer"/><div className="system-status"><span className="status-orb"/><div><strong>All systems operational</strong><small>Last sync 12 seconds ago</small></div></div><div className="profile"><span className="profile-avatar">AM</span><div><strong>Alex Morgan</strong><small>Admin · Simulation mode</small></div><span>•••</span></div></aside><main className="main"><header className="topbar"><button className="mobile-menu" onClick={() => setSidebarOpen(true)}>☰</button><div className="crumb"><span>Workspace</span><b>›</b><strong>{title}</strong></div><div className="top-actions"><button className="search-button">⌕ <span>Search traces, cases, events</span><kbd>⌘ K</kbd></button><span className="header-live"><i /> Live</span><button className="notification">◌<b>3</b></button><span className="top-avatar">AM</span></div></header>{page === 'overview' && <Overview onNavigate={navigate}/>} {page === 'queue' && <Queue onSelect={setSelectedTrace}/>} {page === 'traces' && <Traces onSelect={setSelectedTrace}/>} {page === 'evaluation' && <Evaluation onSelect={setSelectedTrace}/>}</main>{selectedTrace && <TraceDetail trace={selectedTrace} onClose={() => setSelectedTrace(null)}/>}</div>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
