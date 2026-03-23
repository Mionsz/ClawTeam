import { useEffect, useRef } from "react";
import logo from "../../assets/icon.png";

const clients = ["Claude Code", "Codex", "OpenClaw", "nanobot", "Any CLI"];
const orbitClients = [
  { key: "codex", label: "Codex" },
  { key: "claude", label: "Claude Code" },
  { key: "openclaw", label: "OpenClaw" },
  { key: "nanobot", label: "nanobot" },
  { key: "any", label: "Any CLI" }
];
const features = [
  { title: "Shared task graph", body: "One board for blockers, priority, ownership, and progress across all agents." },
  { title: "Persistent coordination", body: "Handoffs, aliases, and notes stay visible after prompts scroll away." },
  { title: "Git-aware execution", body: "Real repos, worktrees, diffs, and mergeable state keep the swarm grounded." }
];
const steps = [
  { num: "01", title: "Install", body: "Get the CLI. Add P2P transport when the team needs it.", code: 'pip install clawteam\npip install "clawteam[p2p]"' },
  { num: "02", title: "Model the work", body: "Create a team and define tasks so the board tracks the project.", code: 'clawteam team spawn-team my-team -d "Docs + engineering"\nclawteam task create my-team "Build landing page" --priority urgent' },
  { num: "03", title: "Spawn agents", body: "Run any terminal-native client from the same surface.", code: "clawteam spawn tmux claude-code --team my-team --agent-name builder\nclawteam spawn tmux codex --team my-team --agent-name reviewer" }
];
const docs = [
  { title: "Quick Start", body: "Install to first running swarm.", href: "https://github.com/HKUDS/ClawTeam#-quick-start" },
  { title: "Skill Guide", body: "Agent-facing operating guide.", href: "skills/clawteam/SKILL.md" },
  { title: "CLI Reference", body: "Commands, flags, and runtime details.", href: "skills/clawteam/references/cli-reference.md" },
  { title: "Workflows", body: "Practical patterns for real teams.", href: "skills/clawteam/references/workflows.md" }
];

function HalfGlobe() {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas.getContext("2d");
    let w = 0, h = 0, dpr = 1, R = 0, rot = 0, raf = 0;
    let tilt = -0.45;
    const agents = [
      // upper arc (south pole region, appears at top)
      { theta: 0.3, phi: 2.6,  r: 249, g: 115, b: 22 },
      { theta: 1.5, phi: 2.5,  r: 129, g: 140, b: 248 },
      { theta: 2.7, phi: 2.7,  r: 34,  g: 197, b: 94 },
      { theta: 3.8, phi: 2.55, r: 249, g: 115, b: 22 },
      { theta: 5.0, phi: 2.65, r: 129, g: 140, b: 248 },
      // middle band
      { theta: 0.8, phi: 2.1,  r: 34,  g: 197, b: 94 },
      { theta: 1.9, phi: 2.2,  r: 249, g: 115, b: 22 },
      { theta: 3.2, phi: 2.0,  r: 129, g: 140, b: 248 },
      { theta: 4.4, phi: 2.15, r: 34,  g: 197, b: 94 },
      { theta: 5.6, phi: 2.1,  r: 249, g: 115, b: 22 },
      // lower band (equator, appears near bottom edge)
      { theta: 0.5, phi: 1.6,  r: 129, g: 140, b: 248 },
      { theta: 1.7, phi: 1.5,  r: 249, g: 115, b: 22 },
      { theta: 3.0, phi: 1.55, r: 34,  g: 197, b: 94 },
      { theta: 4.2, phi: 1.65, r: 129, g: 140, b: 248 },
      { theta: 5.4, phi: 1.5,  r: 249, g: 115, b: 22 }
    ];
    const conns = [[0,1],[1,2],[2,3],[3,4],[4,0],[0,5],[1,6],[2,7],[3,8],[4,9],[5,6],[6,7],[7,8],[8,9],[9,5],[5,10],[6,11],[7,12],[8,13],[9,14],[10,11],[11,12],[12,13],[13,14],[14,10]];
    const sph = (t, p) => ({ x: Math.sin(p)*Math.cos(t), y: Math.cos(p), z: Math.sin(p)*Math.sin(t) });
    const rX = (p, a) => { const c=Math.cos(a),s=Math.sin(a); return {x:p.x, y:p.y*c-p.z*s, z:p.y*s+p.z*c}; };
    const rY = (p, a) => { const c=Math.cos(a),s=Math.sin(a); return {x:p.x*c-p.z*s, y:p.y, z:p.x*s+p.z*c}; };
    const xform = (t, p) => rX(rY(sph(t, p), rot), tilt);
    const cx = () => w * 0.5;
    const cy = () => h + R * 0.08;
    const proj = (p) => { const d=3.2, sc=d/(d-p.z); return {x:cx()+p.x*R*sc, y:cy()+p.y*R*sc, z:p.z, scale:sc}; };

    const resize = () => {
      const rc = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio||1, 2);
      w = rc.width; h = rc.height;
      R = w * 0.3;
      canvas.width = Math.round(w*dpr); canvas.height = Math.round(h*dpr);
      ctx.setTransform(dpr,0,0,dpr,0,0);
    };

    const onScroll = () => {
      const rect = canvas.getBoundingClientRect();
      const vh = window.innerHeight;
      const center = rect.top + rect.height / 2;
      const progress = Math.max(0, Math.min(1, 1 - center / vh));
      tilt = -1.4 + progress * 2.8;
    };

    const drawGrid = () => {
      const glow = ctx.createRadialGradient(cx(),cy(),0, cx(),cy(),R*1.15);
      glow.addColorStop(0,"rgba(99,102,241,0.05)"); glow.addColorStop(0.4,"rgba(249,115,22,0.025)"); glow.addColorStop(1,"transparent");
      ctx.beginPath(); ctx.arc(cx(),cy(),R*1.15,0,Math.PI*2); ctx.fillStyle=glow; ctx.fill();
      ctx.lineWidth=1;
      for(let i=0;i<13;i++){const phi=((i+1)/14)*Math.PI; ctx.beginPath(); ctx.strokeStyle="rgba(148,163,184,0.16)"; let on=false;
        for(let j=0;j<=100;j++){const p=proj(xform((j/100)*Math.PI*2,phi)); if(p.z<-0.35||p.y>h+5){on=false;continue;} if(!on){ctx.moveTo(p.x,p.y);on=true;}else ctx.lineTo(p.x,p.y);} ctx.stroke();}
      for(let i=0;i<20;i++){const t=(i/20)*Math.PI*2; ctx.beginPath(); ctx.strokeStyle="rgba(148,163,184,0.16)"; let on=false;
        for(let j=0;j<=100;j++){const p=proj(xform(t,(j/100)*Math.PI)); if(p.z<-0.35||p.y>h+5){on=false;continue;} if(!on){ctx.moveTo(p.x,p.y);on=true;}else ctx.lineTo(p.x,p.y);} ctx.stroke();}
      ctx.beginPath(); ctx.arc(cx(),cy(),R*1.08,0,Math.PI*2);
      ctx.setLineDash([6,12]); ctx.strokeStyle="rgba(148,163,184,0.1)"; ctx.lineWidth=1; ctx.stroke(); ctx.setLineDash([]);
    };

    const drawConns = () => {
      conns.forEach(([i,j])=>{
        const a=proj(xform(agents[i].theta,agents[i].phi)), b=proj(xform(agents[j].theta,agents[j].phi));
        if(a.z<-0.5||b.z<-0.5||a.y>h||b.y>h) return;
        const fade=Math.min((a.z+0.5)/0.8,(b.z+0.5)/0.8), dist=Math.hypot(b.x-a.x,b.y-a.y);
        if(dist<2) return;
        const mx=(a.x+b.x)/2, my=(a.y+b.y)/2, nx=-(b.y-a.y)/dist, ny=(b.x-a.x)/dist;
        ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.quadraticCurveTo(mx+nx*dist*0.12,my+ny*dist*0.12,b.x,b.y);
        ctx.strokeStyle=`rgba(148,163,184,${0.13*fade})`; ctx.lineWidth=0.8; ctx.stroke();
      });
    };

    const drawAgents = (time) => {
      agents.forEach(agent=>{
        const p=proj(xform(agent.theta,agent.phi));
        if(p.z<-0.5||p.y>h) return;
        const fade=Math.min(1,(p.z+0.5)/0.8), pulse=1+0.2*Math.sin(time*0.002+agent.theta*5);
        const {r,g,b}=agent, gr=26*p.scale*pulse;
        const grd=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,gr);
        grd.addColorStop(0,`rgba(${r},${g},${b},${0.4*fade})`); grd.addColorStop(1,"transparent");
        ctx.beginPath(); ctx.arc(p.x,p.y,gr,0,Math.PI*2); ctx.fillStyle=grd; ctx.fill();
        ctx.beginPath(); ctx.arc(p.x,p.y,4.5*p.scale*pulse,0,Math.PI*2); ctx.fillStyle=`rgba(${r},${g},${b},${0.95*fade})`; ctx.fill();
        ctx.beginPath(); ctx.arc(p.x,p.y,10*p.scale*pulse,0,Math.PI*2); ctx.strokeStyle=`rgba(${r},${g},${b},${0.2*fade})`; ctx.lineWidth=1; ctx.stroke();
      });
    };

    const draw = (time) => { ctx.clearRect(0,0,w,h); drawGrid(); drawConns(); drawAgents(time); rot+=0.0018; raf=requestAnimationFrame(draw); };
    resize(); onScroll(); draw(0);
    window.addEventListener("resize",resize); window.addEventListener("scroll",onScroll,{passive:true});
    return ()=>{ cancelAnimationFrame(raf); window.removeEventListener("resize",resize); window.removeEventListener("scroll",onScroll); };
  },[]);

  return (
    <div className="globe-section">
      <div className="globe-glow" aria-hidden="true" />
      <canvas ref={ref} className="globe-canvas" aria-hidden="true" />
      {orbitClients.map(c=><span key={c.key} className={`orbit-label orbit-${c.key}`}>{c.label}</span>)}
      <div className="globe-fade-top" aria-hidden="true" />
      <div className="globe-fade-bottom" aria-hidden="true" />
    </div>
  );
}

function TerminalMockup() {
  return (
    <div className="terminal">
      <div className="terminal-bar"><span className="terminal-dot"/><span className="terminal-dot"/><span className="terminal-dot"/><span className="terminal-title">clawteam</span></div>
      <div className="terminal-body">
        <div className="terminal-line"><span className="t-prompt">$</span> clawteam team spawn-team docs-sprint</div>
        <div className="terminal-line t-output"><span className="t-success">{"\u2713"}</span> Team &quot;docs-sprint&quot; created</div><br/>
        <div className="terminal-line"><span className="t-prompt">$</span> clawteam spawn tmux claude-code --agent-name builder</div>
        <div className="terminal-line t-output"><span className="t-active">{"\u25cf"}</span> Agent &quot;builder&quot; spawned in tmux</div><br/>
        <div className="terminal-line"><span className="t-prompt">$</span> clawteam team status docs-sprint</div>
        <div className="terminal-output-block">
          <div className="t-status-header">docs-sprint <span className="t-dim">3 agents active</span></div>
          <div className="t-status-row"><span className="t-success">{"\u25cf"}</span> T-001 Build landing page <span className="t-badge t-done">done</span></div>
          <div className="t-status-row"><span className="t-active">{"\u25cf"}</span> T-002 Write API docs <span className="t-badge t-progress">active</span></div>
          <div className="t-status-row"><span className="t-dim">{"\u25cb"}</span> T-003 Review &amp; merge <span className="t-badge t-blocked">blocked</span></div>
        </div>
        <div className="terminal-line" style={{marginTop:10}}><span className="t-prompt">$</span> <span className="terminal-cursor"/></div>
      </div>
    </div>
  );
}

function App() {
  return (
    <div className="page">
      <div className="bg-gradient" aria-hidden="true"/>
      <header className="header">
        <div className="shell header-inner">
          <a className="logo" href="#top"><img src={logo} alt="ClawTeam"/><strong>ClawTeam</strong></a>
          <nav className="nav"><a href="#features">Features</a><a href="#workflow">How it works</a><a href="#docs">Docs</a></nav>
          <a className="btn-primary" href="https://github.com/HKUDS/ClawTeam" target="_blank" rel="noreferrer">GitHub</a>
        </div>
      </header>
      <main>
        <section className="hero shell" id="top">
          <div className="hero-content">
            <p className="badge">Agent swarm orchestration</p>
            <h1>Coordinate any coding agent from one CLI</h1>
            <p className="hero-sub">ClawTeam is the coordination layer for Claude Code, Codex, OpenClaw, nanobot, and any terminal-native client that needs to plan, delegate, and ship together.</p>
            <div className="hero-cta">
              <a className="btn-primary" href="https://github.com/HKUDS/ClawTeam#-quick-start" target="_blank" rel="noreferrer">Get started</a>
              <a className="btn-ghost" href="skills/clawteam/references/cli-reference.md">CLI Reference</a>
            </div>
          </div>
          <div className="hero-visual"><TerminalMockup/></div>
        </section>

        <HalfGlobe/>

        <section className="clients shell">
          <span className="clients-label">Works with</span>
          <div className="clients-list">{clients.map(c=><span key={c}>{c}</span>)}</div>
        </section>
        <section className="features shell" id="features">
          <div className="section-header"><p className="section-label">Core capabilities</p><h2>Built for agent teams, not isolated sessions</h2></div>
          <div className="features-grid">{features.map(f=><article className="feature-card" key={f.title}><h3>{f.title}</h3><p>{f.body}</p></article>)}</div>
        </section>
        <section className="workflow shell" id="workflow">
          <div className="section-header"><p className="section-label">How it works</p><h2>Three steps to a running swarm</h2></div>
          <div className="steps">{steps.map(s=><div className="step" key={s.num}><div className="step-info"><span className="step-num">{s.num}</span><h3>{s.title}</h3><p>{s.body}</p></div><pre className="step-code"><code>{s.code}</code></pre></div>)}</div>
        </section>
        <section className="docs shell" id="docs">
          <div className="section-header"><p className="section-label">Documentation</p><h2>Learn more</h2></div>
          <div className="docs-grid">{docs.map(d=><a className="doc-card" key={d.title} href={d.href} target={d.href.startsWith("http")?"_blank":undefined} rel={d.href.startsWith("http")?"noreferrer":undefined}><strong>{d.title}</strong><span>{d.body}</span><span className="doc-arrow">{"\u2192"}</span></a>)}</div>
        </section>
      </main>
      <footer className="footer shell">
        <span>ClawTeam</span>
        <div className="footer-links"><a href="https://github.com/HKUDS/ClawTeam">GitHub</a><a href="skills/clawteam/SKILL.md">Skill</a><a href="skills/clawteam/references/cli-reference.md">CLI Reference</a></div>
      </footer>
    </div>
  );
}

export default App;
