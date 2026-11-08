import React, { useCallback, useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import {
  Area, AreaChart, CartesianGrid, ComposedChart, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from 'recharts';

const CUSTOMER_NAV = [
  ['overview', 'Overview', '◫'], ['day', 'Day explorer', '⌁'], ['heatmap', 'Usage heatmap', '▦'],
  ['alerts', 'Alerts', '◇'], ['story', 'Energy story', '✳'], ['appliances', 'Appliances', '▤'], ['settings', 'Privacy & settings', '⚙'],
];
const STAFF_NAV = [['queue', 'Review queue', '▣'], ['protection', 'Protection', '◈']];
const fmt = (value, digits = 1) => Number(value ?? 0).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
const dayLabel = (value) => new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
const PREF_KEY = 'sme.pulse.preferences.v2';
const LEGACY_PREF_KEY = 'sme.pulse.preferences.v1';
const DEFAULT_PREFS = {
  soundEnabled: true, interactionSounds: true, alertChimes: true, volume: 0.22,
  reducedMotion: false, calmMode: false, energyRibbon: true, whatIfMorph: true,
  sharedTransitions: true, scrollReveals: true, countUpNumbers: true,
  haptics: true, undoToast: true,
};
const BOOLEAN_PREFS = Object.keys(DEFAULT_PREFS).filter((key) => key !== 'volume');
function normalizePrefs(value) {
  const source = value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  const merged = { ...DEFAULT_PREFS, ...source };
  BOOLEAN_PREFS.forEach((key) => { merged[key] = merged[key] === true; });
  const volume = Number(merged.volume);
  merged.volume = Number.isFinite(volume) ? Math.min(0.5, Math.max(0, volume)) : DEFAULT_PREFS.volume;
  return merged;
}
function readLocalFlag(key) { try { return localStorage.getItem(key) === '1'; } catch { return false; } }
function writeLocalFlag(key) { try { localStorage.setItem(key, '1'); } catch { /* Storage may be disabled; this prompt will simply not persist dismissal. */ } }
function readPrefs() {
  try {
    const current = localStorage.getItem(PREF_KEY);
    const legacy = current == null ? localStorage.getItem(LEGACY_PREF_KEY) : null;
    const parsed = JSON.parse(current ?? legacy ?? '{}');
    const normalized = normalizePrefs(parsed);
    if (current == null && legacy != null) localStorage.setItem(PREF_KEY, JSON.stringify(normalized));
    return normalized;
  } catch { return { ...DEFAULT_PREFS }; }
}
function PulseRing({ day }) {
  const slots = day?.intervals || [];
  const hours = Array.from({ length: 24 }, (_, hour) => {
    const rows = slots.slice(hour * 4, hour * 4 + 4);
    return { hour, kwh: rows.reduce((sum, row) => sum + (Number(row.energy_kwh) || 0), 0), count: rows.filter((row) => row.energy_kwh != null).length, flagged: rows.some((row) => row.flagged) };
  });
  const maximum = Math.max(...hours.map((hour) => hour.kwh), 0.01);
  const radius = 78; const circumference = 2 * Math.PI * radius; const step = circumference / 24; const gap = 3;
  const total = hours.reduce((sum, hour) => sum + hour.kwh, 0);
  const summary = `${fmt(total, 2)} kWh across 24 hours; ${hours.filter((hour) => hour.count > 0).length} hours contain readings; ${hours.filter((hour) => hour.flagged).length} hours include saved customer alerts.`;
  return <div className="pulse-ring-layout"><div className="pulse-ring-wrap"><svg className="pulse-ring" viewBox="0 0 200 200" role="group" aria-label={`Pulse Ring for ${day?.date || 'the selected day'}. ${summary}`}>
    <circle cx="100" cy="100" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="13" />
    {hours.map((hour) => { const length = hour.kwh > 0 ? (hour.kwh / maximum) * (step - gap) : 0; const label = `${String(hour.hour).padStart(2, '0')}:00, ${fmt(hour.kwh, 3)} kWh${hour.flagged ? ', detector alert' : ''}, ${hour.count} of 4 intervals`; return <circle key={hour.hour} className={`pulse-segment ${hour.flagged ? 'flagged' : ''}`} tabIndex="0" role="img" aria-label={label} cx="100" cy="100" r={radius} fill="none" stroke={hour.flagged ? '#c2410c' : '#7c93b5'} strokeWidth={hour.flagged ? 16 : 13} strokeLinecap={hour.flagged ? 'round' : 'butt'} strokeDasharray={`${length} ${circumference - length}`} strokeDashoffset={-(hour.hour / 24) * circumference} transform="rotate(-90 100 100)"><title>{label}</title></circle>; })}
    <text x="100" y="91" textAnchor="middle" className="pulse-total">{fmt(total, 1)}</text><text x="100" y="111" textAnchor="middle" className="pulse-unit">kWh · 24 HOURS</text>
  </svg><div className="pulse-anchors"><span>12 AM</span><span>6 AM</span><span>12 PM</span><span>6 PM</span></div></div><div className="pulse-detail"><div className="eyebrow">TODAY · {day?.date || 'No date'}</div><p>{summary}</p><div className="pulse-legend"><span><i className="normal"/>Recorded use</span><span><i className="flag"/>Saved detector alert</span></div><details className="pulse-details"><summary>Show hourly table</summary><div className="table-wrap"><table><caption>Hourly energy and reading coverage</caption><thead><tr><th>Hour</th><th>Energy (kWh)</th><th>Coverage</th><th>Alert</th></tr></thead><tbody>{hours.map((hour) => <tr key={hour.hour}><td>{String(hour.hour).padStart(2, '0')}:00</td><td>{fmt(hour.kwh, 3)}</td><td>{hour.count}/4</td><td>{hour.flagged ? 'Flagged' : '—'}</td></tr>)}</tbody></table></div></details></div></div>;
}
function WeeklyChart({ weekly }) {
  const [showTable, setShowTable] = useState(false);
  const values = weekly.map((item) => Number(item.total_kwh || 0));
  const sum = values.reduce((a, b) => a + b, 0); const minimum = Math.min(...values); const maximum = Math.max(...values);
  const summary = `Across ${weekly.length} recorded days, daily use ranges from ${fmt(minimum, 2)} to ${fmt(maximum, 2)} kWh. Displayed daily totals add to ${fmt(sum, 2)} kWh; missing intervals are not filled.`;
  return <article className="card"><div className="card-head"><div><h2>Daily consumption</h2><p>Recorded kWh per day · local time (Asia/Manila)</p></div><span className="pill">7 DAYS</span></div><div style={{ width: '100%', height: 220 }} role="img" aria-label={`Weekly daily energy totals. ${summary}`}><ResponsiveContainer><AreaChart data={weekly}><defs><linearGradient id="rechartsArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7c93b5" stopOpacity={0.25} /><stop offset="100%" stopColor="#7c93b5" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#2a3c52" strokeDasharray="4 4" vertical={false} /><XAxis dataKey="date" tickFormatter={dayLabel} stroke="#8fa3bb" fontSize={10} /><YAxis stroke="#8fa3bb" fontSize={10} /><Tooltip contentStyle={{ background: '#14253a', border: '1px solid #30445b', color: '#eef4fb' }} /><Area type="monotone" dataKey="total_kwh" stroke="#7c93b5" fill="url(#rechartsArea)" strokeWidth={2.5} /></AreaChart></ResponsiveContainer></div><p className="chart-summary">{summary}</p><div className="legend"><span>Meter readings</span><span>Missing intervals are not imputed</span></div><button className="btn secondary" aria-expanded={showTable} onClick={() => setShowTable((value) => !value)}>{showTable ? 'Hide table' : 'Show as a table'}</button>{showTable && <div className="table-wrap chart-table"><table><caption>Daily electricity totals</caption><thead><tr><th>Date</th><th>Energy (kWh)</th></tr></thead><tbody>{weekly.map((item) => <tr key={item.date}><td>{item.date}</td><td>{fmt(item.total_kwh, 3)}</td></tr>)}</tbody><tfoot><tr><th>Total</th><th>{fmt(sum, 3)} kWh</th></tr></tfoot></table></div>}</article>;
}
function HeatmapPanel({ data }) {
  const [showTable, setShowTable] = useState(false);
  const maximum = Math.max(...data.days.flatMap((day) => day.blocks), 0);
  const maxPoint = data.days.flatMap((day) => day.blocks.map((value, index) => ({ date: day.date, label: data.labels[index], value }))).sort((a, b) => b.value - a.value)[0];
  const summary = maxPoint ? `Highest six-hour block in this week: ${maxPoint.label} on ${dayLabel(maxPoint.date)}, ${fmt(maxPoint.value, 2)} kWh. Each cell shows a relative level and its recorded energy value.` : 'No readings are available for this period.';
  const levelFor = (value) => value === 0 ? 'L' : value <= maximum * .33 ? 'M' : value <= maximum * .66 ? 'H' : 'P';
  return <><article className="card"><div className="card-head"><div><h2>Daily profile by time block</h2><p>kWh totals · local time · partial days show received coverage</p></div><span className="pill">7 DAYS</span></div><div className="heatmap"><div />{data.labels.map((label) => <div className="heat-label heat-head" key={label}>{label}</div>)}{data.days.flatMap((day) => [<div key={`${day.date}-label`} className="heat-label">{dayLabel(day.date)}<br />{fmt(day.coverage_pct)}%</div>, ...day.blocks.map((value, index) => { const level = levelFor(value); return <div key={`${day.date}-${index}`} className={`heat-cell level-${level.toLowerCase()}`} title={`${data.labels[index]}: ${fmt(value)} kWh`} aria-label={`${dayLabel(day.date)}, ${data.labels[index]}: ${fmt(value)} kWh, level ${level}`}><span>{level}</span><small>{fmt(value)}</small></div>; })])}</div><div className="heat-legend"><span><b>L</b>Low</span><span><b>M</b>Medium</span><span><b>H</b>High</span><span><b>P</b>Peak</span></div><p className="chart-summary">{summary} Missing intervals remain absent and are not treated as zero-consumption observations.</p><button className="btn secondary" aria-expanded={showTable} onClick={() => setShowTable((value) => !value)}>{showTable ? 'Hide table' : 'Show as a table'}</button></article>{showTable && <div className="table-wrap chart-table"><table><caption>Six-hour usage totals by day</caption><thead><tr><th>Date</th>{data.labels.map((label) => <th key={label}>{label} (kWh)</th>)}<th>Coverage</th></tr></thead><tbody>{data.days.map((day) => <tr key={day.date}><th scope="row">{day.date}</th>{day.blocks.map((value, index) => <td key={index}>{fmt(value, 3)}</td>)}<td>{fmt(day.coverage_pct, 1)}%</td></tr>)}</tbody></table></div>}</>;
}
function PortalHome({ onOverview, onAlerts }) { return <><div className="page-head"><div><div className="eyebrow">SMART METER EXPLORER</div><h1>See what changed. Understand the numbers.</h1><p>A local workspace for exploring simulated 15-minute meter readings, transparent pattern alerts, and appliance-use estimates.</p></div></div><section className="card pulse-card home-hero"><div className="eyebrow">PULSE · LOCAL ENERGY INSIGHT</div><h2>Your electricity, easier to understand.</h2><p className="muted">The application turns stored interval readings into clear views without claiming to know more than the meter can show.</p><div className="btn-row"><button className="btn primary" onClick={onOverview}>Open sample portal</button><button className="btn secondary" onClick={onAlerts}>Review alerts</button></div></section><div className="notice info" style={{ marginTop: 16 }}>SAMPLE DATA: This local demonstration uses simulated readings. It is not an official Meralco site and is not endorsed by Meralco. Nothing here is live or real.</div></>;}


function App() {
  const [user, setUser] = useState(null);
  const [csrf, setCsrf] = useState('');
  const csrfRef = useRef('');
  const [page, setPage] = useState('overview');
  const [data, setData] = useState(null);
  const [screen, setScreen] = useState('loading');
  const [message, setMessage] = useState(null);
  const [authMode, setAuthMode] = useState('customer');
  const [preauth, setPreauth] = useState('');
  const [adminChallenge, setAdminChallenge] = useState('');
  const [consent, setConsent] = useState(null);
  const [busy, setBusy] = useState(false);
  const [pulseDay, setPulseDay] = useState(null);
  const [prefs, setPrefs] = useState(readPrefs);
  const prefsRef = useRef(prefs);
  prefsRef.current = prefs;
  const [showSoundPrompt, setShowSoundPrompt] = useState(false);
  const audioRef = useRef(null);
  const lastSoundAt = useRef(0);
  const pendingSound = useRef(null);
  const soundPromptRef = useRef(null);
  const soundPromptOpener = useRef(null);
  const seenAlertIds = useRef(null);
  const scrollPositions = useRef({});
  const loadRequestId = useRef(0);

  useEffect(() => { csrfRef.current = csrf; }, [csrf]);
  useEffect(() => {
    try { localStorage.setItem(PREF_KEY, JSON.stringify(normalizePrefs(prefs))); } catch { /* Browser storage can be unavailable; keep this session usable. */ }
    const systemReduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    document.documentElement.classList.toggle('calm-mode', !!prefs.calmMode);
    document.documentElement.classList.toggle('reduced-motion', !!prefs.reducedMotion || !!prefs.calmMode || systemReduced);
    document.documentElement.classList.toggle('shared-transitions', !!prefs.sharedTransitions && !prefs.reducedMotion && !prefs.calmMode && !systemReduced);
    document.documentElement.classList.toggle('scroll-reveals', !!prefs.scrollReveals && !prefs.reducedMotion && !prefs.calmMode && !systemReduced);
    document.querySelectorAll('#main-content .card').forEach((card) => card.classList.toggle('reveal-on-scroll', !!prefs.scrollReveals && !prefs.reducedMotion && !prefs.calmMode && !systemReduced));
  }, [prefs, page, data, busy]);
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!media) return undefined;
    const apply = () => {
      document.documentElement.classList.toggle('reduced-motion', !!prefsRef.current.reducedMotion || !!prefsRef.current.calmMode || media.matches);
      document.documentElement.classList.toggle('shared-transitions', !!prefsRef.current.sharedTransitions && !prefsRef.current.reducedMotion && !prefsRef.current.calmMode && !media.matches);
      document.documentElement.classList.toggle('scroll-reveals', !!prefsRef.current.scrollReveals && !prefsRef.current.reducedMotion && !prefsRef.current.calmMode && !media.matches);
      document.querySelectorAll('#main-content .card').forEach((card) => card.classList.toggle('reveal-on-scroll', !!prefsRef.current.scrollReveals && !prefsRef.current.reducedMotion && !prefsRef.current.calmMode && !media.matches));
    };
    media.addEventListener?.('change', apply);
    return () => media.removeEventListener?.('change', apply);
  }, []);
  useEffect(() => {
    const onVisibility = () => { if (document.hidden && audioRef.current?.state === 'running') audioRef.current.suspend().catch(() => {}); };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);
  useEffect(() => {
    if (screen === 'app' && page === 'overview' && user?.role === 'customer' && !prefsRef.current.soundEnabled && !readLocalFlag('sme.pulse.soundPromptAsked')) setShowSoundPrompt(true);
  }, [screen, page, user]);
  useEffect(() => {
    if (!showSoundPrompt) return undefined;
    soundPromptOpener.current = document.activeElement;
    const modal = soundPromptRef.current;
    const buttons = modal ? Array.from(modal.querySelectorAll('button')) : [];
    buttons[0]?.focus();
    const onKeyDown = (event) => {
      if (event.key === 'Escape') { writeLocalFlag('sme.pulse.soundPromptAsked'); setShowSoundPrompt(false); }
      if (event.key === 'Tab' && buttons.length) {
        if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[buttons.length - 1].focus(); }
        else if (!event.shiftKey && document.activeElement === buttons[buttons.length - 1]) { event.preventDefault(); buttons[0].focus(); }
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      requestAnimationFrame(() => {
        const target = soundPromptOpener.current?.isConnected ? soundPromptOpener.current : document.querySelector('#main-content h1');
        target?.focus?.({ preventScroll: true });
      });
    };
  }, [showSoundPrompt]);
  useEffect(() => {
    if (screen !== 'app' || busy) return;
    const saved = Number(scrollPositions.current[page] || 0);
    window.scrollTo({ top: saved, behavior: 'auto' });
    requestAnimationFrame(() => {
      const heading = document.querySelector('#main-content h1');
      if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus({ preventScroll: true }); }
    });
  }, [screen, page, busy, data]);

  const ensureAudioFromGesture = () => {
    const current = prefsRef.current;
    if (!current.soundEnabled || current.calmMode || document.hidden) return Promise.resolve();
    try { const Ctx = window.AudioContext || window.webkitAudioContext; if (!Ctx) return Promise.resolve(); if (!audioRef.current || audioRef.current.state === 'closed') audioRef.current = new Ctx(); if (audioRef.current.state === 'suspended') return audioRef.current.resume().then(() => undefined).catch(() => undefined); return Promise.resolve(); } catch { /* optional sound */ return Promise.resolve(); }
  };
  const playTone = (kind = 'tap', channel = 'interaction') => {
    const currentPrefs = prefsRef.current;
    if (!currentPrefs.soundEnabled || currentPrefs.calmMode || document.hidden || !audioRef.current) return;
    if (channel === 'interaction' && !currentPrefs.interactionSounds) return;
    if (channel === 'alert' && !currentPrefs.alertChimes) return;
    const now = performance.now();
    const remaining = 150 - (now - lastSoundAt.current);
    if (remaining > 0) {
      if (kind === 'tap') return;
      clearTimeout(pendingSound.current);
      pendingSound.current = setTimeout(() => { pendingSound.current = null; playTone(kind, channel); }, remaining);
      return;
    }
    lastSoundAt.current = now;
    if (audioRef.current.state !== 'running') return;
    const notes = {
      tap: [{ f: 1200, ms: 30, gain: .035 }],
      success: [{ f: 523, ms: 80, gain: .045 }, { f: 784, ms: 80, gain: .045, delay: .09 }],
      remove: [{ f: 440, ms: 80, gain: .035 }, { f: 330, ms: 80, gain: .035, delay: .09 }],
      error: [{ f: 180, ms: 120, gain: .045, wave: 'triangle' }],
      alert: [{ f: 880, ms: 90, gain: .055 }, { f: 660, ms: 100, gain: .055, delay: .11 }],
    }[kind] || [{ f: 1200, ms: 30, gain: .035 }];
    notes.forEach((note) => { const ctx = audioRef.current; const osc = ctx.createOscillator(); const gain = ctx.createGain(); const start = ctx.currentTime + (note.delay || 0); const end = start + note.ms / 1000; osc.type = note.wave || 'sine'; osc.frequency.setValueAtTime(note.f, start); gain.gain.setValueAtTime(0, start); gain.gain.linearRampToValueAtTime(note.gain * Math.min(.5, Math.max(0, currentPrefs.volume)), start + .008); gain.gain.exponentialRampToValueAtTime(.0001, end); osc.connect(gain); gain.connect(ctx.destination); osc.start(start); osc.stop(end + .01); });
  };
  const updatePrefs = (patch) => { const next = normalizePrefs({ ...prefsRef.current, ...patch }); prefsRef.current = next; setPrefs(next); };
  const handleAudioInteraction = (event) => {
    if (event?.target?.closest?.('.security-silent')) return;
    const currentPrefs = prefsRef.current;
    const interactive = event?.target?.closest?.('button,input[type=checkbox],input[type=range],select,[role=button]');
    if (interactive && currentPrefs.haptics && !currentPrefs.calmMode && !document.hidden && typeof navigator.vibrate === 'function') {
      try { navigator.vibrate(8); } catch { /* Haptics are an optional device capability. */ }
    }
    if (!currentPrefs.soundEnabled || currentPrefs.calmMode) return;
    const resumed = ensureAudioFromGesture();
    if (resumed && typeof resumed.then === 'function') resumed.then(() => playTone('tap', 'interaction')).catch(() => {});
    else playTone('tap', 'interaction');
  };
  const runSharedTransition = (callback) => {
    const current = prefsRef.current;
    const reduced = current.reducedMotion || current.calmMode || (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false);
    if (!current.sharedTransitions || reduced || typeof document.startViewTransition !== 'function') { callback(); return; }
    try {
      const transition = document.startViewTransition(() => flushSync(callback));
      transition.finished?.catch?.(() => {});
    } catch { callback(); }
  };

  const api = useCallback(async (path, options = {}) => {
    const headers = new Headers(options.headers || {});
    if (options.body !== undefined) headers.set('Content-Type', 'application/json');
    if (options.method && options.method !== 'GET' && csrfRef.current) headers.set('X-CSRF-Token', csrfRef.current);
    const response = await fetch(path, { ...options, headers, credentials: 'same-origin', cache: 'no-store' });
    const type = response.headers.get('content-type') || '';
    const result = type.includes('application/json') ? await response.json() : await response.text();
    const isMutation = String(options.method || 'GET').toUpperCase() !== 'GET';
    const silentSecurityAction = path.startsWith('/api/internal/safe-mode/');
    if (!response.ok) {
      if (isMutation && !silentSecurityAction) playTone('error');
      const detail = result?.error || {};
      const error = new Error(detail.message || `Request failed (${response.status}).`);
      error.code = detail.code || 'request_failed';
      error.requestId = detail.request_id || response.headers.get('X-Request-ID');
      error.status = response.status;
      throw error;
    }
    if (isMutation && !silentSecurityAction) playTone(String(options.method || '').toUpperCase() === 'DELETE' || /\/retire(?:\/|$)/.test(path) ? 'remove' : 'success');
    return result;
  }, []);

  const fail = (error) => setMessage({ type: 'error', text: `${error.message}${error.code ? ` [${error.code}]` : ''}${error.requestId ? ` · ${error.requestId}` : ''}` });

  const startConsent = useCallback(async () => {
    try {
      const current = await api('/api/consent');
      setConsent(current); setMessage(null); setScreen('consent');
    } catch (error) { fail(error); setScreen('unavailable'); }
  }, [api]);

  const loadPage = useCallback(async (nextPage) => {
    const requestId = ++loadRequestId.current;
    scrollPositions.current[page] = window.scrollY;
    if (!user) { setScreen('login'); return; }
    if (user.must_change_password) { setScreen('password'); return; }
    runSharedTransition(() => { setPage(nextPage); setScreen('app'); setMessage(null); setData(null); setPulseDay(null); setBusy(true); });
    try {
      if (user.role === 'customer' && nextPage !== 'settings') {
        const current = await api('/api/session');
        if (requestId !== loadRequestId.current) return;
        if (current.consent_required) { const consentResult = await api('/api/consent'); if (requestId !== loadRequestId.current) return; setConsent(consentResult); setMessage(null); setScreen('consent'); return; }
      }
      const pathByPage = {
        overview: '/api/customer/overview', day: '/api/customer/day', heatmap: '/api/customer/heatmap?days=7',
        alerts: '/api/customer/alerts', story: '/api/customer/story', appliances: '/api/customer/appliances',
        settings: '/api/customer/settings', queue: '/api/internal/queue', protection: '/api/internal/protection',
      };
      const result = await api(pathByPage[nextPage] || pathByPage.overview);
      if (requestId !== loadRequestId.current) return;
      if (nextPage === 'overview') {
        const day = await api(`/api/customer/day?day=${encodeURIComponent(result.period.end)}`);
        if (requestId !== loadRequestId.current) return;
        setPulseDay(day);
        const ids = new Set((result.alerts || []).map((alert) => String(alert.id)));
        if (seenAlertIds.current && [...ids].some((id) => !seenAlertIds.current.has(id))) playTone('alert', 'alert');
        seenAlertIds.current = ids;
      } else if (nextPage === 'alerts') {
        const ids = new Set((result.alerts || []).map((alert) => String(alert.id)));
        if (seenAlertIds.current && [...ids].some((id) => !seenAlertIds.current.has(id))) playTone('alert', 'alert');
        seenAlertIds.current = ids;
      }
      if (requestId !== loadRequestId.current) return;
      setData(result);
    } catch (error) {
      if (requestId !== loadRequestId.current) return;
      if (error.status === 401) { setUser(null); setCsrf(''); csrfRef.current = ''; setData(null); setScreen('login'); }
      else if (error.code === 'consent_required') { try { const consentResult = await api('/api/consent'); if (requestId === loadRequestId.current) { setConsent(consentResult); setMessage(null); setScreen('consent'); } } catch (consentError) { if (requestId === loadRequestId.current) fail(consentError); } }
      else fail(error);
    } finally {
      if (requestId === loadRequestId.current) setBusy(false);
    }
  }, [api, startConsent, user, page, runSharedTransition]);

  // Enter a workspace using the role returned by the server response. Do not
  // depend on React state having re-rendered first: login/session transitions
  // and state updates are asynchronous.
  const enterWorkspace = useCallback(async (current) => {
    const requestId = ++loadRequestId.current;
    setUser(current.user);
    setCsrf(current.csrf_token);
    csrfRef.current = current.csrf_token;
    if (current.user.must_change_password) { setScreen('password'); return; }
    if (current.user.role === 'customer' && current.consent_required) {
      await startConsent();
      return;
    }
    const target = current.user.role === 'customer' ? 'overview' : 'queue';
    const endpoint = current.user.role === 'customer' ? '/api/customer/overview' : '/api/internal/queue';
    runSharedTransition(() => { setPage(target); setScreen('app'); setBusy(true); setData(null); setPulseDay(null); setMessage(null); });
    try {
      const result = await api(endpoint);
      if (requestId !== loadRequestId.current) return;
      if (current.user.role === 'customer') {
        const day = await api(`/api/customer/day?day=${encodeURIComponent(result.period.end)}`);
        if (requestId !== loadRequestId.current) return;
        setPulseDay(day);
        seenAlertIds.current = new Set((result.alerts || []).map((alert) => String(alert.id)));
      }
      if (requestId !== loadRequestId.current) return;
      setData(result);
    } catch (error) {
      if (requestId !== loadRequestId.current) return;
      if (error.status === 401) { setUser(null); setCsrf(''); csrfRef.current = ''; setData(null); setScreen('login'); }
      else fail(error);
    } finally { if (requestId === loadRequestId.current) setBusy(false); }
  }, [api, startConsent, runSharedTransition]);

  const refreshSession = useCallback(async () => {
    const current = await api('/api/session');
    if (!current.authenticated) { setUser(null); setCsrf(''); csrfRef.current = ''; setScreen('login'); return; }
    await enterWorkspace(current);
  }, [api, enterWorkspace]);

  useEffect(() => {
    let active = true;
    api('/api/session').then(async (current) => {
      if (!active) return;
      if (!current.authenticated) { setScreen('login'); return; }
      await enterWorkspace(current);
    }).catch((error) => { if (active) { fail(error); setScreen('unavailable'); } });
    return () => { active = false; };
  // Initial session check only. Later navigations use loadPage.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function login(event) {
    event.preventDefault(); if (prefsRef.current.soundEnabled) ensureAudioFromGesture(); setBusy(true); setMessage(null);
    const form = new FormData(event.currentTarget);
    const username = String(form.get('username') || '').trim();
    const password = String(form.get('password') || '');
    try {
      let pre = preauth;
      if (!pre) { const result = await api('/api/auth/preflight'); pre = result.csrf_token; setPreauth(pre); }
      setCsrf(pre); csrfRef.current = pre;
      if (authMode === 'customer') {
        await api('/api/auth/customer/login', { method: 'POST', body: JSON.stringify({ username, password }) });
        setPreauth(''); await refreshSession();
      } else {
        const result = await api('/api/auth/admin/start', { method: 'POST', body: JSON.stringify({ username, password }) });
        setAdminChallenge(result.challenge_id); setMessage({ type: 'success', text: `${result.message} Check the local server terminal.` });
      }
    } catch (error) { setPreauth(''); setAdminChallenge(''); fail(error); }
    finally { setBusy(false); }
  }

  async function verifyAdmin(event) {
    event.preventDefault(); if (prefsRef.current.soundEnabled) ensureAudioFromGesture(); setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await api('/api/auth/admin/verify', { method: 'POST', body: JSON.stringify({ challenge_id: adminChallenge, code: form.get('code') }) });
      setUser(result.user); setCsrf(result.csrf_token); csrfRef.current = result.csrf_token;
      setPreauth(''); setAdminChallenge(''); await refreshSession();
    } catch (error) { fail(error); setAdminChallenge(''); }
    finally { setBusy(false); }
  }

  async function changePassword(event) {
    event.preventDefault(); if (prefsRef.current.soundEnabled) ensureAudioFromGesture(); setBusy(true);
    const form = new FormData(event.currentTarget);
    if (form.get('next') !== form.get('confirm')) { setMessage({ type: 'error', text: 'The new passphrases do not match.' }); setBusy(false); return; }
    try {
      const result = await api('/api/auth/password/change', { method: 'POST', body: JSON.stringify({ current_password: form.get('current'), new_password: form.get('next') }) });
      setCsrf(result.csrf_token); csrfRef.current = result.csrf_token; await refreshSession();
    } catch (error) { fail(error); }
    finally { setBusy(false); }
  }

  async function saveConsent(event) {
    event.preventDefault(); if (prefsRef.current.soundEnabled) ensureAudioFromGesture(); setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await api('/api/consent', { method: 'POST', body: JSON.stringify({ text_version: consent.version, request_id: crypto.randomUUID(), required_analytics: form.get('required') === 'on', push_alerts: form.get('push') === 'on', sms_alerts: form.get('sms') === 'on' }) });
      if (!result.analytics_unlocked) throw new Error('Consent did not unlock analytics. Refresh and review consent status.');
      await loadPage('overview');
    } catch (error) { fail(error); await startConsent(); }
    finally { setBusy(false); }
  }

  async function signOut() {
    loadRequestId.current += 1;
    try { await api('/api/auth/logout', { method: 'POST', body: JSON.stringify({}) }); } catch { /* Session may already have expired. */ }
    setUser(null); setCsrf(''); csrfRef.current = ''; setPreauth(''); setAdminChallenge(''); setData(null); setPulseDay(null); seenAlertIds.current = null; setMessage(null); setScreen('login');
  }

  const changePage = (next) => loadPage(next);

  if (screen === 'loading') return <main className="boot"><span className="mark">SME</span><p>Starting local workspace…</p></main>;
  if (screen === 'unavailable') return <div className="screen-center"><section className="card wide-card"><span className="mark">SME</span><div className="eyebrow" style={{ marginTop: 25 }}>LOCAL SETUP REQUIRED</div><h1 style={{ fontSize: 30 }}>The workspace is not ready yet.</h1><p className="muted">{message?.text || 'The local API or database is unavailable.'}</p><div className="notice info">Start the local MySQL service, apply migrations, seed the simulated dataset, then start the application on 127.0.0.1.</div><button className="btn secondary" onClick={() => location.reload()}>Retry connection</button></section></div>;
  if (screen === 'login') return <div className="login-wrap" onClickCapture={handleAudioInteraction}>
    <section className="hero"><div className="brand"><span className="mark">SME</span><div><div className="brand-title">SMART METER EXPLORER</div><span className="brand-sub">LOCAL ENERGY INTELLIGENCE · V2.0</span></div></div><div className="eyebrow" style={{ marginTop: 58 }}>A clearer view of your energy</div><h1>Understand your usage.<br /><span style={{ color: 'var(--cyan)' }}>Spot what changes.</span></h1><p>Explore 15-minute electricity readings, learn how usage changes through the week, and review transparent alerts. This build runs locally and uses simulated meter data only.</p><div className="pulse-line" aria-hidden="true"><svg viewBox="0 0 420 48"><path d="M0 25 H95 L112 25 L127 8 L143 40 L159 18 L172 25 H245 L260 25 L275 14 L289 34 L304 25 H420" /></svg></div><div className="feature-list"><span>15-minute usage exploration and data coverage</span><span>Explainable alerts with transparent provenance</span><span>Local storage, consent controls and audit trail</span></div></section>
    <section className="login-card"><h2>Welcome back</h2><p>Sign in to your local demonstration workspace.</p><div className="login-switch"><button className={authMode === 'customer' ? 'active' : ''} onClick={() => { setAuthMode('customer'); setAdminChallenge(''); }}>Customer</button><button className={authMode === 'internal' ? 'active' : ''} onClick={() => { setAuthMode('internal'); setAdminChallenge(''); }}>Staff portal</button></div>
      {adminChallenge ? <form onSubmit={verifyAdmin} className="grid" style={{ gap: 13 }}><p className="muted small">A one-time code was printed in the local server terminal.</p><div className="field"><label>6-digit one-time code</label><input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength="6" required /></div><button className="btn primary" disabled={busy}>Verify one-time code →</button></form> : <form onSubmit={login} className="grid" style={{ gap: 13 }}><div className="field"><label>Username</label><input name="username" autoComplete="username" required maxLength="80" /></div><div className="field"><label>Passphrase</label><input name="password" type="password" autoComplete="current-password" required maxLength="1024" /></div><button className="btn primary" disabled={busy}>Continue →</button></form>}
      {message && <div className={`notice ${message.type}`} role={message.type === 'error' ? 'alert' : 'status'} aria-live={message.type === 'error' ? 'assertive' : 'polite'}>{message.text}</div>}<div className="footer-note">Generated account passphrases are printed once during local demo setup. Staff sign-in also requires a one-time code printed in the server terminal.</div>
    </section>
  </div>;

  if (screen === 'password') return <div className="screen-center" onClickCapture={handleAudioInteraction}><section className="card wide-card"><div className="brand"><span className="mark">SME</span><div><div className="brand-title">SECURE YOUR ACCOUNT</div><span className="brand-sub">FIRST SIGN-IN REQUIRED</span></div></div><div className="eyebrow" style={{ marginTop: 30 }}>One-time setup</div><h1 style={{ fontSize: 30 }}>Create a new passphrase</h1><p className="muted small">Use at least 15 characters. Temporary credentials must be changed before using the workspace.</p>{message && <div className="notice error">{message.text}</div>}<form onSubmit={changePassword} className="grid" style={{ maxWidth: 480, gap: 14, marginTop: 22 }}><div className="field"><label>Current passphrase</label><input name="current" type="password" autoComplete="current-password" required /></div><div className="field"><label>New passphrase (15+ characters)</label><input name="next" type="password" minLength="15" autoComplete="new-password" required /></div><div className="field"><label>Confirm new passphrase</label><input name="confirm" type="password" minLength="15" autoComplete="new-password" required /></div><button className="btn primary" disabled={busy}>Update passphrase →</button></form></section></div>;

  if (screen === 'consent') return <div className="screen-center" onClickCapture={handleAudioInteraction}><section className="card wide-card"><div className="brand"><span className="mark">SME</span><div><div className="brand-title">SMART METER EXPLORER</div><span className="brand-sub">PRIVACY AND CONSENT</span></div></div><div className="eyebrow" style={{ marginTop: 30 }}>Before you continue</div><h1 style={{ fontSize: 30 }}>Your data. Your choice.</h1><p className="muted small">Review what this local demonstration stores. Required permission unlocks usage screens. Optional notification settings are mock-only and nothing is sent.</p><div className="consent-text">{consent?.text}{'\n\n'}Version {consent?.version} · SHA-256 {consent?.text_hash?.slice(0, 18)}…</div>{message && <div className="notice error">{message.text}</div>}<form onSubmit={saveConsent} className="grid" style={{ gap: 15 }}><label className="check"><input name="required" type="checkbox" required /><span><strong>Required:</strong> {consent?.required?.label}. Needed to open the dashboard. You can withdraw later in Privacy & settings.</span></label>{consent?.optional?.map((o) => <label className="check" key={o.purpose}><input name={o.purpose === 'push_alerts' ? 'push' : 'sms'} type="checkbox" /><span>{o.label}. Optional. These channels are simulated only and are never sent.</span></label>)}<div className="btn-row"><button className="btn primary" disabled={busy}>Agree and continue →</button><button type="button" className="btn secondary" onClick={signOut}>Sign out</button></div></form><div className="footer">Consent is stored locally as an append-only decision with version, text hash and timestamp.</div></section></div>;

  const nav = user?.role === 'customer' ? CUSTOMER_NAV : STAFF_NAV;
  return <>
    <header className="topbar" onClickCapture={handleAudioInteraction}><div className="brand"><span className="mark">SME</span><div><div className="brand-title">SMART METER EXPLORER</div><span className="brand-sub">LOCAL ENERGY INTELLIGENCE</span></div></div><div className="top-actions"><button className="btn secondary home-shortcut" onClick={() => { scrollPositions.current[page] = window.scrollY; runSharedTransition(() => { setData(null); setPulseDay(null); setPage('home'); setMessage(null); }); }}>Back to home</button>{user?.role === 'customer' && <button className="btn secondary settings-shortcut" onClick={() => changePage('settings')}>Settings</button>}<span className="badge sim" aria-label="All data shown is simulated">● SIMULATED DATA</span><span className="pill">{user?.username} · {user?.role}</span><button className="btn secondary sound-quick" onClick={(event) => { event.stopPropagation(); const enabled = !prefs.soundEnabled; updatePrefs({ soundEnabled: enabled }); if (enabled) { const ready = ensureAudioFromGesture(); if (ready?.then) ready.then(() => setTimeout(() => playTone('tap'), 0)); } }} aria-label="Toggle interface sounds" aria-pressed={prefs.soundEnabled && !prefs.calmMode}>{prefs.soundEnabled && !prefs.calmMode ? 'Sound on' : 'Sound off'}</button><button className="btn secondary" onClick={signOut}>Sign out</button></div></header>
    <div className="shell" onClickCapture={handleAudioInteraction}><aside className="sidebar"><div className="side-label">{user?.role === 'customer' ? 'Your workspace' : 'Internal workspace'}</div><nav className="nav" aria-label="Main navigation">{nav.map(([id, label, icon]) => <button key={id} onClick={() => { scrollPositions.current[page] = window.scrollY; changePage(id); }} className={page === id ? 'active' : ''} aria-current={page === id ? 'page' : undefined}><span className="nav-icon" aria-hidden="true">{icon}</span>{label}</button>)}</nav><div className="side-note"><strong style={{ color: '#dce9f7' }}>Local-only demo</strong><br />All meter readings and model benchmarks in this workspace are synthetic. No live Meralco feed is connected.</div></aside>
      <main className="content" id="main-content" tabIndex="-1">{message && <div className={`notice ${message.type}`} role={message.type === 'error' ? 'alert' : 'status'} aria-live={message.type === 'error' ? 'assertive' : 'polite'}>{message.text}</div>}{busy && <div className="small muted" role="status">Updating workspace…</div>}<div className="screen-view" key={page}>{page === 'home' ? <PortalHome onOverview={() => changePage('overview')} onAlerts={() => changePage('alerts')} /> : busy && !data ? <LoadingPanel /> : renderCurrentPage({ page, data, pulseDay, api, csrf, setCsrf, setMessage, loadPage, setData, user, prefs, updatePrefs, ensureAudioFromGesture, playTone, runSharedTransition })}</div><div className="footer">Smart Meter Explorer V2 · Synthetic meter data · Local database · No cloud services · Never use this build for billing or service decisions.</div></main>
    </div>
    {showSoundPrompt && <div className="pulse-prompt-backdrop"><section ref={soundPromptRef} className="pulse-prompt" role="dialog" aria-modal="true" aria-labelledby="sound-prompt-title" aria-describedby="sound-prompt-copy"><div className="eyebrow">A small preference</div><h2 id="sound-prompt-title">Would you like interface sounds?</h2><p id="sound-prompt-copy">Optional quiet feedback for taps and saved actions. Sound is enabled at a low level on new installations and can always be muted.</p><div className="btn-row"><button className="btn primary" onClick={() => { writeLocalFlag('sme.pulse.soundPromptAsked'); updatePrefs({ soundEnabled: true }); const ready = ensureAudioFromGesture(); setShowSoundPrompt(false); if (ready?.then) ready.then(() => setTimeout(() => playTone('success', 'test'), 0)); }}>Enable sounds</button><button className="btn secondary" onClick={() => { writeLocalFlag('sme.pulse.soundPromptAsked'); setShowSoundPrompt(false); }}>Keep muted</button></div></section></div>}
  </>;
}

function PageHead({ kicker, title, description, children }) {
  return <div className="page-head"><div><div className="eyebrow">{kicker}</div><h1>{title}</h1><p>{description}</p></div>{children && <div className="btn-row">{children}</div>}</div>;
}
function LoadingPanel() {
  return <section className="loading-panel" role="status" aria-label="Loading page content"><div className="skeleton-block skeleton-heading" /><div className="grid kpis">{Array.from({ length: 4 }, (_, index) => <div className="skeleton-block skeleton-kpi" key={index} />)}</div><div className="skeleton-block skeleton-panel" /></section>;
}
function CountUpMetric({ value, digits = 1, suffix = '' }) {
  const [display, setDisplay] = useState(Number(value) || 0);
  useEffect(() => {
    const target = Number(value);
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    if (!Number.isFinite(target) || reduced) { setDisplay(Number.isFinite(target) ? target : 0); return undefined; }
    const started = performance.now(); const duration = 560; let frame = 0;
    setDisplay(0);
    const tick = (now) => {
      const progress = Math.min(1, (now - started) / duration);
      const eased = 1 - ((1 - progress) ** 3);
      setDisplay(target * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, digits]);
  return <><span aria-hidden="true">{fmt(display, digits)}{suffix}</span><span className="sr-only">{fmt(value, digits)}{suffix}</span></>;
}
function Kpi({ label, value, foot, metricValue, metricSuffix = '', metricDigits = 1, countUp = false }) {
  const showCount = countUp && Number.isFinite(Number(metricValue));
  return <article className="card reveal-on-scroll"><div className="kpi-label">{label}</div><div className="kpi-value">{showCount ? <CountUpMetric value={metricValue} digits={metricDigits} suffix={metricSuffix} /> : value}</div><div className="kpi-foot">{foot}</div></article>;
}
function EnergyRibbon({ intervals = [], date }) {
  const [selectedHour, setSelectedHour] = useState(0);
  const hours = Array.from({ length: 24 }, (_, hour) => {
    const records = intervals.slice(hour * 4, hour * 4 + 4);
    return { hour, kwh: records.reduce((sum, row) => sum + (row.energy_kwh == null ? 0 : Number(row.energy_kwh) || 0), 0), received: records.filter((row) => row.energy_kwh != null).length, flagged: records.filter((row) => row.flagged).length };
  });
  const maximum = Math.max(...hours.map((item) => item.kwh), 0);
  const selected = hours[selectedHour] || hours[0];
  return <article className="card energy-ribbon-panel reveal-on-scroll"><div className="card-head"><div><h2>Energy Ribbon</h2><p>24-hour timeline · select an hour to inspect its four 15-minute intervals</p></div><span className="pill">{date}</span></div><div className="energy-ribbon" role="group" aria-label="Hourly energy timeline">{hours.map((hour) => { const scale = maximum > 0 ? hour.kwh / maximum : 0; return <button type="button" key={hour.hour} className={`energy-ribbon-hour ${selectedHour === hour.hour ? 'active' : ''} ${hour.flagged ? 'flagged' : ''}`} aria-label={`${String(hour.hour).padStart(2, '0')}:00, ${fmt(hour.kwh, 3)} kilowatt-hours, ${hour.received} of 4 readings${hour.flagged ? `, ${hour.flagged} flagged intervals` : ''}`} aria-pressed={selectedHour === hour.hour} onClick={() => setSelectedHour(hour.hour)}><span className="energy-ribbon-track"><span className="energy-ribbon-fill" style={{ transform: `scaleY(${scale})` }} /></span><small>{hour.hour % 6 === 0 ? `${String(hour.hour).padStart(2, '0')}` : ''}</small></button>; })}</div><label className="energy-ribbon-scrubber" htmlFor="energy-ribbon-hour"><span>Selected hour</span><input id="energy-ribbon-hour" type="range" min="0" max="23" step="1" value={selectedHour} onChange={(event) => setSelectedHour(Number(event.target.value))} /><output>{String(selectedHour).padStart(2, '0')}:00</output></label><p className="chart-summary" aria-live="polite">{String(selected.hour).padStart(2, '0')}:00 — {fmt(selected.kwh, 3)} kWh recorded · {selected.received}/4 intervals received · {selected.flagged} flagged intervals. Missing readings are not interpreted as zero-consumption observations.</p></article>;
}
function WhatIfPanel({ appliances = [] }) {
  const [selectedId, setSelectedId] = useState(appliances[0]?.id || '');
  const selected = appliances.find((item) => item.id === selectedId) || appliances[0];
  const [hours, setHours] = useState(Number(selected?.hours_per_day || 0));
  useEffect(() => { setHours(Number(selected?.hours_per_day || 0)); }, [selected?.id, selected?.hours_per_day]);
  if (!selected) return null;
  const otherEstimate = appliances.filter((item) => item.id !== selected.id).reduce((sum, item) => sum + Number(item.declared_kwh_per_week || 0), 0);
  const currentItem = Number(selected.declared_kwh_per_week || 0);
  const nextItem = (Number(selected.rated_power_w) / 1000) * Number(selected.quantity) * (Number(selected.duty_pct) / 100) * Math.min(24, Math.max(0, hours)) * Number(selected.days_per_week);
  const currentTotal = otherEstimate + currentItem;
  const nextTotal = otherEstimate + nextItem;
  const currentShare = currentTotal > 0 ? currentItem / currentTotal : 0;
  const nextShare = nextTotal > 0 ? nextItem / nextTotal : 0;
  const delta = nextItem - currentItem;
  return <article className="card what-if-panel reveal-on-scroll"><div className="card-head"><div><h2>What-if appliance preview</h2><p>Explore a schedule change without saving or changing your appliance record.</p></div><span className="pill">LOCAL SIMULATION</span></div><div className="what-if-controls"><div className="field"><label htmlFor="what-if-appliance">Appliance</label><select id="what-if-appliance" value={selected.id} onChange={(event) => setSelectedId(event.target.value)}>{appliances.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div><div className="field"><label htmlFor="what-if-hours">Hours per day · {fmt(hours, 2)} h</label><input id="what-if-hours" type="range" min="0" max="24" step="0.25" value={hours} onChange={(event) => setHours(Number(event.target.value))} /></div></div><div className="what-if-comparison"><div><span>Current listed estimate</span><strong>{fmt(currentItem, 2)} kWh/week</strong><div className="what-if-bar"><span style={{ transform: `scaleX(${currentShare})` }} /></div></div><div><span>What-if estimate</span><strong>{fmt(nextItem, 2)} kWh/week</strong><div className="what-if-bar"><span className="scenario" style={{ transform: `scaleX(${nextShare})` }} /></div></div></div><div className="stat-row"><span>Estimated weekly change</span><strong className={delta > 0.005 ? 'up' : delta < -0.005 ? 'down' : ''}>{delta > 0 ? '+' : ''}{fmt(delta, 2)} kWh</strong></div><p className="small muted">This is a calculation from the nameplate rating, quantity, duty factor, and entered schedule. It is not a measured appliance load and does not change saved data.</p></article>;
}
function Empty({ text }) { return <div className="empty">{text}</div>; }
function AlertList({ alerts = [] }) { return alerts.length ? <div className="alert-list">{alerts.map((a) => <div className="alert-item" key={a.id}><span className={`alert-dot ${a.tier}`} /><div><div className="alert-title">{a.title || a.type || 'Usage pattern'}</div><div className="alert-copy">{a.message || a.reason || ''}</div></div><span className="alert-tier">{a.tier}</span></div>)}</div> : <Empty text="No customer alerts in this sample period." />; }

function renderCurrentPage(ctx) {
  const { page, data, pulseDay, api, setMessage, loadPage, setData, user, prefs, updatePrefs, ensureAudioFromGesture, playTone, runSharedTransition } = ctx;
  const countUpEnabled = prefs.countUpNumbers && !prefs.reducedMotion && !prefs.calmMode;
  if (page === 'home') return <PortalHome onOverview={() => loadPage('overview')} onAlerts={() => loadPage('alerts')} />;
  if (!data) return <Empty text="No data loaded." />;
  if (page === 'overview') {
    const change = data.change_pct == null ? 'Not enough comparable coverage' : `${data.change_pct > 0 ? '+' : ''}${fmt(data.change_pct)}% vs previous week`;
    return <><PageHead kicker="CUSTOMER OVERVIEW" title="Your energy at a glance" description={`Last 7 days · ${data.period.start} to ${data.period.end} · Synthetic meter readings`} /><section className="grid kpis"><Kpi label="Recorded usage · 7 days" value={`${fmt(data.total_kwh)} kWh`} foot={`${data.period.start} — ${data.period.end}`} metricValue={data.total_kwh} metricSuffix=" kWh" countUp={countUpEnabled} /><Kpi label="Change vs previous week" value={data.change_pct == null ? '—' : `${data.change_pct > 0 ? '+' : ''}${fmt(data.change_pct)}%`} foot={change} /><Kpi label="Reading coverage" value={`${fmt(data.coverage_pct)}%`} foot="Expected 672 intervals · 15 minutes each" metricValue={data.coverage_pct} metricSuffix="%" countUp={countUpEnabled} /><Kpi label="Average demand" value={`${fmt(data.average_power_kw, 2)} kW`} foot="Calculated from recorded energy" metricValue={data.average_power_kw} metricSuffix=" kW" metricDigits={2} countUp={countUpEnabled} /></section>{prefs.energyRibbon && <EnergyRibbon intervals={pulseDay?.intervals || []} date={pulseDay?.date || data.period.end} />}<article className="card pulse-card"><div className="card-head"><div><div className="eyebrow">PULSE RING</div><h2>Today's energy heartbeat</h2><p>24-hour radial view · one segment per hour · energy in kWh</p></div><span className="pill">HOURLY VIEW</span></div><PulseRing day={pulseDay} /></article><section className="grid two-col"><WeeklyChart weekly={data.weekly} /><article className="card"><div className="card-head"><div><h2>Recent usage alerts</h2><p>Customer-safe summaries only</p></div><button className="btn secondary" onClick={() => loadPage('alerts')}>View all</button></div><AlertList alerts={data.alerts} /></article></section><article className="card" style={{ marginTop: 16 }}><div className="card-head"><div><h2>Appliance estimate coverage</h2><p>Declared appliance specifications, not direct per-appliance meter measurements</p></div><span className="pill">{data.appliances.count} ACTIVE ITEMS</span></div><div className="stat-row"><span>Estimated coverage of total meter usage</span><strong>{data.appliances.coverage_pct == null ? '—' : `${fmt(data.appliances.coverage_pct)}%`}</strong></div><div className="stat-row"><span>Largest listed category</span><strong>{data.appliances.top_category || 'Not available'}</strong></div><p className="small muted">Appliance entries are estimates. The meter measures household total consumption only.</p></article></>;
  }
  if (page === 'day') {
    const chartData = data.intervals.map((slot) => ({ ...slot, flagged_kwh: slot.flagged ? slot.energy_kwh : null }));
    return <><PageHead kicker="DAY EXPLORER" title={`15-minute intervals · ${data.date}`} description="Each point is interval energy in kWh. Amber markers show persisted customer-facing detector alerts with their plain-language reason." /><section className="grid kpis"><Kpi label="Total energy" value={`${fmt(data.summary.total_kwh)} kWh`} foot="Recorded intervals only" metricValue={data.summary.total_kwh} metricSuffix=" kWh" countUp={countUpEnabled} /><Kpi label="Data coverage" value={`${fmt(data.summary.coverage_pct)}%`} foot="96 expected intervals" metricValue={data.summary.coverage_pct} metricSuffix="%" countUp={countUpEnabled} /><Kpi label="Intervals received" value={`${data.summary.received_intervals} / 96`} foot={data.summary.partial ? 'Partial day' : 'Complete day'} /><Kpi label="Average demand" value={`${fmt(data.summary.average_power_kw, 2)} kW`} foot="Local day total / 24 hours" metricValue={data.summary.average_power_kw} metricSuffix=" kW" metricDigits={2} countUp={countUpEnabled} /></section>{prefs.energyRibbon && <EnergyRibbon intervals={data.intervals} date={data.date} />}<article className="card"><div className="card-head"><div><h2>15-minute interval profile</h2><p>Missing intervals remain gaps; they are not displayed as zero. Markers come from saved detector alerts, not generator labels.</p></div><span className="pill">{data.intervals.filter((slot) => slot.flagged).length} FLAGGED SLOTS</span></div><p className="chart-summary">{data.summary.received_intervals} of 96 expected readings received ({fmt(data.summary.coverage_pct)}% coverage). {data.intervals.filter((slot) => slot.flagged).length} intervals have saved customer-facing detector alerts. Missing values remain gaps.</p><div style={{ width: '100%', height: 280 }} role="img" aria-label={`15-minute energy chart. ${data.summary.received_intervals} of 96 intervals received; ${data.intervals.filter((slot) => slot.flagged).length} flagged intervals.`}><ResponsiveContainer><ComposedChart data={chartData}><CartesianGrid stroke="#2a3c52" strokeDasharray="4 4" vertical={false} /><XAxis dataKey="time" interval={7} stroke="#8fa3bb" fontSize={10} /><YAxis stroke="#8fa3bb" fontSize={10} /><Tooltip contentStyle={{ background: '#14253a', border: '1px solid #30445b', color: '#eef4fb' }} formatter={(value, name) => [value == null ? 'Missing' : `${fmt(value, 4)} kWh`, name === 'flagged_kwh' ? 'Detector alert' : 'Recorded energy']} /><Area type="monotone" dataKey="energy_kwh" name="Recorded energy" stroke="#5ce1d2" fill="#5ce1d2" fillOpacity={0.12} connectNulls={false} strokeWidth={2} /><Scatter dataKey="flagged_kwh" name="Detector alert" fill="#ffbd68" shape="circle" /></ComposedChart></ResponsiveContainer></div><details className="chart-table-toggle"><summary>Show as a table</summary><div className="table-wrap chart-table"><table><caption>All expected 15-minute readings, including missing intervals</caption><thead><tr><th>Local time</th><th>Energy (kWh)</th><th>Average power (kW)</th><th>Quality</th><th>Detector flag</th><th>Reason</th></tr></thead><tbody>{data.intervals.map((slot) => <tr key={slot.slot}><td>{slot.time}</td><td>{slot.energy_kwh == null ? 'Missing' : fmt(slot.energy_kwh, 4)}</td><td>{slot.average_power_kw == null ? '—' : fmt(slot.average_power_kw, 3)}</td><td>{slot.quality}</td><td>{slot.flagged ? `${slot.alert_tier} · ${slot.alert_type}` : '—'}</td><td>{slot.reason || '—'}</td></tr>)}</tbody></table></div></details></article></>;
  }
  if (page === 'heatmap') return <><PageHead kicker="USAGE PATTERNS" title="Weekly usage heatmap" description="Each cell aggregates six hours of recorded energy. Colour intensity is relative to this displayed period." /><HeatmapPanel data={data} /></>;
  if (page === 'alerts') return <><PageHead kicker="ALERTS" title="Usage pattern alerts" description="Alerts come from local simulated readings. They are not a diagnosis, enforcement finding, or service notice." /><article className="card"><AlertList alerts={data.alerts} /></article></>;
  if (page === 'story') return <><PageHead kicker="ENERGY STORY" title="A readable summary" description="This summary and its suggestions use computed facts. Suggestions are cautious prompts, not guaranteed savings or electrical advice."><select className="pill" defaultValue="en" onChange={async (event) => { try { setData(await api(`/api/customer/story?language=${event.target.value}`)); } catch (error) { setMessage({ type: 'error', text: error.message }); } }}><option value="en">English</option><option value="fil">Filipino</option></select></PageHead><article className="card"><div className="eyebrow">{data.engine} · {data.validator_passed ? 'VALIDATED' : 'NOT VALIDATED'}</div><h2 style={{ fontSize: 22, lineHeight: 1.6, fontWeight: 550 }}>{data.story}</h2>{[['Period', `${data.fact_sheet.period_start} — ${data.fact_sheet.period_end}`], ['Recorded usage', `${fmt(data.fact_sheet.total_kwh)} kWh`], ['Coverage', `${fmt(data.fact_sheet.coverage_pct)}%`], ['Data source', 'Simulated meter readings']].map(([k,v]) => <div className="stat-row" key={k}><span>{k}</span><strong>{v}</strong></div>)}</article><article className="card"><div className="card-head"><div><h2>Suggestions to review</h2><p>Fact-grounded prompts; no guaranteed savings or electrical repair advice.</p></div><span className="pill">{data.recommendations?.engine || 'template'}</span></div><ul className="recommendation-list">{(data.recommendations?.items || []).map((item,index) => <li key={index}>{item}</li>)}</ul><p className="small muted">{data.recommendations?.engine === 'local_llm' ? 'Generated by your verified local model and checked against the computed fact sheet.' : 'Generated from deterministic rules. Enable a verified local Ollama model to optionally rephrase suggestions.'}</p></article></>;
  if (page === 'appliances') return <AppliancePanel data={data} api={api} setData={setData} setMessage={setMessage} prefs={prefs} />;
  if (page === 'settings') return <SettingsPanel data={data} api={api} setMessage={setMessage} prefs={prefs} updatePrefs={updatePrefs} ensureAudioFromGesture={ensureAudioFromGesture} playTone={playTone} />;
  if (page === 'queue') return <QueuePanel data={data} api={api} setData={setData} setMessage={setMessage} />;
  if (page === 'protection') return <ProtectionPanel data={data} api={api} loadPage={loadPage} setMessage={setMessage} />;
  return <Empty text="This view is not available." />;
}

function AppliancePanel({ data, api, setData, setMessage, prefs }) {
  const emptyForm = { id: '', version: '', name: '', category: 'other', rated_power_w: '', quantity: 1, duty_pct: 100, hours_per_day: 4, days_per_week: 7, notes: '' };
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [undoAction, setUndoAction] = useState(null);
  const categories = Object.entries(data.categories || {});
  useEffect(() => {
    if (!undoAction || !prefs.undoToast) return undefined;
    const timer = window.setTimeout(() => setUndoAction(null), 10000);
    return () => window.clearTimeout(timer);
  }, [undoAction, prefs.undoToast]);
  const update = (event) => setForm((prev) => ({ ...prev, [event.target.name]: event.target.value }));
  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    const body = { ...form, quantity: Number(form.quantity), days_per_week: Number(form.days_per_week), rated_power_w: String(form.rated_power_w), duty_pct: String(form.duty_pct), hours_per_day: String(form.hours_per_day) };
    delete body.id; if (!form.id) delete body.version; else body.version = Number(form.version);
    try { await api(form.id ? `/api/customer/appliances/${form.id}` : '/api/customer/appliances', { method: form.id ? 'PUT' : 'POST', body: JSON.stringify(body) }); setForm(emptyForm); const result = await api('/api/customer/appliances'); setData(result); setMessage({ type: 'success', text: 'Appliance estimate saved.' }); }
    catch (error) { setMessage({ type: 'error', text: `${error.message}${error.code ? ` [${error.code}]` : ''}` }); }
    finally { setSaving(false); }
  };
  const retire = async (item) => {
    if (!confirm(`Retire ${item.name}? Historical versions will remain.`)) return;
    try {
      const result = await api(`/api/customer/appliances/${item.id}`, { method: 'DELETE', body: JSON.stringify({ action: 'retire', version: item.version }) });
      setData(await api('/api/customer/appliances'));
      setUndoAction(prefs.undoToast ? { id: item.id, name: item.name, version: result.version } : null);
      setMessage({ type: 'success', text: result.message || 'Appliance retired.' });
    } catch (error) { setMessage({ type: 'error', text: `${error.message}${error.code ? ` [${error.code}]` : ''}` }); }
  };
  const undoRetire = async () => {
    if (!undoAction) return;
    try {
      const result = await api(`/api/customer/appliances/${undoAction.id}/restore`, { method: 'POST', body: JSON.stringify({ version: undoAction.version }) });
      setUndoAction(null); setData(await api('/api/customer/appliances'));
      setMessage({ type: 'success', text: result.message || `${undoAction.name} restored.` });
    } catch (error) {
      setUndoAction(null);
      setMessage({ type: 'error', text: `${error.message}${error.code ? ` [${error.code}]` : ''}` });
    }
  };
  return <><PageHead kicker="APPLIANCE ESTIMATES" title="Your listed appliances" description="Estimates use rated power, quantity, duty, and schedule. The meter does not measure each appliance separately." />{undoAction && prefs.undoToast && <div className="undo-toast" role="status" aria-live="polite"><span><strong>{undoAction.name}</strong> retired. You can restore it for a few seconds.</span><div className="btn-row"><button className="btn secondary" type="button" onClick={undoRetire}>Undo</button><button className="btn secondary" type="button" onClick={() => setUndoAction(null)} aria-label="Dismiss undo message">Dismiss</button></div></div>}{prefs.whatIfMorph && <WhatIfPanel appliances={data.appliances} />}<section className="grid two-col"><article className="card reveal-on-scroll"><div className="card-head"><div><h2>Appliances you listed</h2><p>Up to 30 active items · effective-dated versions</p></div><span className="pill">{data.appliances.length} ITEMS</span></div>{data.appliances.length ? <div className="table-wrap"><table><thead><tr><th>Appliance</th><th>Rated power</th><th>Qty</th><th>Weekly estimate</th><th>Action</th></tr></thead><tbody>{data.appliances.map((item) => <tr key={item.id}><td>{item.name}<div className="muted small">{item.category_label}</div></td><td>{fmt(item.rated_power_w, 0)} W</td><td>{item.quantity}</td><td>{fmt(item.declared_kwh_per_week)} kWh</td><td><button className="btn secondary" onClick={() => setForm({ ...item, version: item.version })}>Edit</button> <button className="btn danger" onClick={() => retire(item)}>Retire</button></td></tr>)}</tbody></table></div> : <Empty text="No appliances listed yet." />}</article><article className="card reveal-on-scroll"><div className="card-head"><div><h2>{form.id ? 'Edit appliance' : 'Add an appliance'}</h2><p>Appliance details are only visible to this customer account.</p></div></div><form className="form-grid" onSubmit={submit}>{[['name','Appliance name','text'],['rated_power_w','Rated power (W)','number'],['quantity','Quantity','number'],['duty_pct','Duty (%)','number'],['hours_per_day','Hours per day','number'],['days_per_week','Days per week','number']].map(([name,label,type]) => <div key={name} className="field"><label>{label}</label><input name={name} type={type} value={form[name] ?? ''} onChange={update} required min={name==='quantity'||name==='days_per_week'?1:0} max={name==='rated_power_w'?20000:name==='quantity'?99:name==='duty_pct'?100:name==='hours_per_day'?24:name==='days_per_week'?7:undefined} step={name==='hours_per_day'?'.25':name==='rated_power_w'||name==='duty_pct'?'.01':'1'} /></div>)}<div className="field"><label>Category</label><select name="category" value={form.category} onChange={update}>{categories.map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></div><div className="field full"><label>Private note (not used in model explanations)</label><textarea name="notes" value={form.notes} onChange={update} maxLength="200" /></div><div className="field full btn-row"><button className="btn primary" disabled={saving}>{saving ? 'Saving…' : 'Save appliance'}</button><button type="button" className="btn secondary" onClick={() => setForm(emptyForm)}>Clear</button></div></form></article></section></>;
}

function SettingsPanel({ data, api, setMessage, prefs, updatePrefs, ensureAudioFromGesture, playTone }) {
  const [language, setLanguage] = useState(data.language);
  const [push, setPush] = useState(data.push_alerts);
  const [sms, setSms] = useState(data.sms_alerts);
  const [experience, setExperience] = useState(() => normalizePrefs(prefs));
  useEffect(() => setExperience(normalizePrefs(prefs)), [prefs]);
  const setExperienceOption = (key, value) => setExperience((current) => normalizePrefs({ ...current, [key]: value }));
  const save = async (event) => { event.preventDefault(); try { await api('/api/customer/settings', { method: 'PUT', body: JSON.stringify({ language, push_alerts: push, sms_alerts: sms }) }); setMessage({ type: 'success', text: 'Notification settings saved. Nothing is transmitted.' }); } catch (error) { setMessage({ type: 'error', text: `${error.message}${error.code ? ` [${error.code}]` : ''}` }); } };
  const saveExperience = (event) => {
    event.preventDefault();
    const next = normalizePrefs(experience);
    updatePrefs(next); setExperience(next);
    if (next.soundEnabled && !next.calmMode) {
      const ready = ensureAudioFromGesture();
      if (ready?.then) ready.then(() => setTimeout(() => playTone('success', 'test'), 0)).catch(() => {});
    }
    setMessage({ type: 'success', text: 'Experience preferences saved on this browser.' });
  };
  const testSound = () => {
    const next = normalizePrefs({ ...experience, soundEnabled: true, calmMode: false });
    updatePrefs(next); setExperience(next);
    const ready = ensureAudioFromGesture();
    if (ready?.then) ready.then(() => playTone('success', 'test')).catch(() => {});
  };
  const exportData = async () => { let url; try { const result = await api('/api/customer/export'); url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })); const link = document.createElement('a'); link.href = url; link.download = 'smart-meter-explorer-export.json'; link.click(); } catch (error) { setMessage({ type: 'error', text: error.message }); } finally { if (url) setTimeout(() => URL.revokeObjectURL(url), 1000); } };
  const withdraw = async () => { if (!confirm('Withdraw required usage consent and all optional notification consents?')) return; try { await api('/api/customer/consent/withdraw', { method: 'POST', body: JSON.stringify({}) }); setMessage({ type: 'success', text: 'Consent withdrawn. Analytics access is blocked.' }); window.location.reload(); } catch (error) { setMessage({ type: 'error', text: error.message }); } };
  const removeData = async () => { if (!confirm('Delete all simulated readings, generated alerts, stories, and appliances for this demo customer?')) return; try { await api('/api/customer/sample-data', { method: 'DELETE', body: JSON.stringify({ confirm: true }) }); setMessage({ type: 'success', text: 'Simulated data deleted. Consent history and account remain.' }); } catch (error) { setMessage({ type: 'error', text: error.message }); } };
  const toggle = (key, label, description) => <label className="check preference-row" key={key}><input type="checkbox" checked={!!experience[key]} onChange={(event) => setExperienceOption(key, event.target.checked)} /><span><strong>{label}</strong><small>{description}</small></span></label>;
  return <><PageHead kicker="PRIVACY AND CONTROL" title="Your data and settings" description="Control privacy, local notifications, optional Pulse enhancements, and simulated data." /><section className="grid two-col"><article className="card reveal-on-scroll"><h2 style={{ fontSize: 14 }}>Notification settings</h2><form onSubmit={save} className="grid" style={{ gap: 15, marginTop: 15 }}><div className="field"><label>Language</label><select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="en">English</option><option value="fil">Filipino</option></select></div><label className="check"><input type="checkbox" checked={push} onChange={(e) => setPush(e.target.checked)} />Enable mock push records (optional consent required).</label><label className="check"><input type="checkbox" checked={sms} onChange={(e) => setSms(e.target.checked)} />Enable mock SMS records (optional consent required).</label><button className="btn primary">Save settings</button></form></article>
    <article className="card reveal-on-scroll"><h2 style={{ fontSize: 14 }}>Pulse experience</h2><p className="small muted">New installations enable the optional effects by default. Sound and haptics only respond to a user interaction; nothing autoplays.</p><form className="grid" style={{ gap: 13, marginTop: 14 }} onSubmit={saveExperience}>
      {toggle('soundEnabled', 'Interface sounds', 'Enabled by default at a low volume; audio context starts only after a user gesture.')}
      {toggle('interactionSounds', 'Interaction sounds', 'Quiet feedback for taps and switches.')}
      {toggle('alertChimes', 'Alert chimes', 'Gentle chime for newly detected local alerts; muted while the tab is hidden.')}
      <div className="field"><label htmlFor="pulse-volume">Sound volume · {Math.round(experience.volume * 100)}%</label><input id="pulse-volume" type="range" min="0" max="50" step="1" value={Math.round(experience.volume * 100)} onChange={(event) => setExperienceOption('volume', Number(event.target.value) / 100)} /></div>
      <div className="settings-subhead">Optional interface features</div>
      {toggle('energyRibbon', 'Energy Ribbon', 'Hourly horizontal timeline with a keyboard-accessible scrubber.')}
      {toggle('whatIfMorph', 'What-if appliance preview', 'Live schedule simulation; it never changes the saved appliance record.')}
      {toggle('sharedTransitions', 'Shared screen transitions', 'Uses native View Transitions when supported; CSS screen-entry motion otherwise.')}
      {toggle('scrollReveals', 'Scroll-driven reveals', 'Feature-detected; reveals use transform and opacity only.')}
      {toggle('countUpNumbers', 'Count-up metrics', 'Brief number animation with the final value always available to assistive technology.')}
      {toggle('haptics', 'Haptic taps', 'Very short vibration on supported devices; disable here or use Calm Mode.')}
      {toggle('undoToast', 'Undo appliance retirement', 'Offers a time-limited, version-checked restore action after retiring an appliance.')}
      <div className="settings-subhead">Accessibility</div>
      {toggle('reducedMotion', 'Reduce motion', 'Disables animated effects. Your operating-system preference is respected too.')}
      {toggle('calmMode', 'Calm Mode', 'Temporarily suppresses motion, sound, and haptics without changing your individual preferences.')}
      <div className="btn-row"><button className="btn primary" type="submit">Save experience settings</button><button className="btn secondary" type="button" onClick={testSound}>Test sound</button></div>
      <p className="small muted">Settings are stored in this browser only. Haptics depend on browser and device support. Optional effects never block or delay a server-confirmed action.</p>
    </form></article>
    <article className="card reveal-on-scroll"><h2 style={{ fontSize: 14 }}>Consent history</h2><p className="small muted">Latest decision for each purpose</p>{Object.entries(data.consent).map(([key,value]) => <div className="stat-row" key={key}><span>{key}</span><strong>{value?.status ? (value.status === 'granted' ? 'Granted' : 'Withdrawn') : (value ? 'Granted' : 'Not granted')}</strong></div>)}<div className="notice info" style={{ marginTop: 15 }}>Withdrawing required consent immediately blocks dashboard and alert access.</div><button className="btn danger" onClick={withdraw}>Withdraw all consent</button></article></section><article className="card reveal-on-scroll" style={{ marginTop: 16 }}><h2 style={{ fontSize: 14 }}>Data controls</h2><p className="muted small">Consent decisions are retained as an append-only audit history.</p><div className="btn-row"><button className="btn secondary" onClick={exportData}>Export my data (JSON)</button><button className="btn danger" onClick={removeData}>Delete simulated readings and appliances</button></div></article></>;
}

function QueuePanel({ data, api, setData, setMessage }) {
  const review = async (id, status) => { try { await api(`/api/internal/queue/${id}/review`, { method: 'POST', body: JSON.stringify({ status }) }); setData(await api('/api/internal/queue')); setMessage({ type: 'success', text: 'Review status saved.' }); } catch (error) { setMessage({ type: 'error', text: error.message }); } };
  return <><PageHead kicker="INTERNAL REVIEW" title="Pattern review queue" description="Internal-only pattern leads from synthetic readings. These are not evidence of theft or wrongdoing." />{data.safe_mode === 'read_only' && <div className="notice error">Safe mode is active. Review actions are paused.</div>}<article className="card"><div className="table-wrap"><table><thead><tr><th>Pattern type</th><th>Tier</th><th>Reason</th><th>Window start</th><th>Action</th></tr></thead><tbody>{data.leads.map((lead) => <tr key={lead.id}><td>{lead.type}</td><td>{lead.tier}</td><td>{lead.reason}</td><td>{lead.window_start}</td><td><select id={`status-${lead.id}`} defaultValue="reviewed"><option value="reviewed">Reviewed</option><option value="field_check_requested">Field check requested</option></select> <button className="btn secondary" onClick={() => review(lead.id, document.getElementById(`status-${lead.id}`).value)}>Save</button></td></tr>)}</tbody></table></div>{!data.leads.length && <Empty text="No open internal review items." />}</article></>;
}

function ProtectionPanel({ data, api, loadPage, setMessage }) {
  const lock = async () => { if (!confirm('Enter read-only safe mode?')) return; try { await api('/api/internal/safe-mode/lock', { method: 'POST', body: JSON.stringify({}) }); await loadPage('protection'); setMessage({ type: 'success', text: 'Safe mode enabled.' }); } catch (error) { setMessage({ type: 'error', text: error.message }); } };
  const approve = async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); try { const result = await api('/api/internal/safe-mode/approval/start', { method: 'POST', body: JSON.stringify({ username: form.get('username'), password: form.get('password') }) }); document.getElementById('approval-challenge').value = result.challenge_id; setMessage({ type: 'success', text: `${result.message} Check the server terminal.` }); } catch (error) { setMessage({ type: 'error', text: error.message }); } };
  const unlock = async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); try { await api('/api/internal/safe-mode/unlock', { method: 'POST', body: JSON.stringify({ approval_challenge_id: form.get('challenge'), approval_code: form.get('code'), current_password: form.get('current') }) }); await loadPage('protection'); setMessage({ type: 'success', text: 'Safe mode unlocked with two-person approval.' }); } catch (error) { setMessage({ type: 'error', text: error.message }); } };
  return <div className="security-silent"><><PageHead kicker="SYSTEM PROTECTION" title="Local security status" description="Safe mode pauses protected writes. Unlock requires two different active administrators." /><section className="grid kpis"><Kpi label="Application mode" value={data.mode.toUpperCase()} foot={data.reason_code} /><Kpi label="Network boundary" value="LOCALHOST" foot="No remote listener permitted" /><Kpi label="Audit integrity" value="CHECKED" foot={data.integrity} /><Kpi label="Last security event" value={data.last_security_event?.reason_code || 'None'} foot={data.last_security_event?.occurred_at || ''} /></section><section className="grid two-col"><article className="card"><h2 style={{ fontSize: 14 }}>Lock the application</h2><p className="muted small">Switch the app into read-only mode. Available to administrators.</p><button className="btn danger" onClick={lock}>Enter read-only safe mode</button></article><article className="card"><h2 style={{ fontSize: 14 }}>Unlock (two-person approval)</h2><p className="muted small">The second administrator receives a one-time code in the server terminal.</p><form onSubmit={approve} className="grid" style={{ gap: 10 }}><div className="field"><label>Second administrator username</label><input name="username" required /></div><div className="field"><label>Second administrator passphrase</label><input name="password" type="password" required /></div><button className="btn secondary">Request approval</button></form><form onSubmit={unlock} className="grid" style={{ gap: 10, marginTop: 18 }}><div className="field"><label>Approval challenge ID</label><input id="approval-challenge" name="challenge" required /></div><div className="field"><label>Second administrator code</label><input name="code" inputMode="numeric" pattern="[0-9]{6}" maxLength="6" required /></div><div className="field"><label>Your passphrase</label><input name="current" type="password" required /></div><button className="btn primary">Unlock safely</button></form></article></section></> </div>;
}

export default App;
