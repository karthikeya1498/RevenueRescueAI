import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

function App() {
  return <main className="shell"><p className="eyebrow">RevenueRescue AI</p><h1>Engineering foundation online.</h1><p className="lede">The recovery workflow is intentionally not implemented in Phase 1. This surface will become the command center after the data, state, policy, and evaluation foundations are verified.</p><div className="status"><span className="dot" />Phase 1 · Foundation</div></main>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
