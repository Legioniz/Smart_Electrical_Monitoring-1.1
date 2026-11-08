(() => {
  'use strict';
  const root = document.getElementById('app');
  const state = { user: null, csrf: '', page: 'overview', authMode: 'customer', preauth: '', adminChallenge: '', consent: null, busy: false, audio: null, lastSoundAt: 0, pendingSound: null, shellRole: null, scrollPositions: {}, lastAlertIds: new Set(), alertFeedInitialized: false, undoAction: null, undoTimer: null, countFrames: new Set(), loadRequestId: 0 };
  const PREF_KEY = 'sme.pulse.preferences.v2';
  const LEGACY_PREF_KEY = 'sme.pulse.preferences.v1';
  const defaultPrefs = { soundEnabled:true, interactionSounds:true, alertChimes:true, volume:0.22, reducedMotion:false, calmMode:false, energyRibbon:true, whatIfMorph:true, sharedTransitions:true, scrollReveals:true, countUpNumbers:true, haptics:true, undoToast:true };
  const booleanPrefs = Object.keys(defaultPrefs).filter(key => key !== 'volume');
  function normalizePrefs(value){const source=value&&typeof value==='object'&&!Array.isArray(value)?value:{};const next={...defaultPrefs,...source};booleanPrefs.forEach(key=>next[key]=next[key]===true);const volume=Number(next.volume);next.volume=Number.isFinite(volume)?Math.min(.5,Math.max(0,volume)):defaultPrefs.volume;return next;}
  function getPrefs(){try{const current=localStorage.getItem(PREF_KEY);const legacy=current==null?localStorage.getItem(LEGACY_PREF_KEY):null;const prefs=normalizePrefs(JSON.parse(current??legacy??'{}'));if(current==null&&legacy!=null)localStorage.setItem(PREF_KEY,JSON.stringify(prefs));return prefs;}catch{return {...defaultPrefs};}}
  function savePrefs(patch){const next=normalizePrefs({...getPrefs(),...patch});try{localStorage.setItem(PREF_KEY,JSON.stringify(next));}catch(_){/* Preferences remain active for this page even when storage is unavailable. */}applyExperiencePrefs();return next;}
  function applyExperiencePrefs(){const p=getPrefs();const systemReduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches??false;document.documentElement.classList.toggle('calm-mode',!!p.calmMode);document.documentElement.classList.toggle('reduced-motion',!!p.reducedMotion||!!p.calmMode||systemReduced);document.documentElement.classList.toggle('shared-transitions',!!p.sharedTransitions&&!p.reducedMotion&&!p.calmMode&&!systemReduced);document.documentElement.classList.toggle('scroll-reveals',!!p.scrollReveals&&!p.reducedMotion&&!p.calmMode&&!systemReduced);}
  function ensureAudioFromGesture(){
    try {
      const prefs=getPrefs();
      if(!prefs.soundEnabled||prefs.calmMode||document.hidden) return Promise.resolve();
      const Ctx=window.AudioContext||window.webkitAudioContext;
      if(!Ctx) return Promise.resolve();
      if(!state.audio||state.audio.state==='closed') state.audio=new Ctx();
      if(state.audio.state==='suspended') return state.audio.resume().then(()=>undefined).catch(()=>undefined);
      return Promise.resolve();
    } catch(_) { /* Audio is an optional enhancement. */ return Promise.resolve(); }
  }
  function playTone(kind='tap', channel='interaction'){
    const p=getPrefs();
    if(!p.soundEnabled || p.calmMode || document.hidden || !state.audio) return;
    if(channel==='interaction' && !p.interactionSounds) return;
    if(channel==='alert' && !p.alertChimes) return;
    const now=performance.now(), remaining=150-(now-state.lastSoundAt); if(remaining>0){if(kind==='tap')return;clearTimeout(state.pendingSound);state.pendingSound=setTimeout(()=>{state.pendingSound=null;playTone(kind,channel);},remaining);return;} state.lastSoundAt=now;
    try {
      const ctx=state.audio; if(ctx.state!=='running') return;
      const volume=Math.min(.5,Math.max(0,Number(p.volume)||0));
      const specs={
        tap:[{freq:1200,duration:30,wave:'sine',gain:.035,delay:0}],
        glide:[{freq:200,endFreq:400,duration:90,wave:'sine',gain:.025,delay:0}],
        success:[{freq:523,duration:80,wave:'sine',gain:.045,delay:0},{freq:784,duration:80,wave:'sine',gain:.045,delay:.09}],
        error:[{freq:180,duration:120,wave:'triangle',gain:.045,delay:0}],
        remove:[{freq:440,duration:80,wave:'sine',gain:.035,delay:0},{freq:330,duration:80,wave:'sine',gain:.035,delay:.09}],
        alert:[{freq:880,duration:90,wave:'sine',gain:.055,delay:0},{freq:660,duration:100,wave:'sine',gain:.055,delay:.11}],
      };
      (specs[kind]||specs.tap).forEach(note=>{
        const osc=ctx.createOscillator(), gain=ctx.createGain(), start=ctx.currentTime+note.delay, stop=start+note.duration/1000;
        osc.type=note.wave; osc.frequency.setValueAtTime(note.freq,start);
        if(note.endFreq) osc.frequency.linearRampToValueAtTime(note.endFreq,stop);
        gain.gain.setValueAtTime(0,start);
        gain.gain.linearRampToValueAtTime(note.gain*volume,start+.008);
        gain.gain.exponentialRampToValueAtTime(.0001,stop);
        osc.connect(gain); gain.connect(ctx.destination); osc.start(start); osc.stop(stop+.01);
      });
    } catch(_) { /* Sound never blocks or changes an action. */ }
  }
  document.addEventListener('submit',()=>{if(getPrefs().soundEnabled)ensureAudioFromGesture();},true);
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden && state.audio && state.audio.state==='running') state.audio.suspend().catch(()=>{});
  });
  document.addEventListener('click',event=>{const prefs=getPrefs();if(event.target?.closest?.('.security-silent'))return;if(prefs.haptics&&!prefs.calmMode&&!document.hidden&&event.target?.closest?.('button,input[type=checkbox],input[type=range],select,[role=button]')&&typeof navigator.vibrate==='function'){try{navigator.vibrate(8);}catch(_){/* Haptics are optional. */}}},true);
  const motionPreference=window.matchMedia?.('(prefers-reduced-motion: reduce)');motionPreference?.addEventListener?.('change',applyExperiencePrefs);
  function pulsePrompt(){
    try { if(localStorage.getItem('sme.pulse.soundPromptAsked')==='1') return; } catch(_) { return; }
    if(!state.user || state.user.role!=='customer' || state.page!=='overview' || getPrefs().soundEnabled) return;
    const el=document.createElement('div'); el.className='pulse-prompt-backdrop';
    el.innerHTML='<section class="pulse-prompt" role="dialog" aria-modal="true" aria-labelledby="sound-prompt-title" aria-describedby="sound-prompt-copy"><div class="eyebrow">A small preference</div><h2 id="sound-prompt-title">Would you like interface sounds?</h2><p id="sound-prompt-copy">Optional, quiet feedback for taps and saved actions. Sound is enabled at a low level by default on new installations and can always be muted.</p><div class="btn-row"><button class="btn primary" id="pulse-sound-on">Enable sounds</button><button class="btn secondary" id="pulse-sound-off">Keep muted</button></div></section>';
    document.body.appendChild(el);
    const on=el.querySelector('#pulse-sound-on'), off=el.querySelector('#pulse-sound-off');
    const opener=document.activeElement;
    try { localStorage.setItem('sme.pulse.soundPromptAsked','1'); } catch(_) {} on.focus();
    const close=()=>{el.remove();if(opener&&opener.isConnected)opener.focus({preventScroll:true});};
    on.addEventListener('click',()=>{savePrefs({soundEnabled:true});const resumed=ensureAudioFromGesture();if(resumed&&resumed.then)resumed.then(()=>playTone('success','test'));close();});
    off.addEventListener('click',close);
    el.addEventListener('keydown',event=>{if(event.key==='Escape'){close();return;}if(event.key==='Tab'){const items=[on,off];if(event.shiftKey&&document.activeElement===items[0]){event.preventDefault();items[1].focus();}else if(!event.shiftKey&&document.activeElement===items[1]){event.preventDefault();items[0].focus();}}});
  }
  applyExperiencePrefs();
  const navCustomer = [
    ['overview','Overview','◫'], ['day','Day explorer','⌁'], ['heatmap','Usage heatmap','▦'],
    ['alerts','Alerts','◇'], ['story','Energy story','✳'], ['appliances','Appliances','▤'], ['settings','Privacy & settings','⚙']
  ];
  const navInternal = [['queue','Review queue','▣'],['protection','Protection','◈']];
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (v, digits=1) => Number(v ?? 0).toLocaleString(undefined,{minimumFractionDigits:digits,maximumFractionDigits:digits});
  const dateLabel = (v) => new Date(`${v}T12:00:00`).toLocaleDateString(undefined,{month:'short',day:'numeric'});
  function notice(message, type='info') { state.notice = {message,type}; }
  function noticeHtml() { return state.notice ? `<div class="notice ${esc(state.notice.type)}" role="${state.notice.type==='error'?'alert':'status'}" aria-live="${state.notice.type==='error'?'assertive':'polite'}">${esc(state.notice.message)}</div>` : ''; }
  function clearNotice(){ state.notice = null; }
  async function api(path, options={}) {
    const headers = new Headers(options.headers || {});
    if (options.body !== undefined) headers.set('Content-Type','application/json');
    if (state.csrf && options.method && options.method !== 'GET') headers.set('X-CSRF-Token', state.csrf);
    const response = await fetch(path,{...options,headers,credentials:'same-origin',cache:'no-store'});
    const type = response.headers.get('content-type') || '';
    const data = type.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) {
      if (options.method && options.method !== 'GET' && !path.startsWith('/api/internal/safe-mode/')) playTone('error');
      const err = data?.error || {};
      const e = new Error(err.message || `Request failed (${response.status}).`);
      e.code = err.code || 'request_failed'; e.status = response.status; e.requestId = err.request_id || response.headers.get('X-Request-ID');
      throw e;
    }
    if (options.method && options.method !== 'GET' && !path.startsWith('/api/internal/safe-mode/')) playTone(String(options.method).toUpperCase()==='DELETE'||/\/retire(?:\/|$)/.test(path)?'remove':'success');
    return data;
  }
  function errorText(err) {
    const code = err.code ? ` [${err.code}]` : '';
    const id = err.requestId ? ` Reference: ${err.requestId}` : '';
    return `${err.message || 'The request could not be completed.'}${code}${id}`;
  }
  async function boot() {
    try {
      const session = await api('/api/session');
      if (session.authenticated) {
        state.user = session.user; state.csrf = session.csrf_token;
        if (state.user.must_change_password) return renderPasswordChange();
        if (session.consent_required) return renderConsent();
        return showPage('overview');
      }
      renderLanding();
    } catch (e) {
      renderUnavailable(errorText(e));
    }
  }
  function renderLanding() {
    state.shellRole = null; state.user = null; state.page = 'login';
    root.innerHTML = `
      <div class="login-wrap">
        <section class="hero">
          <div class="brand"><span class="mark">SME</span><div><div class="brand-title">SMART METER EXPLORER</div><span class="brand-sub">LOCAL ENERGY INTELLIGENCE · V2.0</span></div></div>
          <div class="eyebrow" style="margin-top:58px">A clearer view of your energy</div>
          <h1>Understand your usage.<br><span style="color:var(--cyan)">Spot what changes.</span></h1>
          <p>Explore 15-minute electricity readings, learn how your usage changes through the week, and review transparent alerts. This build runs locally and uses simulated meter data only.</p>
          <div class="pulse-line" aria-hidden="true"><svg viewBox="0 0 420 48"><path d="M0 25 H95 L112 25 L127 8 L143 40 L159 18 L172 25 H245 L260 25 L275 14 L289 34 L304 25 H420"/></svg></div><div class="feature-list"><span>15-minute usage exploration and daily coverage</span><span>Explainable pattern alerts with data provenance</span><span>Local-only storage, consent controls and audit trail</span></div>
        </section>
        <section class="login-card" aria-label="Sign in">
          <h2>Welcome back</h2><p>Sign in to your local demonstration workspace.</p>
          <div class="login-switch"><button data-mode="customer" class="${state.authMode==='customer'?'active':''}">Customer</button><button data-mode="internal" class="${state.authMode==='internal'?'active':''}">Staff portal</button></div>
          <form id="login-form" class="grid" style="gap:13px">
            <div class="field"><label for="username">Username</label><input id="username" name="username" autocomplete="username" required maxlength="80"></div>
            <div class="field"><label for="password">Passphrase</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="1024"></div>
            <div id="otp-wrap" class="field" ${state.adminChallenge?"":"hidden"}><label for="otp">One-time code from the server terminal</label><input id="otp" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6"></div>
            <button class="btn primary" id="login-submit" type="submit">Continue <span aria-hidden="true">→</span></button>
          </form>
          ${noticeHtml()}
          <div class="footer-note">For the demo, generated account passphrases are printed once by the local setup command. Staff accounts also require a one-time terminal code. No cloud login is used.</div>
        </section>
      </div>`;
    root.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{ state.authMode=b.dataset.mode; state.adminChallenge=''; renderLanding(); }));
    root.querySelector('#login-form').addEventListener('submit',ev=>state.authMode==='internal'&&state.adminChallenge?handleAdminVerify(ev):handleLogin(ev));
  }
  async function handleLogin(ev) {
    ev.preventDefault(); const button = root.querySelector('#login-submit'); button.disabled = true;
    const username = root.querySelector('#username').value.trim(); const password = root.querySelector('#password').value;
    try {
      if (!state.preauth) { const pre = await api('/api/auth/preflight'); state.preauth = pre.csrf_token; }
      state.csrf = state.preauth;
      if (state.authMode === 'internal' && state.adminChallenge) return await handleAdminVerify(ev);
      if (state.authMode === 'customer') {
        const result = await api('/api/auth/customer/login',{method:'POST',body:JSON.stringify({username,password})});
        state.user = {username:result.user.username,role:result.user.role,must_change_password:true}; state.csrf=result.csrf_token; state.preauth='';
        return result.user && (await continueAfterLogin());
      }
      if (!state.adminChallenge) {
        const result = await api('/api/auth/admin/start',{method:'POST',body:JSON.stringify({username,password})});
        state.adminChallenge=result.challenge_id; state.pendingUsername=username;
        notice(result.message,'success'); renderLanding();
        root.querySelector('#username').value=username; root.querySelector('#password').value='';
        root.querySelector('#otp-wrap').hidden=false;
        root.querySelector('#login-submit').textContent='Verify one-time code';
      }
    } catch(e) { notice(errorText(e),'error'); state.preauth=''; state.adminChallenge=''; renderLanding(); }
    finally { const btn=root.querySelector('#login-submit'); if(btn) btn.disabled=false; }
  }
  async function handleAdminVerify(ev) {
    ev.preventDefault(); const btn=root.querySelector('#login-submit'); btn.disabled=true;
    try {
      const code=root.querySelector('#otp').value.trim();
      const result=await api('/api/auth/admin/verify',{method:'POST',body:JSON.stringify({challenge_id:state.adminChallenge,code})});
      state.user=result.user; state.csrf=result.csrf_token; state.preauth=''; state.adminChallenge='';
      await continueAfterLogin();
    } catch(e) { notice(errorText(e),'error'); renderLanding(); root.querySelector('#login-form').addEventListener('submit',handleLogin); }
    finally { if(root.querySelector('#login-submit')) root.querySelector('#login-submit').disabled=false; }
  }
  async function continueAfterLogin() {
    const current=await api('/api/session'); state.user=current.user; state.csrf=current.csrf_token;
    if(current.user.must_change_password) return renderPasswordChange();
    if(current.consent_required) return renderConsent();
    return showPage('overview');
  }
  function renderPasswordChange() {
    state.shellRole = null;
    root.innerHTML=`<div class="screen-center"><section class="card wide-card"><div class="brand"><span class="mark">SME</span><div><div class="brand-title">SECURE YOUR ACCOUNT</div><span class="brand-sub">FIRST SIGN-IN REQUIRED</span></div></div><div class="eyebrow" style="margin-top:30px">One-time setup</div><h1 style="font-size:30px;margin:0 0 10px">Create a new passphrase</h1><p class="muted small" style="line-height:1.7">The temporary passphrase must be changed before using the workspace. Use at least 15 characters. A phrase made of several unrelated words is easier to remember.</p>${noticeHtml()}<form id="pw-form" class="grid" style="max-width:480px;margin-top:22px;gap:14px"><div class="field"><label>Current temporary passphrase</label><input name="current" type="password" required autocomplete="current-password"></div><div class="field"><label>New passphrase (15+ characters)</label><input name="next" type="password" required minlength="15" autocomplete="new-password"></div><div class="field"><label>Confirm new passphrase</label><input name="confirm" type="password" required minlength="15" autocomplete="new-password"></div><button class="btn primary" type="submit">Update passphrase →</button></form><div class="footer">Local account security · Passphrase changes rotate your current session and CSRF token.</div></section></div>`;
    root.querySelector('#pw-form').addEventListener('submit',async ev=>{ev.preventDefault();const f=new FormData(ev.target);if(f.get('next')!==f.get('confirm')){notice('The new passphrases do not match.','error');return renderPasswordChange();}const b=ev.target.querySelector('button');b.disabled=true;try{const r=await api('/api/auth/password/change',{method:'POST',body:JSON.stringify({current_password:f.get('current'),new_password:f.get('next')})});state.csrf=r.csrf_token;const current=await api('/api/session');state.user=current.user;if(current.consent_required)renderConsent();else showPage('overview');}catch(e){notice(errorText(e),'error');renderPasswordChange();}finally{if(root.querySelector('#pw-form button'))root.querySelector('#pw-form button').disabled=false;}});
  }
  async function renderConsent() {
    state.shellRole = null;
    try { state.consent=await api('/api/consent'); } catch(e){return renderUnavailable(errorText(e));}
    const c=state.consent;
    root.innerHTML=`<div class="screen-center"><section class="card wide-card"><div class="brand"><span class="mark">SME</span><div><div class="brand-title">SMART METER EXPLORER</div><span class="brand-sub">PRIVACY AND CONSENT</span></div></div><div class="eyebrow" style="margin-top:30px">Before you continue</div><h1 style="font-size:30px;margin:0 0 10px">Your data. Your choice.</h1><p class="muted small" style="line-height:1.7">Review what this local demonstration stores and choose whether to proceed. The required permission unlocks the simulated usage screens. Optional notification settings are mock-only and nothing is sent.</p><div class="consent-text">${esc(c.text)}\n\nVersion ${esc(c.version)} · SHA-256 ${esc(c.text_hash.slice(0,18))}…</div>${noticeHtml()}<form id="consent-form" class="grid" style="gap:15px"><label class="check"><input id="required-consent" type="checkbox" required><span><strong>Required:</strong> ${esc(c.required.label)}. This is needed to open the dashboard. You can withdraw later in Privacy & settings.</span></label>${c.optional.map(o=>`<label class="check"><input type="checkbox" name="${esc(o.purpose)}"><span>${esc(o.label)}. Optional. These channels are simulated only and are never sent.</span></label>`).join('')}<div class="btn-row" style="margin-top:7px"><button class="btn primary" type="submit">Agree and continue →</button><button class="btn secondary" type="button" id="signout">Sign out</button></div></form><div class="footer">Consent is stored as an append-only decision on this computer with the text version, text hash and time. The application blocks customer analytics when required consent is withdrawn.</div></section></div>`;
    root.querySelector('#consent-form').addEventListener('submit',async ev=>{ev.preventDefault();if(getPrefs().soundEnabled)ensureAudioFromGesture();const btn=ev.target.querySelector('button[type=submit]');btn.disabled=true;try{const result=await api('/api/consent',{method:'POST',body:JSON.stringify({text_version:c.version,request_id:crypto.randomUUID(),required_analytics:root.querySelector('#required-consent').checked,push_alerts:!!ev.target.elements.push_alerts?.checked,sms_alerts:!!ev.target.elements.sms_alerts?.checked})});if(!result.analytics_unlocked)throw new Error('Consent was saved but analytics did not unlock. Refresh the session and review the consent status.');state.notice=null;showPage('overview');}catch(e){notice(errorText(e),'error');renderConsent();}finally{if(root.querySelector('#consent-form button[type=submit]'))root.querySelector('#consent-form button[type=submit]').disabled=false;}});
    root.querySelector('#signout').addEventListener('click',logout);
  }
  async function logout() { state.loadRequestId+=1; try { await api('/api/auth/logout',{method:'POST',body:JSON.stringify({})}); } catch(_) {} state.user=null;state.csrf='';state.preauth='';state.adminChallenge='';state.notice=null;renderLanding(); }
  function frame(content, page) {
    const role=state.user?.role; const nav=role==='customer'?navCustomer:navInternal;
    if(!root.querySelector('#page-content') || state.shellRole!==role){
      root.innerHTML=`<header class="topbar"><div class="brand"><span class="mark" aria-hidden="true">SME</span><div><div class="brand-title">SMART METER EXPLORER</div><span class="brand-sub">LOCAL ENERGY INTELLIGENCE</span></div></div><div class="top-actions"><button class="btn secondary home-shortcut" id="home-shortcut">Back to home</button>${role==='customer'?'<button class="btn secondary settings-shortcut" id="settings-shortcut">Settings</button>':''}<span class="badge sim">● SIMULATED DATA</span><span class="pill">${esc(state.user?.username)} · ${esc(role)}</span><button class="btn secondary sound-quick" id="sound-quick" aria-label="Toggle interface sounds" aria-pressed="${getPrefs().soundEnabled&&!getPrefs().calmMode}">${getPrefs().soundEnabled&&!getPrefs().calmMode?'Sound on':'Sound off'}</button><button class="btn secondary" id="logout">Sign out</button></div></header><div class="shell"><aside class="sidebar"><div class="side-label">${role==='customer'?'Your workspace':'Internal workspace'}</div><nav class="nav" aria-label="Main navigation">${nav.map(([id,label,icon])=>`<button type="button" data-page="${id}" class="${page===id?'active':''}" ${page===id?'aria-current="page"':''}><span class="nav-icon" aria-hidden="true">${icon}</span><span>${label}</span></button>`).join('')}</nav><div class="side-note"><strong style="color:#dce9f7">Local-only demo</strong><br>All meter readings and model benchmarks in this workspace are synthetic. No live Meralco feed is connected.</div></aside><main class="content"><div id="notice-region">${noticeHtml()}</div><div id="page-content"></div><div class="footer">Smart Meter Explorer V2 · Synthetic meter data · Local database · No cloud services · <span class="muted">Never use this build for billing or service decisions.</span></div></main></div>`;
      state.shellRole=role;
      root.querySelector('#logout').addEventListener('click',logout);
      root.querySelector('#home-shortcut').addEventListener('click',()=>{state.scrollPositions[state.page]=window.scrollY;state.notice=null;renderPortalHome();});
      const settingsShortcut=root.querySelector('#settings-shortcut'); if(settingsShortcut) settingsShortcut.addEventListener('click',()=>{state.notice=null;showPage('settings');});
      const soundQuick=root.querySelector('#sound-quick'); if(soundQuick) soundQuick.addEventListener('click',()=>{const next=savePrefs({soundEnabled:!getPrefs().soundEnabled});soundQuick.textContent=next.soundEnabled&&!getPrefs().calmMode?'Sound on':'Sound off';soundQuick.setAttribute('aria-pressed',String(next.soundEnabled&&!getPrefs().calmMode));if(next.soundEnabled){const resumed=ensureAudioFromGesture();if(resumed&&resumed.then)resumed.then(()=>playTone('tap'));}});
      root.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{state.scrollPositions[state.page]=window.scrollY;state.notice=null;showPage(b.dataset.page);}));
    }
    root.querySelectorAll('[data-page]').forEach(b=>{const active=b.dataset.page===page;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
    const soundQuick=root.querySelector('#sound-quick'); if(soundQuick){soundQuick.textContent=getPrefs().soundEnabled&&!getPrefs().calmMode?'Sound on':'Sound off';soundQuick.setAttribute('aria-pressed',String(getPrefs().soundEnabled&&!getPrefs().calmMode));}
    root.querySelector('#notice-region').innerHTML=noticeHtml();
    const target=root.querySelector('#page-content');
    const paint=()=>{
      target.innerHTML=`<section class="screen-view" data-screen="${esc(page)}">${content}</section>`;
      const cards=target.querySelectorAll('.card');
      if(getPrefs().scrollReveals&&!document.documentElement.classList.contains('reduced-motion'))cards.forEach(card=>card.classList.add('reveal-on-scroll'));
      const heading=target.querySelector('.page-head h1, h1');
      if(heading){heading.setAttribute('tabindex','-1');heading.focus({preventScroll:true});}
      const saved=state.scrollPositions[page]||0;
      requestAnimationFrame(()=>window.scrollTo({top:saved,behavior:'auto'}));
      animateCountUps(target);
    };
    // Keep DOM replacement synchronous in the no-build fallback. The browser
    // View Transitions API defers its update callback, which would otherwise
    // race the page-specific event bindings immediately below. React uses the
    // native API with flushSync; this fallback uses the same CSS entry motion.
    applyExperiencePrefs();
    paint();
    // Interaction sounds are armed only by this real user gesture. A success/error
    // tone is emitted by api() only after the server responds.
    target.querySelectorAll('button').forEach(b=>{if(!b.id.startsWith('sound-')&&b.id!=='logout'&&!b.closest('.security-silent')&&!b.dataset.soundBound){b.dataset.soundBound='1';b.addEventListener('click',()=>{if(getPrefs().soundEnabled){const resumed=ensureAudioFromGesture();if(resumed&&resumed.then)resumed.then(()=>playTone('tap'));}},{passive:true});}});
  }
  function renderPortalHome(){
    state.page='home';
    frame(`${pageHead('SMART METER EXPLORER','Your electricity, easier to understand','A local workspace for exploring simulated 15-minute meter readings, transparent pattern alerts, and appliance-use estimates.')}<section class="card pulse-card home-hero"><div class="eyebrow">PULSE · LOCAL ENERGY INSIGHT</div><h2>See what changed. Understand the numbers.</h2><p class="muted">The application turns stored interval readings into clear views without claiming to know more than the meter can show.</p><div class="btn-row"><button class="btn primary" id="home-overview">Open sample portal</button><button class="btn secondary" id="home-alerts">Review alerts</button></div></section><section class="grid two-col" style="margin-top:16px"><article class="card"><h2>Explore</h2><p class="muted small">Review daily intervals, weekly patterns, declared appliance estimates, and validated energy stories.</p></article><article class="card"><h2>Built to be careful</h2><p class="muted small">Simulated data only. Customer alerts are descriptive; possible theft-related leads remain restricted to authorized internal review.</p></article></section><div class="notice info" style="margin-top:16px">SAMPLE DATA: This local demonstration uses simulated readings. It is not an official Meralco site and is not endorsed by Meralco. Nothing here is live or real.</div>`, 'home');
    root.querySelector('#home-overview').addEventListener('click',()=>showPage('overview'));
    root.querySelector('#home-alerts').addEventListener('click',()=>showPage('alerts'));
  }
  function pageHead(kicker,title,desc,actions=''){return `<div class="page-head"><div><div class="eyebrow">${esc(kicker)}</div><h1 tabindex="-1">${esc(title)}</h1><p>${esc(desc)}</p></div><div class="btn-row">${actions}</div></div>`;}
  function renderLoading(page){const label=page==='overview'?'Overview':page==='day'?'Day explorer':page==='heatmap'?'Usage heatmap':page==='alerts'?'Alerts':page==='story'?'Energy story':page==='appliances'?'Appliances':page==='settings'?'Settings':page==='queue'?'Review queue':'Protection';frame(`${pageHead('LOADING',label,'Loading saved local information…')}<section class="grid kpis"><div class="skeleton-block skeleton-kpi"></div><div class="skeleton-block skeleton-kpi"></div><div class="skeleton-block skeleton-kpi"></div><div class="skeleton-block skeleton-kpi"></div></section><section class="skeleton-block skeleton-panel" aria-label="Loading chart and detail content"></section>` ,page);}
  function lineChart(items,valueKey='total_kwh') {
    const values=items.map(x=>Number(x[valueKey]||0));const max=Math.max(...values,1)*1.16;const min=0;const width=640,height=210,left=34,right=12,top=12,bottom=29;const points=values.map((v,i)=>`${left+(i/(Math.max(values.length-1,1)))*(width-left-right)},${top+(1-(v-min)/(max-min))*(height-top-bottom)}`).join(' ');const area=`${left},${height-bottom} ${points} ${width-right},${height-bottom}`;
    const total=values.reduce((a,b)=>a+b,0),low=Math.min(...values),high=Math.max(...values);
    const summary=`Across ${items.length} recorded days, daily use ranges from ${fmt(low,2)} to ${fmt(high,2)} kWh. The sum of the displayed daily totals is ${fmt(total,2)} kWh; missing intervals are not filled.`;
    const rows=items.map(x=>`<tr><td>${esc(x.date)}</td><td>${fmt(x[valueKey],3)}</td></tr>`).join('');
    return `<div class="chart-block"><svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Weekly daily electricity totals. ${esc(summary)}"><defs><linearGradient id="area" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#7c93b5" stop-opacity=".24"/><stop offset="1" stop-color="#7c93b5" stop-opacity="0"/></linearGradient></defs>${[0,.33,.66,1].map(q=>`<line class="gridline" x1="${left}" x2="${width-right}" y1="${top+(1-q)*(height-top-bottom)}" y2="${top+(1-q)*(height-top-bottom)}"/>`).join('')}<polygon class="area" points="${area}"/><polyline class="line" points="${points}"/>${items.map((x,i)=>i%Math.max(1,Math.ceil(items.length/7))===0?`<text x="${left+(i/(Math.max(values.length-1,1)))*(width-left-right)}" y="${height-7}" text-anchor="middle">${esc(dateLabel(x.date))}</text>`:'').join('')}</svg><p class="chart-summary">${esc(summary)}</p><button class="btn secondary" id="weekly-table-toggle" aria-expanded="false" aria-controls="weekly-table">Show as a table</button></div><div class="table-wrap chart-table" id="weekly-table" hidden><table><caption>Daily electricity totals</caption><thead><tr><th>Date</th><th>Energy (kWh)</th></tr></thead><tbody>${rows}</tbody><tfoot><tr><th>Total</th><th>${fmt(total,3)} kWh</th></tr></tfoot></table></div>`;
  }
  function bindTableToggle(buttonId,tableId,showText='Show as a table',hideText='Hide table') {const b=root.querySelector(`#${buttonId}`),t=root.querySelector(`#${tableId}`);if(!b||!t)return;b.addEventListener('click',()=>{t.hidden=!t.hidden;b.textContent=t.hidden?showText:hideText;b.setAttribute('aria-expanded',String(!t.hidden));});}
  function announceNewAlerts(alerts){
    const ids=new Set((alerts||[]).map(a=>String(a.id)));
    if(state.alertFeedInitialized){const added=(alerts||[]).filter(a=>!state.lastAlertIds.has(String(a.id)));if(added.length)playTone('alert','alert');}
    state.lastAlertIds=ids;state.alertFeedInitialized=true;
  }
  async function showPage(page) {
    const requestId=++state.loadRequestId;
    if(!state.user)return renderLanding();
    if(state.user.must_change_password)return renderPasswordChange();
    if(state.page)state.scrollPositions[state.page]=window.scrollY;
    if(page==='home'){state.notice=null;state.page='home';return renderPortalHome();}
    if(state.user.role==='customer'&&page!=='settings'){
      try{const sess=await api('/api/session');if(requestId!==state.loadRequestId)return;if(sess.consent_required)return renderConsent();}
      catch(error){if(requestId!==state.loadRequestId)return;if(error.status===401){state.user=null;state.csrf='';return renderLanding();}notice(errorText(error),'error');return renderGenericError(page);}
    }
    if(requestId!==state.loadRequestId)return;
    state.page=page;renderLoading(page);
    try{
      if(state.user.role==='customer'){
        if(page==='overview'){const overview=await api('/api/customer/overview');if(requestId!==state.loadRequestId)return;const day=await api(`/api/customer/day?day=${encodeURIComponent(overview.period.end)}`);if(requestId!==state.loadRequestId)return;return renderOverview(overview,day);}
        if(page==='day'){const result=await api('/api/customer/day');if(requestId!==state.loadRequestId)return;return renderDay(result);}
        if(page==='heatmap'){const result=await api('/api/customer/heatmap?days=7');if(requestId!==state.loadRequestId)return;return renderHeatmap(result);}
        if(page==='alerts'){const result=await api('/api/customer/alerts');if(requestId!==state.loadRequestId)return;return renderAlerts(result);}
        if(page==='story'){const result=await api('/api/customer/story');if(requestId!==state.loadRequestId)return;return renderStory(result);}
        if(page==='appliances'){const result=await api('/api/customer/appliances');if(requestId!==state.loadRequestId)return;return renderAppliances(result);}
        if(page==='settings'){const result=await api('/api/customer/settings');if(requestId!==state.loadRequestId)return;return renderSettings(result);}
      }else{
        if(page==='queue'){const result=await api('/api/internal/queue');if(requestId!==state.loadRequestId)return;return renderQueue(result);}
        if(page==='protection'){const result=await api('/api/internal/protection');if(requestId!==state.loadRequestId)return;return renderProtection(result);}
      }
      if(requestId===state.loadRequestId){state.page='overview';return showPage('overview');}
    }catch(error){
      if(requestId!==state.loadRequestId)return;
      if(error.status===401){state.user=null;state.csrf='';return renderLanding();}
      if(error.code==='consent_required')return renderConsent();
      notice(errorText(error),'error');return renderGenericError(page);
    }
  }
  function pulseRing(day){
    const slots=day?.intervals||[]; const hours=Array.from({length:24},(_,h)=>{const rows=slots.slice(h*4,h*4+4);return {hour:h,kwh:rows.reduce((sum,r)=>sum+(Number(r.energy_kwh)||0),0),count:rows.filter(r=>r.energy_kwh!==null&&r.energy_kwh!==undefined).length,flagged:rows.some(r=>r.flagged)};});
    const max=Math.max(...hours.map(x=>x.kwh),0.01), r=78, c=2*Math.PI*r, gap=3, step=c/24;
    const circles=hours.map((h)=>{const len=h.kwh>0?(h.kwh/max)*(step-gap):0;const offset=-((h.hour/24)*c);const color=h.flagged?'#c2410c':'#7c93b5';const label=`${String(h.hour).padStart(2,'0')}:00, ${fmt(h.kwh,3)} kWh${h.flagged?', detector flag':''}, ${h.count}/4 intervals`;return `<circle class="pulse-segment ${h.flagged?'flagged':''}" tabindex="0" role="img" aria-label="${esc(label)}" data-hour="${h.hour}" cx="100" cy="100" r="${r}" fill="none" stroke="${color}" stroke-width="${h.flagged?16:13}" stroke-linecap="${h.flagged?'round':'butt'}" stroke-dasharray="${len} ${c-len}" stroke-dashoffset="${offset}" transform="rotate(-90 100 100)"><title>${esc(label)}</title></circle>`;}).join('');
    const total=hours.reduce((a,b)=>a+b.kwh,0); const summary=`${fmt(total,2)} kWh across 24 hours; ${hours.filter(h=>h.count>0).length} hours contain readings; ${hours.filter(h=>h.flagged).length} hours include saved customer alerts.`;
    const rows=hours.map(h=>`<tr><td>${String(h.hour).padStart(2,'0')}:00</td><td>${fmt(h.kwh,3)}</td><td>${h.count}/4</td><td>${h.flagged?'Flagged':'—'}</td></tr>`).join('');
    return `<div class="pulse-ring-layout"><div class="pulse-ring-wrap"><svg class="pulse-ring" viewBox="0 0 200 200" role="group" aria-label="Pulse Ring: hourly energy for ${esc(day.date)}. ${esc(summary)}"><circle cx="100" cy="100" r="78" fill="none" stroke="#e2e8f0" stroke-width="13"/>${circles}<text x="100" y="91" text-anchor="middle" class="pulse-total">${fmt(total,1)}</text><text x="100" y="111" text-anchor="middle" class="pulse-unit">kWh · 24 HOURS</text></svg><div class="pulse-anchors"><span>12 AM</span><span>6 AM</span><span>12 PM</span><span>6 PM</span></div></div><div class="pulse-detail"><div class="eyebrow">TODAY · ${esc(day.date)}</div><p>${esc(summary)}</p><div class="pulse-legend"><span><i class="normal"></i> Recorded use</span><span><i class="flag"></i> Saved detector alert</span></div><button class="btn secondary" id="pulse-table-toggle" aria-expanded="false" aria-controls="pulse-table">Show hourly table</button></div></div><div class="table-wrap pulse-table" id="pulse-table" hidden><table><thead><tr><th>Hour</th><th>Energy (kWh)</th><th>Coverage</th><th>Alert</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }
  function bindPulseTable(){const b=root.querySelector('#pulse-table-toggle'),t=root.querySelector('#pulse-table');if(!b||!t)return;b.addEventListener('click',()=>{t.hidden=!t.hidden;b.textContent=t.hidden?'Show hourly table':'Hide hourly table';b.setAttribute('aria-expanded',String(!t.hidden));playTone('tap');});}
  function countValue(value,digits=1,suffix=''){
    const number=Number(value);const safe=Number.isFinite(number)?number:0;const final=`${fmt(safe,digits)}${suffix}`;
    return `<span class="count-up-value" data-count-target="${safe}" data-count-digits="${digits}" data-count-suffix="${esc(suffix)}" aria-label="${esc(final)}">${esc(final)}</span>`;
  }
  function animateCountUps(container){
    state.countFrames.forEach(frame=>cancelAnimationFrame(frame));state.countFrames.clear();
    const prefs=getPrefs();const reduced=prefs.reducedMotion||prefs.calmMode||(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches??false);
    if(!prefs.countUpNumbers||reduced)return;
    container.querySelectorAll('[data-count-target]').forEach(node=>{
      const target=Number(node.dataset.countTarget),digits=Math.max(0,Math.min(4,Number(node.dataset.countDigits)||1)),suffix=node.dataset.countSuffix||'';
      if(!Number.isFinite(target))return;
      const started=performance.now(),duration=560;
      let frameId=0;
      const tick=now=>{state.countFrames.delete(frameId);const progress=Math.min(1,(now-started)/duration),eased=1-Math.pow(1-progress,3);node.textContent=`${fmt(target*eased,digits)}${suffix}`;if(progress<1){frameId=requestAnimationFrame(tick);state.countFrames.add(frameId);}else node.textContent=node.getAttribute('aria-label')||`${fmt(target,digits)}${suffix}`;};
      node.textContent=`${fmt(0,digits)}${suffix}`;frameId=requestAnimationFrame(tick);state.countFrames.add(frameId);
    });
  }
  function energyRibbon(day){
    const hours=Array.from({length:24},(_,hour)=>{const rows=day.intervals.slice(hour*4,hour*4+4);return{hour,kwh:rows.reduce((sum,row)=>sum+(row.energy_kwh==null?0:Number(row.energy_kwh)||0),0),received:rows.filter(row=>row.energy_kwh!=null).length,flagged:rows.filter(row=>row.flagged).length};});
    const max=Math.max(...hours.map(row=>row.kwh),0);
    const buttons=hours.map(row=>{const scale=max>0?row.kwh/max:0;const label=`${String(row.hour).padStart(2,'0')}:00, ${fmt(row.kwh,3)} kWh, ${row.received} of 4 readings, ${row.flagged} flagged`;return `<button type="button" class="energy-ribbon-hour ${row.hour===0?'active':''} ${row.flagged?'flagged':''}" data-energy-hour="${row.hour}" aria-label="${esc(label)}" aria-pressed="${row.hour===0}"><span class="energy-ribbon-track"><span class="energy-ribbon-fill" style="transform:scaleY(${scale})"></span></span><small>${row.hour%6===0?String(row.hour).padStart(2,'0'):''}</small></button>`;}).join('');
    return `<article class="card energy-ribbon-panel"><div class="card-head"><div><h2>Energy Ribbon</h2><p>24-hour timeline · select an hour to inspect its four 15-minute intervals</p></div><span class="pill">${esc(day.date)}</span></div><div class="energy-ribbon" role="group" aria-label="Hourly energy timeline">${buttons}</div><label class="energy-ribbon-scrubber" for="energy-ribbon-hour"><span>Selected hour</span><input id="energy-ribbon-hour" type="range" min="0" max="23" step="1" value="0"><output id="energy-ribbon-time">00:00</output></label><p class="chart-summary" id="energy-ribbon-summary" aria-live="polite"></p></article>`;
  }
  function bindEnergyRibbon(day){
    const hours=Array.from({length:24},(_,hour)=>{const rows=day.intervals.slice(hour*4,hour*4+4);return{hour,kwh:rows.reduce((sum,row)=>sum+(row.energy_kwh==null?0:Number(row.energy_kwh)||0),0),received:rows.filter(row=>row.energy_kwh!=null).length,flagged:rows.filter(row=>row.flagged).length};});
    const slider=root.querySelector('#energy-ribbon-hour'),summary=root.querySelector('#energy-ribbon-summary'),time=root.querySelector('#energy-ribbon-time');if(!slider||!summary||!time)return;
    const select=hour=>{const selected=hours[Math.min(23,Math.max(0,Number(hour)||0))];slider.value=selected.hour;time.textContent=`${String(selected.hour).padStart(2,'0')}:00`;summary.textContent=`${time.textContent} — ${fmt(selected.kwh,3)} kWh recorded · ${selected.received}/4 intervals received · ${selected.flagged} flagged intervals. Missing readings are not interpreted as zero-consumption observations.`;root.querySelectorAll('[data-energy-hour]').forEach(button=>{const active=Number(button.dataset.energyHour)===selected.hour;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});};
    slider.addEventListener('input',()=>select(slider.value));root.querySelectorAll('[data-energy-hour]').forEach(button=>button.addEventListener('click',()=>select(button.dataset.energyHour)));select(0);
  }
  function whatIfPanel(appliances){
    if(!appliances.length)return '<article class="card what-if-panel"><h2>What-if appliance preview</h2><p class="muted small">Add an appliance to explore a schedule change.</p></article>';
    const first=appliances[0];const options=appliances.map(item=>`<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('');
    return `<article class="card what-if-panel"><div class="card-head"><div><h2>What-if appliance preview</h2><p>Explore a schedule change without saving or changing your appliance record.</p></div><span class="pill">LOCAL SIMULATION</span></div><div class="what-if-controls"><div class="field"><label for="what-if-appliance">Appliance</label><select id="what-if-appliance">${options}</select></div><div class="field"><label for="what-if-hours">Hours per day · <output id="what-if-hours-value">${fmt(first.hours_per_day,2)} h</output></label><input id="what-if-hours" type="range" min="0" max="24" step="0.25" value="${Number(first.hours_per_day)||0}"></div></div><div class="what-if-comparison"><div><span>Current listed estimate</span><strong id="what-if-current">${fmt(first.declared_kwh_per_week,2)} kWh/week</strong><div class="what-if-bar"><span id="what-if-current-bar"></span></div></div><div><span>What-if estimate</span><strong id="what-if-next">${fmt(first.declared_kwh_per_week,2)} kWh/week</strong><div class="what-if-bar"><span id="what-if-next-bar" class="scenario"></span></div></div></div><div class="stat-row"><span>Estimated weekly change</span><strong id="what-if-delta">0.00 kWh</strong></div><p class="small muted">This calculation uses nameplate power, quantity, duty factor, and entered schedule. It is not a measured appliance load and does not change saved data.</p></article>`;
  }
  function bindWhatIf(appliances){
    const select=root.querySelector('#what-if-appliance'),slider=root.querySelector('#what-if-hours');if(!select||!slider)return;
    const update=()=>{const item=appliances.find(row=>row.id===select.value)||appliances[0];if(!item)return;const hours=Math.min(24,Math.max(0,Number(slider.value)||0));const current=Number(item.declared_kwh_per_week)||0;const next=(Number(item.rated_power_w)/1000)*(Number(item.quantity)||1)*(Number(item.duty_pct)/100)*hours*(Number(item.days_per_week)||7);const others=appliances.filter(row=>row.id!==item.id).reduce((sum,row)=>sum+(Number(row.declared_kwh_per_week)||0),0);const currentTotal=others+current,nextTotal=others+next;const currentShare=currentTotal>0?current/currentTotal:0,nextShare=nextTotal>0?next/nextTotal:0;const delta=next-current;
      root.querySelector('#what-if-hours-value').textContent=`${fmt(hours,2)} h`;root.querySelector('#what-if-current').textContent=`${fmt(current,2)} kWh/week`;root.querySelector('#what-if-next').textContent=`${fmt(next,2)} kWh/week`;root.querySelector('#what-if-current-bar').style.transform=`scaleX(${currentShare})`;root.querySelector('#what-if-next-bar').style.transform=`scaleX(${nextShare})`;const deltaNode=root.querySelector('#what-if-delta');deltaNode.textContent=`${delta>0?'+':''}${fmt(delta,2)} kWh`;deltaNode.className=delta>.005?'up':delta<-.005?'down':'';};
    const syncHours=()=>{const item=appliances.find(row=>row.id===select.value)||appliances[0];slider.value=String(Math.min(24,Math.max(0,Number(item.hours_per_day)||0)));update();};select.addEventListener('change',syncHours);slider.addEventListener('input',update);syncHours();
  }
  function renderUndoToast(){
    if(!state.undoAction||!getPrefs().undoToast)return '';
    return `<div id="undo-toast" class="undo-toast" role="status" aria-live="polite"><span><strong>${esc(state.undoAction.name)}</strong> retired. You can restore it for a few seconds.</span><div class="btn-row"><button class="btn secondary" type="button" id="undo-appliance">Undo</button><button class="btn secondary" type="button" id="dismiss-undo" aria-label="Dismiss undo message">Dismiss</button></div></div>`;
  }
  function bindUndoToast(){
    const undo=root.querySelector('#undo-appliance'),dismiss=root.querySelector('#dismiss-undo');
    if(dismiss)dismiss.addEventListener('click',()=>{state.undoAction=null;clearTimeout(state.undoTimer);showPage('appliances');});
    if(undo)undo.addEventListener('click',async()=>{const item=state.undoAction;if(!item)return;undo.disabled=true;try{const result=await api(`/api/customer/appliances/${item.id}/restore`,{method:'POST',body:JSON.stringify({version:item.version})});state.undoAction=null;clearTimeout(state.undoTimer);notice(result.message||`${item.name} restored.`,'success');await showPage('appliances');}catch(error){state.undoAction=null;clearTimeout(state.undoTimer);notice(errorText(error),'error');await showPage('appliances');}});
  }
  let weatherPromptedThisLaunch = false;
  let weatherRequestActive = false;
  function weatherModal() {
    if (weatherPromptedThisLaunch || !state.user || state.user.role !== 'customer') return;
    weatherPromptedThisLaunch = true;
    const wrap = document.createElement('div');
    wrap.className = 'pulse-prompt-backdrop';
    wrap.innerHTML = `<section class="pulse-prompt" role="dialog" aria-modal="true" aria-labelledby="weather-consent-title" aria-describedby="weather-consent-copy">
      <div class="eyebrow">Optional location · requested on each launch</div>
      <h2 id="weather-consent-title">Use local weather context?</h2>
      <p id="weather-consent-copy">If you allow location access, your browser will provide coordinates to retrieve local weather from Open-Meteo. The coordinates are used only for this session and are not saved by this app. Weather may help explain cooling-related demand, but cannot prove why usage changed.</p>
      <div class="btn-row"><button class="btn primary" id="weather-allow">Use my location</button><button class="btn secondary" id="weather-skip">Not now</button></div>
      <p class="small muted">You can skip this every time. The app continues normally without location or weather.</p>
    </section>`;
    document.body.appendChild(wrap);
    const allow=wrap.querySelector('#weather-allow'), skip=wrap.querySelector('#weather-skip');
    const opener=document.activeElement;
    const close=()=>{wrap.remove();if(opener?.isConnected)opener.focus({preventScroll:true});};
    skip.addEventListener('click',()=>{close();});
    allow.addEventListener('click',()=>{
      if(!navigator.geolocation){close();weatherPanelMessage('Location is unavailable in this browser. You can continue without weather.');return;}
      allow.disabled=true;allow.textContent='Requesting location…';
      navigator.geolocation.getCurrentPosition(async position=>{
        const {latitude,longitude,accuracy}=position.coords;
        close();
        await loadWeatherContext(latitude,longitude,accuracy);
      },error=>{
        close();
        const reason=error.code===1?'Location permission was denied.':error.code===2?'Your location could not be determined.':'Location request timed out.';
        weatherPanelMessage(`${reason} The app will continue without weather.`);
      },{enableHighAccuracy:true,timeout:12000,maximumAge:0});
    });
    wrap.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();close();}if(event.key==='Tab'&&event.shiftKey&&document.activeElement===allow){event.preventDefault();skip.focus();}else if(event.key==='Tab'&&!event.shiftKey&&document.activeElement===skip){event.preventDefault();allow.focus();}});
    allow.focus();
  }
  function weatherPanelMessage(message) {
    const node=document.getElementById('weather-context-content');
    if(node) node.innerHTML=`<p class="small muted">${esc(message)}</p>`;
  }
  async function loadWeatherContext(latitude,longitude,accuracy) {
    if(weatherRequestActive)return;
    if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||latitude < -90||latitude > 90||longitude < -180||longitude > 180){weatherPanelMessage('The browser returned invalid coordinates. Weather was skipped; meter analysis remains available.');return;}
    weatherRequestActive=true;
    weatherPanelMessage('Fetching local weather and comparing it with recent daily usage…');
    try {
      const params=new URLSearchParams({latitude:String(latitude),longitude:String(longitude),current:'temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,cloud_cover,wind_speed_10m',hourly:'temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,cloud_cover',past_days:'7',forecast_days:'1',timezone:'Asia/Manila'});
      const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),10000);
      let weather;
      try { const response=await fetch(`https://api.open-meteo.com/v1/forecast?${params}`,{signal:controller.signal,cache:'no-store',credentials:'omit'}); if(!response.ok)throw new Error(`Weather service returned ${response.status}.`); weather=await response.json(); }
      finally { clearTimeout(timer); }
      if(!weather.current||!weather.hourly||!Array.isArray(weather.hourly.time))throw new Error('Weather data was incomplete.');
      const current=weather.current, hourly=weather.hourly;
      const byDay=new Map();
      for(let i=0;i<hourly.time.length;i++){
        const day=String(hourly.time[i]).slice(0,10), temp=Number(hourly.temperature_2m?.[i]);
        if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Number.isFinite(temp)||temp < -80||temp > 65)continue;
        if(!byDay.has(day))byDay.set(day,[]);
        byDay.get(day).push(temp);
      }
      const weatherDaily=[...byDay.entries()].filter(([,temps])=>temps.length>=18).map(([date,temps])=>({date,temperature_c:temps.reduce((a,b)=>a+b,0)/temps.length,cooling_degree_days:temps.reduce((a,b)=>a+Math.max(0,b-24),0)/temps.length}));
      const pageData=window.__smeOverviewData;
      const usage=(pageData?.weekly||[]).filter(x=>Number(x.coverage_pct)>=80&&Number.isFinite(Number(x.total_kwh))&&Number(x.total_kwh)>=0).map(x=>({date:x.date,total_kwh:Number(x.total_kwh)}));
      const usageMap=new Map(usage.map(x=>[x.date,x.total_kwh]));
      const pairs=weatherDaily.filter(x=>usageMap.has(x.date)).map(x=>({usage:usageMap.get(x.date),temp:x.temperature_c,cdd:x.cooling_degree_days}));
      const pearson=(key)=>{if(pairs.length<5)return null;const a=pairs.map(x=>x.usage),b=pairs.map(x=>x[key]),ma=a.reduce((s,x)=>s+x,0)/a.length,mb=b.reduce((s,x)=>s+x,0)/b.length,va=a.reduce((s,x)=>s+(x-ma)**2,0),vb=b.reduce((s,x)=>s+(x-mb)**2,0);return va>1e-9&&vb>1e-9?Math.max(-1,Math.min(1,a.reduce((s,x,i)=>s+(x-ma)*(b[i]-mb),0)/Math.sqrt(va*vb))):null;};
      const tempCorrelation=pearson('temp'), cddCorrelation=pearson('cdd');
      const t=Number(current.temperature_2m), apparent=Number(current.apparent_temperature), humidity=Number(current.relative_humidity_2m), wind=Number(current.wind_speed_10m);
      const correlationText=tempCorrelation===null?`Only ${pairs.length} matched full-coverage days with meter data; more variation and history are needed.`:`Exploratory matched-day association: temperature r = ${tempCorrelation.toFixed(2)}; cooling-degree-day r = ${cddCorrelation===null?'—':cddCorrelation.toFixed(2)} across ${pairs.length} days. These are unadjusted associations, not proof of causation.`;
      const coolingText=t>=30?'Warm conditions may increase cooling demand in some households. Check the declared appliance mix and weekday baseline; do not assume air-conditioning is present.':t<=23?'Cooler conditions may reduce cooling demand, depending on household behavior.':'Current temperature alone is not enough to infer an electricity-use effect.';
      const accuracyText=Number.isFinite(accuracy)?(accuracy>10000?`Location accuracy is coarse (about ${Math.round(accuracy/1000)} km); nearby weather may not represent the property.`:`Device-reported location accuracy: about ${Math.round(accuracy)} m.`):'Device-reported location accuracy is unavailable.';
      const node=document.getElementById('weather-context-content');
      if(node)node.innerHTML=`<div class="stat-row"><span>Current temperature</span><strong>${Number.isFinite(t)?t.toFixed(1)+' °C':'—'}</strong></div><div class="stat-row"><span>Feels like · humidity</span><strong>${Number.isFinite(apparent)?apparent.toFixed(1)+' °C':'—'} · ${Number.isFinite(humidity)?humidity+'%':'—'}</strong></div><div class="stat-row"><span>Wind speed</span><strong>${Number.isFinite(wind)?wind.toFixed(1)+' km/h':'—'}</strong></div><div class="stat-row"><span>Matched full-coverage days</span><strong>${pairs.length}</strong></div><p class="small">${esc(coolingText)}</p><p class="small muted">${esc(correlationText)}</p><p class="small muted">${esc(accuracyText)} Coordinates were not stored by this app. Weather source: Open-Meteo. Cooling degree days use a 24 °C reference and are exploratory only.</p>`;
    } catch(error) {
      weatherPanelMessage(`${error.name==='AbortError'?'Weather request timed out.':error.message||'Weather could not be loaded.'} Meter analysis remains available without weather.`);
    } finally { weatherRequestActive=false; }
  }

  function renderOverview(d,day) {
    window.__smeOverviewData=d;
    const change=d.change_pct===null?'<span class="muted">Not enough comparable coverage</span>':`<span class="${d.change_pct>0?'up':'down'}">${d.change_pct>0?'+':''}${fmt(d.change_pct)}% vs previous week</span>`;
    announceNewAlerts(d.alerts);
    const alerts=d.alerts.length?d.alerts.map(a=>`<div class="alert-item ${['WATCH','CRITICAL'].includes(a.tier)?'attention':''}"><span class="alert-dot ${esc(a.tier)}"></span><div><div class="alert-title">${esc(a.title||a.type||'Usage pattern')}</div><div class="alert-copy">${esc(a.message||a.reason||'Review this usage pattern.')}</div></div><span class="alert-tier">${esc(a.tier)}</span></div>`).join(''):'<div class="empty">No customer alerts in this sample period.</div>';
    frame(`${pageHead('CUSTOMER OVERVIEW','Your energy at a glance',`Last 7 days · ${d.period.start} to ${d.period.end} · Synthetic meter readings`)}<section class="grid kpis"><article class="card"><div class="kpi-label">Recorded usage · 7 days</div><div class="kpi-value">${countValue(d.total_kwh,1,' kWh')}</div><div class="kpi-foot">${esc(d.period.start)} — ${esc(d.period.end)}</div></article><article class="card"><div class="kpi-label">Change vs previous week</div><div class="kpi-value">${d.change_pct===null?'—':`${d.change_pct>0?'+':''}${fmt(d.change_pct)}%`}</div><div class="kpi-foot">${change}</div></article><article class="card"><div class="kpi-label">Reading coverage</div><div class="kpi-value">${countValue(d.coverage_pct,1,'%')}</div><div class="kpi-foot">Expected 672 intervals · 15 minutes each</div></article><article class="card"><div class="kpi-label">Average demand</div><div class="kpi-value">${countValue(d.average_power_kw,2,' kW')}</div><div class="kpi-foot">Calculated from recorded energy</div></article></section>${getPrefs().energyRibbon?energyRibbon(day):''}<article class="card" style="margin:0 0 16px"><div class="card-head"><div><div class="eyebrow">ADAPTIVE INTELLIGENCE</div><h2>Baseline, change signals and forecast</h2><p>Robust MAD · EWMA · CUSUM · Bayesian evidence · weekday baseline · change-point scan</p></div><span class="pill">${esc(d.intelligence?.status||'unavailable').toUpperCase()}</span></div>${d.intelligence?.status==='ready'?`<div class="stat-row"><span>Recent robust baseline</span><strong>${fmt(d.intelligence.baseline_kwh,2)} kWh/day</strong></div><div class="stat-row"><span>Next-day expected usage</span><strong>${fmt(d.intelligence.forecast.expected_kwh,2)} kWh</strong></div><div class="stat-row"><span>Indicative range</span><strong>${fmt(d.intelligence.forecast.lower_kwh,2)}–${fmt(d.intelligence.forecast.upper_kwh,2)} kWh</strong></div><div class="stat-row"><span>Signals</span><strong>${d.intelligence.signals.length}</strong></div><div class="stat-row"><span>Bayesian anomaly estimate</span><strong>${fmt(Number(d.intelligence.bayesian_anomaly_probability||0)*100,1)}%</strong></div><div class="stat-row"><span>Ensemble evidence score</span><strong>${fmt(Number(d.intelligence.ensemble_score||0)*100,0)}/100</strong></div><div class="stat-row"><span>EWMA standardized shift</span><strong>${fmt(d.intelligence.ewma_z,2)}</strong></div><div class="stat-row"><span>Two-sided CUSUM · increase / decrease</span><strong>${fmt(d.intelligence.cusum_positive,2)} / ${fmt(d.intelligence.cusum_negative,2)}</strong></div><div class="stat-row"><span>Data quality · gaps / duplicates / rejected</span><strong>${d.intelligence.data_quality?.calendar_gaps?.length||0} / ${d.intelligence.data_quality?.duplicate_dates||0} / ${d.intelligence.data_quality?.rejected_rows||0}</strong></div><p class="small muted">${d.intelligence.signals.length?d.intelligence.signals.map(x=>esc(x.explanation)).join(' '):'No strong statistical signal in the latest daily aggregate.'}</p>${(d.intelligence.recommendations||[]).map(x=>`<p class="small">${esc(x)}</p>`).join('')}${d.intelligence.change_point?`<p class="small">Candidate ${esc(d.intelligence.change_point.direction)} change near ${esc(d.intelligence.change_point.after_date)} (${fmt(d.intelligence.change_point.relative_change_pct)}%). Requires confirmation.</p>`:''}<p class="small muted">${esc(d.intelligence.confidence)} confidence · ${d.intelligence.valid_days} valid days. ${esc(d.intelligence.forecast.warning)}</p>`:`<p class="small muted">${esc(d.intelligence?.message||'Insufficient data for adaptive intelligence.')}</p>`}</article><article class="card" style="margin:0 0 16px"><div class="card-head"><div><div class="eyebrow">WEATHER CONTEXT</div><h2>Local conditions and usage</h2><p>Optional location-based context · not a causal diagnosis</p></div><span class="pill">OPT-IN</span></div><div id="weather-context-content"><p class="small muted">Weather has not been requested for this launch.</p></div></article><article class="card pulse-card" style="margin-bottom:16px"><div class="card-head"><div><div class="eyebrow">PULSE RING</div><h2>Today's energy heartbeat</h2><p>24-hour radial view · each segment is one hour · interval energy in kWh</p></div><span class="pill">HOURLY VIEW</span></div>${pulseRing(day)}</article><section class="grid two-col"><article class="card"><div class="card-head"><div><h2>Daily consumption</h2><p>Recorded kWh per day · local time (Asia/Manila)</p></div><span class="pill">7 DAYS</span></div>${lineChart(d.weekly)}<div class="legend"><span>Meter readings</span><span style="color:var(--muted)">Missing intervals are not imputed</span></div></article><article class="card"><div class="card-head"><div><h2>Recent usage alerts</h2><p>Customer-safe summaries only</p></div><button class="btn secondary" data-page="alerts">View all</button></div><div class="alert-list">${alerts}</div></article></section><section class="card" style="margin-top:16px"><div class="card-head"><div><h2>Appliance estimate coverage</h2><p>Based on declared appliance specifications, not direct per-appliance meter measurements</p></div><span class="pill">${d.appliances.count} ACTIVE ITEMS</span></div><div class="stat-row"><span>Estimated coverage of total meter usage</span><strong>${d.appliances.coverage_pct===null?'—':fmt(d.appliances.coverage_pct)+'%'}</strong></div><div class="stat-row"><span>Largest listed category</span><strong>${esc(d.appliances.top_category||'Not available')}</strong></div><p class="small muted">Appliance entries are estimates. The meter measures household total consumption only.</p></section>`, 'overview');
    root.querySelectorAll('[data-page="alerts"]').forEach(b=>b.addEventListener('click',()=>showPage('alerts')));
    bindPulseTable(); bindTableToggle('weekly-table-toggle','weekly-table'); if(getPrefs().energyRibbon)bindEnergyRibbon(day); pulsePrompt(); weatherModal();
  }
  function renderDay(d) {
    const points = d.intervals;
    const max = Math.max(...points.map(p => p.energy_kwh ?? 0), .01) * 1.2;
    const width = 900, height = 250;
    const segments = [];
    let segment = [];
    points.forEach((point, i) => {
      if (point.energy_kwh === null || point.energy_kwh === undefined) {
        if (segment.length) segments.push(segment);
        segment = [];
        return;
      }
      const x = (i / 95) * width;
      const y = height - (point.energy_kwh / max) * (height - 28);
      segment.push(`${x},${y}`);
    });
    if (segment.length) segments.push(segment);
    const polylines = segments.map(group => `<polyline class="line" points="${group.join(' ')}"/>`).join('');
    const markers = points.map((point, i) => {
      if (!point.flagged || point.energy_kwh === null || point.energy_kwh === undefined) return '';
      const x = (i / 95) * width;
      const y = height - (point.energy_kwh / max) * (height - 28);
      return `<circle class="flagged-marker" cx="${x}" cy="${y}" r="5"><title>${esc(point.alert_tier || 'Alert')}: ${esc(point.reason || 'Detector alert')}</title></circle>`;
    }).join('');
    const rows = points.map(point => `<tr><td>${esc(point.time)}</td><td>${point.energy_kwh === null ? 'Missing' : fmt(point.energy_kwh, 4)}</td><td>${point.average_power_kw === null ? '—' : fmt(point.average_power_kw, 3)}</td><td>${esc(point.quality)}</td><td>${point.flagged ? `<span class="pill">${esc(point.alert_tier || 'FLAGGED')}</span>` : '—'}</td><td>${point.flagged ? esc(point.reason || '') : '—'}</td></tr>`).join('');
    const flaggedCount = points.filter(point => point.flagged).length;
    frame(`${pageHead('DAY EXPLORER', `15-minute intervals · ${d.date}`, 'Amber markers show saved customer-facing detector alerts with a plain-language reason.') }<section class="grid kpis"><article class="card"><div class="kpi-label">Total energy</div><div class="kpi-value">${countValue(d.summary.total_kwh,1,' kWh')}</div></article><article class="card"><div class="kpi-label">Data coverage</div><div class="kpi-value">${countValue(d.summary.coverage_pct,1,'%')}</div></article><article class="card"><div class="kpi-label">Intervals received</div><div class="kpi-value">${d.summary.received_intervals}<small class="muted" style="font-size:12px"> / 96</small></div></article><article class="card"><div class="kpi-label">Average demand</div><div class="kpi-value">${countValue(d.summary.average_power_kw,2,' kW')}</div></article></section>${getPrefs().energyRibbon?energyRibbon(d):''}<article class="card"><div class="card-head"><div><h2>15-minute interval profile</h2><p>Missing intervals remain gaps; they are not treated as zero. Markers come from persisted detector alerts, not synthetic generator labels.</p></div><span class="pill">${flaggedCount} FLAGGED SLOTS</span></div><p class="chart-summary">${d.summary.received_intervals} of 96 expected readings received (${fmt(d.summary.coverage_pct)}% coverage). ${flaggedCount} intervals have persisted customer-facing detector alerts. Missing values remain gaps.</p><svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="15-minute energy profile with amber detector alert markers. ${d.summary.received_intervals} of 96 readings received; ${flaggedCount} flagged intervals."><line class="gridline" x1="0" x2="${width}" y1="${height-28}" y2="${height-28}"/>${polylines}${markers}</svg></article><article class="card" style="margin-top:16px"><div class="card-head"><div><h2>Reading detail</h2><p>96 expected intervals · saved alert reasons are shown alongside their affected readings</p></div></div><p class="chart-summary">The complete table includes missing intervals and the reason for every saved customer-facing alert.</p><button class="btn secondary" id="day-table-toggle" aria-expanded="false" aria-controls="day-table">Show as a table</button><div class="table-wrap chart-table" id="day-table" hidden><table><caption>All 96 expected 15-minute readings, including missing intervals</caption><thead><tr><th>Local time</th><th>Energy (kWh)</th><th>Average power (kW)</th><th>Quality</th><th>Detector flag</th><th>Reason</th></tr></thead><tbody>${rows}</tbody></table></div></article>`, 'day');
    bindTableToggle('day-table-toggle','day-table'); if(getPrefs().energyRibbon)bindEnergyRibbon(d);
  }
  function renderHeatmap(d) {
    const maximum=Math.max(...d.days.flatMap(x=>x.blocks),0);
    const rows=d.days.map(day=>`<div class="heat-label">${esc(dateLabel(day.date))}<br><span class="small">${fmt(day.coverage_pct)}%</span></div>${day.blocks.map((v,i)=>{const intensity=Math.min(.85,Math.max(.1,v/Math.max(maximum,1)));const level=v===0?'L':v<=maximum*.33?'M':v<=maximum*.66?'H':'P';return `<div class="heat-cell level-${level.toLowerCase()}" title="${esc(d.labels[i])}: ${fmt(v)} kWh" aria-label="${esc(dateLabel(day.date))}, ${esc(d.labels[i])}: ${fmt(v)} kWh, level ${level}"><span>${level}</span><small>${fmt(v)}</small></div>`;}).join('')}`).join('');
    const maxPoint=d.days.flatMap(day=>day.blocks.map((value,index)=>({date:day.date,label:d.labels[index],value}))).sort((a,b)=>b.value-a.value)[0];
    const summary=maxPoint?`Highest six-hour block in this displayed week: ${maxPoint.label} on ${dateLabel(maxPoint.date)}, ${fmt(maxPoint.value,2)} kWh. Cell letters indicate relative intensity (L, M, H, P); the recorded kWh value is shown in each cell.`:'No readings are available for the selected period.';
    const tableRows=d.days.map(day=>`<tr><th scope="row">${esc(day.date)}</th>${day.blocks.map(v=>`<td>${fmt(v,3)} kWh</td>`).join('')}<td>${fmt(day.coverage_pct,1)}%</td></tr>`).join('');
    frame(`${pageHead('USAGE PATTERNS','Weekly usage heatmap','Each cell aggregates six hours of recorded energy. Colour intensity is relative to this displayed period.') }<article class="card"><div class="card-head"><div><h2>Daily profile by time block</h2><p>kWh totals · local time · partial days show received coverage</p></div><span class="pill">7 DAYS</span></div><div class="heatmap"><div></div>${d.labels.map(x=>`<div class="heat-label heat-head">${esc(x)}</div>`).join('')}${rows}</div><div class="heat-legend"><span><b>L</b> Low</span><span><b>M</b> Medium</span><span><b>H</b> High</span><span><b>P</b> Peak</span></div><p class="chart-summary">${esc(summary)} Missing intervals remain absent and are not treated as zero-consumption observations.</p><button class="btn secondary" id="heatmap-table-toggle" aria-expanded="false" aria-controls="heatmap-table">Show as a table</button><div class="footer">The heatmap is descriptive only. It does not identify an appliance or infer a cause.</div></article><div class="table-wrap chart-table" id="heatmap-table" hidden><table><caption>Six-hour usage totals by day</caption><thead><tr><th>Date</th>${d.labels.map(label=>`<th>${esc(label)} (kWh)</th>`).join('')}<th>Coverage</th></tr></thead><tbody>${tableRows}</tbody></table></div>`,'heatmap');
    bindTableToggle('heatmap-table-toggle','heatmap-table');
  }
  function renderAlerts(d) {
    announceNewAlerts(d.alerts);
    const rows=d.alerts.length?d.alerts.map(a=>`<div class="alert-item ${['WATCH','CRITICAL'].includes(a.tier)?'attention':''}"><span class="alert-dot ${esc(a.tier)}"></span><div><div class="alert-title">${esc(a.title||a.type||'Usage pattern')}</div><div class="alert-copy">${esc(a.message||a.reason||'')}<br><span class="muted">${esc(a.created_at||'')}</span></div></div><span class="alert-tier">${esc(a.tier)}</span></div>`).join(''):'<div class="empty">No customer-facing alerts were generated in this simulated period.</div>';
    frame(`${pageHead('ALERTS','Usage pattern alerts','Alerts are generated from local simulated readings. They are not a diagnosis, enforcement finding, or service notice.')}<article class="card"><div class="alert-list">${rows}</div></article>`, 'alerts');
  }
  async function renderStory(d) {
    frame(`${pageHead('ENERGY STORY','A readable summary','This summary and its suggestions use computed facts. Suggestions are cautious prompts, not guaranteed savings or electrical advice.',`<select id="story-language" aria-label="Story language" class="pill"><option value="en">English</option><option value="fil">Filipino</option></select>`)}<article class="card"><div class="eyebrow">${esc(d.engine)} · ${d.validator_passed?'VALIDATED':'NOT VALIDATED'}</div><h2 style="font-size:22px;line-height:1.6;font-weight:550">${esc(d.story)}</h2><div class="stat-row"><span>Period</span><strong>${esc(d.fact_sheet.period_start)} — ${esc(d.fact_sheet.period_end)}</strong></div><div class="stat-row"><span>Recorded usage</span><strong>${fmt(d.fact_sheet.total_kwh)} kWh</strong></div><div class="stat-row"><span>Coverage</span><strong>${fmt(d.fact_sheet.coverage_pct)}%</strong></div><div class="stat-row"><span>Data source</span><strong>Simulated meter readings</strong></div></article><article class="card"><div class="card-head"><div><h2>Suggestions to review</h2><p>Fact-grounded prompts; no guaranteed savings or electrical repair advice.</p></div><span class="pill">${esc(d.recommendations?.engine||'template')}</span></div><ul class="recommendation-list">${(d.recommendations?.items||[]).map(item=>`<li>${esc(item)}</li>`).join('')}</ul><p class="small muted">${d.recommendations?.engine==='local_llm'?'Generated by your verified local model and checked against the computed fact sheet.':'Generated from deterministic rules. Enable a verified local Ollama model to optionally rephrase suggestions.'}</p></article>`, 'story');
    root.querySelector('#story-language').value=new URLSearchParams(location.search).get('language')||'en';root.querySelector('#story-language').addEventListener('change',async ev=>{try{const fresh=await api(`/api/customer/story?language=${encodeURIComponent(ev.target.value)}`);renderStory(fresh);}catch(e){notice(errorText(e),'error');showPage('story');}});
  }
  function renderAppliances(d) {
    const items=d.appliances.map(a=>`<tr><td><strong>${esc(a.name)}</strong><div class="muted small">${esc(a.category_label)}</div></td><td>${fmt(a.rated_power_w,0)} W</td><td>${a.quantity}</td><td>${fmt(a.hours_per_day,2)} h/day</td><td>${fmt(a.declared_kwh_per_week)} kWh</td><td><button class="btn secondary" data-edit="${esc(a.id)}">Edit</button> <button class="btn danger" data-remove="${esc(a.id)}">Retire</button></td></tr>`).join('');
    const categories=Object.entries(d.categories||{}).map(([key,label])=>`<option value="${esc(key)}">${esc(label)}</option>`).join('');
    frame(`${renderUndoToast()}${pageHead('APPLIANCE ESTIMATES','Your listed appliances','These are estimates based on rated power, quantity, duty, and use schedule. They are not measured separately by the meter.')}${getPrefs().whatIfMorph?whatIfPanel(d.appliances):''}<section class="grid two-col"><article class="card"><div class="card-head"><div><h2>Appliances you listed</h2><p>Up to 30 active items · versioned estimates</p></div><span class="pill">${d.appliances.length} ITEMS</span></div>${items?`<div class="table-wrap"><table><thead><tr><th>Appliance</th><th>Rated power</th><th>Qty</th><th>Hours</th><th>Estimate / week</th><th>Action</th></tr></thead><tbody>${items}</tbody></table></div>`:'<div class="empty">No appliances listed yet. Add one to create an estimate.</div>'}</article><article class="card"><div class="card-head"><div><h2 id="appliance-form-title">Add an appliance</h2><p>Enter the nameplate rating and typical schedule.</p></div></div><form id="appliance-form" class="form-grid"><input type="hidden" name="id"><input type="hidden" name="version"><div class="field full"><label>Appliance name</label><input name="name" required maxlength="60" placeholder="e.g. Bedroom air conditioner"></div><div class="field"><label>Category</label><select name="category">${categories}</select></div><div class="field"><label>Rated power (W)</label><input name="rated_power_w" type="number" min="1" max="20000" step="0.01" required></div><div class="field"><label>Quantity</label><input name="quantity" type="number" min="1" max="99" step="1" value="1" required></div><div class="field"><label>Duty (%)</label><input name="duty_pct" type="number" min="1" max="100" step="0.1" value="100" required></div><div class="field"><label>Hours per day</label><input name="hours_per_day" type="number" min="0" max="24" step="0.25" value="4" required></div><div class="field"><label>Days per week</label><input name="days_per_week" type="number" min="1" max="7" step="1" value="7" required></div><div class="field full"><label>Private note (not used in model explanations)</label><textarea name="notes" maxlength="200"></textarea></div><div class="field full btn-row"><button class="btn primary" type="submit">Save appliance</button><button class="btn secondary" type="button" id="reset-appliance">Clear</button></div><div class="field full small muted" id="appliance-preview">Estimated weekly energy will be calculated when saved.</div></form></article></section>`, 'appliances');
    const form=root.querySelector('#appliance-form');form.addEventListener('submit',saveAppliance);root.querySelector('#reset-appliance').addEventListener('click',()=>form.reset());
    if(getPrefs().whatIfMorph)bindWhatIf(d.appliances);bindUndoToast();
    root.querySelectorAll('[data-edit]').forEach(b=>b.addEventListener('click',()=>{const a=d.appliances.find(x=>x.id===b.dataset.edit);if(!a)return;for(const key of ['name','category','rated_power_w','quantity','duty_pct','hours_per_day','days_per_week','notes'])form.elements[key].value=a[key];form.elements.id.value=a.id;form.elements.version.value=a.version;root.querySelector('#appliance-form-title').textContent='Edit appliance';form.querySelector('button[type=submit]').textContent='Update appliance';form.scrollIntoView({behavior:getPrefs().reducedMotion?'auto':'smooth',block:'center'});}));
    root.querySelectorAll('[data-remove]').forEach(b=>b.addEventListener('click',async()=>{const a=d.appliances.find(x=>x.id===b.dataset.remove);if(!a||!confirm(`Retire ${a.name}? Earlier estimate history will be retained.`))return;b.disabled=true;try{const result=await api(`/api/customer/appliances/${a.id}`,{method:'DELETE',body:JSON.stringify({action:'retire',version:a.version})});state.undoAction=getPrefs().undoToast?{id:a.id,name:a.name,version:result.version}:null;if(state.undoTimer)clearTimeout(state.undoTimer);if(state.undoAction)state.undoTimer=setTimeout(()=>{state.undoAction=null;root.querySelector('#undo-toast')?.remove();},10000);notice(result.message||'Appliance retired.','success');await showPage('appliances');}catch(e){notice(errorText(e),'error');await showPage('appliances');}}));
  }
  async function saveAppliance(ev) {
    ev.preventDefault();const form=ev.target;const f=new FormData(form);const body={name:f.get('name'),category:f.get('category'),rated_power_w:f.get('rated_power_w'),quantity:Number(f.get('quantity')),duty_pct:f.get('duty_pct'),hours_per_day:f.get('hours_per_day'),days_per_week:Number(f.get('days_per_week')),notes:f.get('notes')};const id=f.get('id');if(id)body.version=Number(f.get('version'));const btn=form.querySelector('button[type=submit]');btn.disabled=true;
    try{await api(id?`/api/customer/appliances/${id}`:'/api/customer/appliances',{method:id?'PUT':'POST',body:JSON.stringify(body)});notice('Appliance saved. Estimates now reflect the current entry.','success');await showPage('appliances');}catch(e){notice(errorText(e),'error');await showPage('appliances');}finally{if(form.querySelector('button[type=submit]'))form.querySelector('button[type=submit]').disabled=false;}
  }
  async function renderSettings(d) {
    const prefs=getPrefs();
    const toggle=(name,label,description)=>`<label class="check preference-row"><input type="checkbox" name="${name}" ${prefs[name]?'checked':''}><span><strong>${label}</strong><small>${description}</small></span></label>`;
    const consentRows=Object.entries(d.consent||{}).map(([key,value])=>`<div class="stat-row"><span>${esc(key)}</span><strong>${esc(value?.status|| (value?'granted':'not decided'))}</strong></div>`).join('');
    frame(`${pageHead('PRIVACY AND CONTROL','Your data and settings','Manage local notifications, optional Pulse enhancements, privacy, and simulated data.')}<section class="grid two-col"><article class="card"><div class="card-head"><div><h2>Notification settings</h2><p>Nothing is sent outside this local application.</p></div></div><form id="settings-form" class="grid" style="gap:15px"><div class="field"><label>Language</label><select name="language"><option value="en">English</option><option value="fil">Filipino</option></select></div><label class="check"><input name="push_alerts" type="checkbox" ${d.push_alerts?'checked':''}><span>Enable mock push notification records (optional consent required).</span></label><label class="check"><input name="sms_alerts" type="checkbox" ${d.sms_alerts?'checked':''}><span>Enable mock SMS notification records (optional consent required).</span></label><button class="btn primary" type="submit">Save settings</button></form></article><article class="card"><div class="card-head"><div><h2>Pulse experience</h2><p>New installations enable optional enhancements by default. Audio and haptics wait for a user gesture; nothing autoplays.</p></div></div><form id="experience-form" class="grid" style="gap:13px">${toggle('soundEnabled','Interface sounds','Enabled by default at a low volume; audio starts only after a user gesture.')}${toggle('interactionSounds','Interaction sounds','Quiet feedback for taps and successful actions.')}${toggle('alertChimes','Alert chimes','Gentle chime for newly detected local alerts; muted while the tab is hidden.')}<div class="field"><label for="sound-volume">Sound volume · <output id="sound-volume-value">${Math.round(prefs.volume*100)}%</output></label><input id="sound-volume" name="volume" type="range" min="0" max="50" step="1" value="${Math.round(prefs.volume*100)}"></div><div class="settings-subhead">Optional interface features</div>${toggle('energyRibbon','Energy Ribbon','Hourly timeline and keyboard-accessible scrubber on the day explorer and overview.')}${toggle('whatIfMorph','What-if appliance preview','Simulate a usage schedule without changing stored appliance data.')}${toggle('sharedTransitions','Shared screen transitions','Uses native View Transitions when supported; CSS screen-entry motion otherwise.')}${toggle('scrollReveals','Scroll-driven reveals','Feature detected; only transform and opacity are animated.')}${toggle('countUpNumbers','Count-up metrics','Brief number count-up with final values available to assistive technology.')}${toggle('haptics','Haptic taps','Short vibration on supported devices. Disabled by Calm Mode.')}${toggle('undoToast','Undo appliance retirement','Version-checked restore action available for ten seconds after retirement.')}<div class="settings-subhead">Accessibility</div>${toggle('reducedMotion','Reduce motion','Disables motion effects; the operating-system preference is respected too.')}${toggle('calmMode','Calm Mode','Temporarily suppresses motion, sound, and haptics without changing your individual preferences.')}<div class="btn-row"><button class="btn primary" type="submit">Save experience settings</button><button class="btn secondary" type="button" id="sound-test">Test sound</button></div><p class="small muted">Settings are stored in this browser only. Optional features never block or delay a server-confirmed action.</p></form></article><article class="card"><div class="card-head"><div><h2>Consent history</h2><p>Latest decision for each purpose</p></div></div>${consentRows}<div class="notice info" style="margin-top:17px">Withdrawing the required usage permission immediately blocks dashboard and alert access. You can review consent again after withdrawal.</div><button class="btn danger" id="withdraw">Withdraw all consent</button></article></section><section class="card" style="margin-top:16px"><div class="card-head"><div><h2>Data controls</h2><p>Export your records or remove the simulated dataset. Consent decisions are retained as an audit history.</p></div></div><div class="btn-row"><button class="btn secondary" id="export">Export my data (JSON)</button><button class="btn danger" id="delete-data">Delete simulated readings and appliances</button></div></section>`, 'settings');
    root.querySelector('#settings-form').elements.language.value=d.language;
    root.querySelector('#settings-form').addEventListener('submit',async ev=>{ev.preventDefault();const f=new FormData(ev.target);try{await api('/api/customer/settings',{method:'PUT',body:JSON.stringify({language:f.get('language'),push_alerts:ev.target.elements.push_alerts.checked,sms_alerts:ev.target.elements.sms_alerts.checked})});notice('Settings saved.','success');await showPage('settings');}catch(e){notice(errorText(e),'error');await showPage('settings');}});
    const exp=root.querySelector('#experience-form'),vol=root.querySelector('#sound-volume'),volOut=root.querySelector('#sound-volume-value');
    vol.addEventListener('input',()=>volOut.value=`${vol.value}%`);
    exp.addEventListener('submit',ev=>{ev.preventDefault();const f=ev.target.elements;savePrefs({soundEnabled:f.soundEnabled.checked,interactionSounds:f.interactionSounds.checked,alertChimes:f.alertChimes.checked,volume:Number(f.volume.value)/100,energyRibbon:f.energyRibbon.checked,whatIfMorph:f.whatIfMorph.checked,sharedTransitions:f.sharedTransitions.checked,scrollReveals:f.scrollReveals.checked,countUpNumbers:f.countUpNumbers.checked,haptics:f.haptics.checked,undoToast:f.undoToast.checked,reducedMotion:f.reducedMotion.checked,calmMode:f.calmMode.checked});notice('Experience preferences saved on this browser.','success');showPage('settings');});
    root.querySelector('#sound-test').addEventListener('click',()=>{savePrefs({soundEnabled:true,calmMode:false});const resumed=ensureAudioFromGesture();if(resumed&&resumed.then)resumed.then(()=>playTone('success','test'));});
    root.querySelector('#withdraw').addEventListener('click',async()=>{if(!confirm('Withdraw required usage analytics and all optional notification consent? Dashboard access will be blocked until consent is granted again.'))return;try{await api('/api/customer/consent/withdraw',{method:'POST',body:JSON.stringify({})});notice('Consent withdrawn. You will review consent again before continuing.','success');await renderConsent();}catch(e){notice(errorText(e),'error');await showPage('settings');}});
    root.querySelector('#export').addEventListener('click',async()=>{let url;try{const result=await api('/api/customer/export');const blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json'});url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='smart-meter-explorer-export.json';a.click();}catch(e){notice(errorText(e),'error');await showPage('settings');}finally{if(url)setTimeout(()=>URL.revokeObjectURL(url),1000);}});
    root.querySelector('#delete-data').addEventListener('click',async()=>{if(!confirm('Permanently delete the simulated readings, generated alerts, stories, and appliance entries for this demo customer? Consent history and account will remain.'))return;try{await api('/api/customer/sample-data',{method:'DELETE',body:JSON.stringify({confirm:true})});notice('Simulated data deleted.','success');await showPage('settings');}catch(e){notice(errorText(e),'error');await showPage('settings');}});
  }
  function renderQueue(d) {
    const rows=d.leads.length?d.leads.map(a=>`<tr><td>${esc(a.type)}</td><td>${esc(a.tier)}</td><td>${esc(a.reason)}</td><td>${esc(a.window_start)}</td><td><select data-review-status="${esc(a.id)}"><option value="reviewed">Reviewed</option><option value="field_check_requested">Field check requested</option></select> <button class="btn secondary" data-review="${esc(a.id)}">Save</button></td></tr>`).join(''):'<tr><td colspan="5" class="empty">No internal review items.</td></tr>';
    frame(`${pageHead('INTERNAL REVIEW','Pattern review queue','Internal-only pattern leads from simulated data. These are not evidence of theft or wrongdoing.')}${d.safe_mode==='read_only'?'<div class="notice error">Safe mode is active. Review actions are paused.</div>':''}<article class="card"><div class="table-wrap"><table><thead><tr><th>Pattern type</th><th>Tier</th><th>Reason</th><th>Window start</th><th>Review action</th></tr></thead><tbody>${rows}</tbody></table></div></article>`, 'queue');
    root.querySelectorAll('[data-review]').forEach(b=>b.addEventListener('click',async()=>{try{const id=b.dataset.review;await api(`/api/internal/queue/${id}/review`,{method:'POST',body:JSON.stringify({status:root.querySelector(`[data-review-status="${id}"]`).value})});notice('Review status saved.','success');await showPage('queue');}catch(e){notice(errorText(e),'error');await showPage('queue');}}));
  }
  function renderProtection(d) {
    frame(`<div class="security-silent">${pageHead('SYSTEM PROTECTION','Local security status','Safe mode prevents protected writes. Unlock requires two different active administrators and a second one-time approval code.')}<section class="grid kpis"><article class="card"><div class="kpi-label">Application mode</div><div class="kpi-value" style="font-size:23px">${esc(d.mode.toUpperCase())}</div><div class="kpi-foot">${esc(d.reason_code)}</div></article><article class="card"><div class="kpi-label">Network boundary</div><div class="kpi-value" style="font-size:23px">LOCALHOST</div><div class="kpi-foot">No remote listener permitted</div></article><article class="card"><div class="kpi-label">Audit integrity</div><div class="kpi-value" style="font-size:23px">${esc(d.integrity)}</div><div class="kpi-foot">Checked during application startup</div></article><article class="card"><div class="kpi-label">Last security event</div><div class="kpi-value" style="font-size:17px">${esc(d.last_security_event?.reason_code||'None recorded')}</div><div class="kpi-foot">${esc(d.last_security_event?.occurred_at||'')}</div></article></section><section class="grid two-col"><article class="card"><h2 style="font-size:14px">Lock the application</h2><p class="muted small" style="line-height:1.6">Switch the app into read-only mode. This is available to administrators.</p><button class="btn danger" id="lock-app">Enter read-only safe mode</button></article><article class="card"><h2 style="font-size:14px">Unlock (two-person approval)</h2><p class="muted small" style="line-height:1.6">A different administrator must approve. The one-time code is written only to the server terminal.</p><form id="unlock-start" class="grid" style="gap:10px"><div class="field"><label>Second administrator username</label><input name="username" required></div><div class="field"><label>Second administrator passphrase</label><input name="password" type="password" required></div><button class="btn secondary" type="submit">Request second approval</button></form><form id="unlock-finish" class="grid" style="gap:10px;margin-top:20px"><div class="field"><label>Approval challenge ID</label><input name="challenge" required></div><div class="field"><label>Second administrator one-time code</label><input name="code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required></div><div class="field"><label>Your current administrator passphrase</label><input name="current" type="password" required></div><button class="btn primary" type="submit">Unlock safely</button></form></article></section></div>`, 'protection');
    root.querySelector('#lock-app').addEventListener('click',async()=>{if(!confirm('Lock protected application actions in read-only safe mode?'))return;try{await api('/api/internal/safe-mode/lock',{method:'POST',body:JSON.stringify({})});notice('Read-only safe mode enabled.','success');await showPage('protection');}catch(e){notice(errorText(e),'error');await showPage('protection');}});
    root.querySelector('#unlock-start').addEventListener('submit',async ev=>{ev.preventDefault();const f=new FormData(ev.target);try{const r=await api('/api/internal/safe-mode/approval/start',{method:'POST',body:JSON.stringify({username:f.get('username'),password:f.get('password')})});root.querySelector('#unlock-finish').elements.challenge.value=r.challenge_id;notice(r.message,'success');}catch(e){notice(errorText(e),'error');await showPage('protection');}});
    root.querySelector('#unlock-finish').addEventListener('submit',async ev=>{ev.preventDefault();const f=new FormData(ev.target);try{await api('/api/internal/safe-mode/unlock',{method:'POST',body:JSON.stringify({approval_challenge_id:f.get('challenge'),approval_code:f.get('code'),current_password:f.get('current')})});notice('Safe mode unlocked with two-person approval.','success');await showPage('protection');}catch(e){notice(errorText(e),'error');await showPage('protection');}});
  }
  function renderGenericError(page){frame(`${pageHead('REQUEST NOT COMPLETED','This view could not load','Review the error above. If it continues, include the request reference ID when reporting the issue.')}<article class="card"><button class="btn secondary" id="retry">Retry</button></article>`,page);root.querySelector('#retry').addEventListener('click',()=>showPage(page));}
  function renderUnavailable(message){state.shellRole=null;root.innerHTML=`<div class="screen-center"><section class="card wide-card"><span class="mark">SME</span><div class="eyebrow" style="margin-top:25px">LOCAL SETUP REQUIRED</div><h1 style="font-size:30px">The workspace is not ready yet.</h1><p class="muted" style="line-height:1.7">${esc(message)}</p><div class="notice info">Start the local MySQL service, apply the schema migration, seed the synthetic demonstration dataset, then start the application on 127.0.0.1.</div><p class="small muted">See README.md in the project folder. No data is sent to a remote service.</p><button class="btn secondary" onclick="location.reload()">Retry connection</button></section></div>`;}
  boot();
})();
