const $ = s => document.querySelector(s);
let ws, latest = {}, cpuHistory = new Array(48).fill(0), proactive = true;

/* ---------- reactor ---------- */
const canvas = $("#core"), ctx = canvas.getContext("2d");
let W, H, nodes = [], t = 0, intensity = 0.25;

function sizeCanvas() {
  const r = canvas.getBoundingClientRect(), d = devicePixelRatio || 1;
  canvas.width = r.width * d; canvas.height = r.height * d;
  ctx.setTransform(d, 0, 0, d, 0, 0); W = r.width; H = r.height;
  nodes = Array.from({ length: 150 }, () => {
    const a = Math.random() * Math.PI * 2, rad = 0.20 + Math.random() * 0.74;
    return { a, r: rad, sp: (0.0006 + Math.random() * 0.0018) * (Math.random() < .5 ? -1 : 1),
             p: Math.random() * Math.PI * 2, s: 0.7 + Math.random() * 1.5 };
  });
}
addEventListener("resize", sizeCanvas);

function ring(cx, cy, rad, dash, width, alpha, rot) {
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(rot);
  ctx.beginPath(); ctx.arc(0, 0, rad, 0, Math.PI * 2);
  ctx.setLineDash(dash); ctx.lineWidth = width;
  ctx.strokeStyle = `rgba(90,220,255,${alpha})`;
  ctx.shadowBlur = 12; ctx.shadowColor = "rgba(55,224,255,.8)";
  ctx.stroke(); ctx.restore();
}

function draw() {
  t += 1;
  const cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 6;
  ctx.clearRect(0, 0, W, H);
  intensity += (0.2 + (latest.cpu?.percent || 0) / 130 - intensity) * 0.05;

  const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R);
  g.addColorStop(0, `rgba(60,200,255,${0.22 + intensity * .3})`);
  g.addColorStop(0.45, "rgba(10,80,150,0.10)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.fill();

  ring(cx, cy, R * 0.97, [2, 16], 1, .35, t * 0.0016);
  ring(cx, cy, R * 0.86, [40, 18], 1.4, .5, -t * 0.0022);
  ring(cx, cy, R * 0.70, [6, 8], 1, .32, t * 0.0035);
  ring(cx, cy, R * 0.50, [70, 30], 2, .55 + intensity * .3, -t * 0.0015);
  ring(cx, cy, R * 0.30, [3, 7], 1.2, .45, t * 0.005);

  // particle web
  const pts = nodes.map(n => {
    n.a += n.sp; const pulse = 0.5 + 0.5 * Math.sin(t * 0.03 + n.p);
    const rr = n.r * R * (0.985 + 0.02 * Math.sin(t * 0.01 + n.p));
    return { x: cx + Math.cos(n.a) * rr, y: cy + Math.sin(n.a) * rr, b: pulse, s: n.s };
  });
  ctx.lineWidth = 0.6;
  for (let i = 0; i < pts.length; i++) {
    for (let j = i + 1; j < pts.length; j++) {
      const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y, d2 = dx * dx + dy * dy;
      if (d2 < 1900) {
        ctx.strokeStyle = `rgba(70,200,255,${(1 - d2 / 1900) * 0.22 * (0.6 + intensity)})`;
        ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y); ctx.lineTo(pts[j].x, pts[j].y); ctx.stroke();
      }
    }
  }
  pts.forEach(p => {
    ctx.fillStyle = `rgba(150,240,255,${0.35 + p.b * 0.6})`;
    ctx.beginPath(); ctx.arc(p.x, p.y, p.s, 0, 7); ctx.fill();
  });

  // core
  const cr = R * 0.19 + Math.sin(t * 0.05) * 1.6;
  const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr * 2.2);
  cg.addColorStop(0, "rgba(220,250,255,.95)"); cg.addColorStop(.35, "rgba(60,200,255,.55)");
  cg.addColorStop(1, "rgba(20,90,160,0)");
  ctx.fillStyle = cg; ctx.beginPath(); ctx.arc(cx, cy, cr * 2.2, 0, 7); ctx.fill();
  ctx.strokeStyle = "rgba(190,245,255,.9)"; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(cx, cy, cr, 0, 7); ctx.stroke();

  // crosshair ticks
  ctx.strokeStyle = "rgba(55,224,255,.35)";
  [[-1,0],[1,0],[0,-1],[0,1]].forEach(([dx,dy])=>{
    ctx.beginPath(); ctx.moveTo(cx+dx*R*1.0, cy+dy*R*1.0);
    ctx.lineTo(cx+dx*R*0.88, cy+dy*R*0.88); ctx.stroke();
  });
  requestAnimationFrame(draw);
}

/* ---------- cpu bar strip ---------- */
const bars = $("#cpuBars"), bctx = bars.getContext("2d");
function drawBars() {
  const w = bars.clientWidth, h = bars.height; bars.width = w;
  bctx.clearRect(0, 0, w, h);
  const n = cpuHistory.length, bw = w / n;
  cpuHistory.forEach((v, i) => {
    const bh = Math.max(2, (v / 100) * h);
    const grd = bctx.createLinearGradient(0, h - bh, 0, h);
    grd.addColorStop(0, v > 85 ? "#ff7b86" : "#5fe6ff"); grd.addColorStop(1, "rgba(20,90,150,.35)");
    bctx.fillStyle = grd; bctx.fillRect(i * bw + 1, h - bh, bw - 2, bh);
  });
}

/* ---------- websocket ---------- */
function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => { $("#sysStatus").textContent = "● OPTIMAL"; $("#sysStatus").style.color = "#37e0ff"; };
  ws.onclose = () => {
    $("#sysStatus").textContent = "● OFFLINE"; $("#sysStatus").style.color = "#ff5f6d";
    setTimeout(connect, 2500);
  };
  ws.onmessage = e => handle(JSON.parse(e.data));
}

function handle(m) {
  switch (m.type) {
    case "hello":
      $("#aiMode").textContent = m.ai_mode === "offline" ? "LOCAL PARSER" : m.ai_mode.toUpperCase();
      addMsg("ultron", `Online. ${m.capabilities} capabilities available` +
        (m.workflows.length ? `, workflows ready: ${m.workflows.join(", ")}.` : "."));
      break;
    case "metrics": updateMetrics(m.data); break;
    case "message": addMsg(m.role, m.text); break;
    case "thinking": toggleThinking(m.state); break;
    case "log": addLog(m.text, m.level); break;
    case "notification": toast(m.text, m.level); addLog(m.text, m.level); break;
    case "task_update":
      if (m.status === "running") addLog(`▸ ${m.action}`, "info");
      else if (m.detail) addLog(`  ${m.status === "ok" ? "✓" : "✕"} ${m.detail}`,
                                m.status === "ok" ? "info" : "warn");
      break;
    case "confirm_request": showModal(m); break;
  }
}

function updateMetrics(d) {
  latest = d;
  $("#cpuVal").textContent = d.cpu.percent.toFixed(0);
  $("#cpuTemp").textContent = d.cpu.temperature_c ? d.cpu.temperature_c + "°C" : "n/a";
  $("#cpuCores").textContent = `${d.cpu.cores_physical || "?"}C / ${d.cpu.cores_logical}T`;
  cpuHistory = (d.cpu_series && d.cpu_series.length ? d.cpu_series : cpuHistory).slice(-48);
  while (cpuHistory.length < 48) cpuHistory.unshift(0);
  drawBars();

  setBar("ram", d.ram.percent, `${d.ram.used_gb} / ${d.ram.total_gb} GB`);
  const disk = d.storage.disks[0];
  if (disk) setBar("disk", disk.percent, `${disk.free_gb} GB free`);
  if (d.gpu.available) setBar("gpu", d.gpu.usage_percent ?? 0, `${(d.gpu.usage_percent ?? 0).toFixed(0)}%`);
  else { $("#gpuTxt").textContent = "unavailable"; $("#gpuBar").style.width = "0%"; }
  setBar("proc", Math.min(100, d.process_count / 4), `${d.process_count}`);

  $("#netDown").textContent = d.network.download_mb_s.toFixed(2);
  $("#netUp").textContent = d.network.upload_mb_s.toFixed(2);
  $("#netRing").classList.toggle("off", !d.network.connected);
  $("#netState").textContent = d.network.connected ? "LINK" : "NO NET";

  const w = d.watchers || [];
  $("#watchers").innerHTML = w.length
    ? w.map(x => `<div class="w"><span>${x.label}</span><b>${x.active ? "ACTIVE" : "fired"}</b></div>`).join("")
    : '<span class="dim">No active monitors.</span>';
  proactive = d.proactive; $("#proBtn").classList.toggle("on", proactive);
  $("#monTime").textContent = Math.round((d.cpu_series?.length || 0) * 1.5 / 60) + "m";
}
function setBar(id, pct, text) {
  $(`#${id}Bar`).style.width = Math.min(100, pct) + "%";
  $(`#${id}Txt`).textContent = text;
}

/* ---------- conversation ---------- */
function addMsg(role, text) {
  const el = document.createElement("div");
  el.className = "msg " + (role === "user" ? "user" : "ultron");
  el.textContent = text;
  $("#convo").appendChild(el);
  $("#convo").scrollTop = 1e6;
  while ($("#convo").children.length > 40) $("#convo").firstChild.remove();
}
function toggleThinking(on) {
  const ex = $("#thinking");
  if (on && !ex) {
    const e = document.createElement("div");
    e.id = "thinking"; e.className = "msg ultron think"; e.textContent = "processing…";
    $("#convo").appendChild(e); $("#convo").scrollTop = 1e6;
  } else if (!on && ex) ex.remove();
}
function addLog(text, level = "info") {
  const time = new Date().toLocaleTimeString("en-GB");
  const el = document.createElement("div");
  el.className = level; el.innerHTML = `<b>[${time}]</b> ${text}`;
  $("#log").appendChild(el); $("#log").scrollTop = 1e6;
  while ($("#log").children.length > 200) $("#log").firstChild.remove();
}
function toast(text, level) {
  const el = document.createElement("div");
  el.className = "toast " + (level || "info"); el.textContent = text;
  $("#toasts").appendChild(el);
  $("#alertBadge").style.display = "block";
  setTimeout(() => el.remove(), 11000);
}

/* ---------- confirmation modal ---------- */
let pending = null;
function showModal(m) {
  pending = m.id;
  const wrap = $("#modal");
  wrap.classList.toggle("level3", m.level === 3);
  $("#mLevel").textContent = `LEVEL ${m.level} — ${m.level === 3 ? "HIGH RISK" : "CONFIRMATION"}`;
  $("#mTitle").textContent = m.summary || m.action;
  $("#mBody").textContent = `${m.reason} Action: ${m.action}` +
    (Object.keys(m.params || {}).length ? ` with ${JSON.stringify(m.params)}` : "") + ".";
  $("#mAlways").style.display = m.level === 3 ? "none" : "";
  wrap.classList.add("open");
}
function answer(approved, always = false) {
  if (pending) ws.send(JSON.stringify({ type: "confirm", id: pending, approved, always }));
  pending = null; $("#modal").classList.remove("open");
}
$("#mOk").onclick = () => answer(true);
$("#mAlways").onclick = () => answer(true, true);
$("#mDeny").onclick = () => answer(false);

/* ---------- input & quick access ---------- */
$("#cmdForm").onsubmit = e => {
  e.preventDefault();
  const v = $("#cmdInput").value.trim(); if (!v) return;
  ws.send(JSON.stringify({ type: "command", text: v })); $("#cmdInput").value = "";
};
document.querySelectorAll("[data-cmd]").forEach(b => b.onclick = () => {
  ws.send(JSON.stringify({ type: "command", text: b.dataset.cmd }));
});
$("#micBtn").onclick = () => addMsg("ultron",
  "No voice module is installed yet. The voice layer is a drop-in module — wire it to the same command socket when you choose one.");

/* ---------- drawer ---------- */
async function openDrawer(kind) {
  const body = $("#drawerBody");
  if (kind === "memory") {
    $("#drawerTitle").textContent = "MEMORY";
    const m = await (await fetch("/api/memory")).json();
    body.innerHTML =
      `<div class="item"><small>FREQUENT APPS</small>${Object.keys(m.apps).join(", ") || "—"}</div>
       <div class="item"><small>FREQUENT FOLDERS</small>${Object.keys(m.folders).join("<br>") || "—"}</div>` +
      m.facts.map(f => `<div class="item"><small>${new Date(f.ts * 1000).toLocaleString()}</small>${f.text}
        <button onclick="forget('${f.id}')">FORGET</button></div>`).join("");
  } else {
    $("#drawerTitle").textContent = "RECENT ACTIVITY";
    const h = await (await fetch("/api/history")).json();
    body.innerHTML = h.reverse().map(x =>
      `<div class="item"><small>${new Date(x.ts * 1000).toLocaleTimeString()} · ${x.actions.join(", ") || "no action"}</small>
       <b>${x.user}</b><br>${x.reply}</div>`).join("") || '<span class="dim">Nothing yet.</span>';
  }
  $("#drawer").classList.add("open");
}
window.forget = async id => { await fetch("/api/memory/" + id, { method: "DELETE" }); openDrawer("memory"); };
$("#recentBtn").onclick = () => openDrawer("recent");
$("#btnAlerts").onclick = () => { $("#alertBadge").style.display = "none"; openDrawer("recent"); };
$("#btnSettings").onclick = () => openDrawer("memory");
$("#drawerClose").onclick = () => $("#drawer").classList.remove("open");

setInterval(() => $("#clock").textContent = new Date().toLocaleTimeString("en-GB"), 1000);
sizeCanvas(); draw(); drawBars(); connect();
