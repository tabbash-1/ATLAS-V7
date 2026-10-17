(() => {
  "use strict";
  const LINKS = [
    ["Production Status","production-status.html"],
    ["Trade Monitor","trade-monitor.html"],
    ["Trade Outcomes","trade-outcomes.html"],
    ["Evidence Center","evidence-control-center.html"],
    ["Paper Validation","paper-validation.html"],
    ["Validation","validation.html"],
    ["Feedback Lab","feedback-lab.html"]
  ];
  const read = (id, fallback="—") => {
    const el=document.getElementById(id);
    const v=el && el.textContent ? el.textContent.trim() : "";
    return v || fallback;
  };
  const esc = v => String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const tile=(label,value,sub="")=>`<div class="atlas-unified-tile"><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(sub)}</small></div>`;
  function removeLiteralScriptSeparator(){
    const script=document.currentScript || Array.from(document.scripts).find(s=>String(s.src||"").includes("atlas-unified-command-center.js"));
    const previous=script && script.previousSibling;
    if(previous && previous.nodeType===Node.TEXT_NODE && /^\\n\s*$/.test(previous.nodeValue||"")) previous.remove();
  }
  function ensure(){
    if(document.getElementById("atlasUnifiedCommandCenter")) return;
    const main=document.querySelector("main.main");
    const nav=document.getElementById("atlasWorkspaceNav");
    if(!main) return;
    const section=document.createElement("section");
    section.id="atlasUnifiedCommandCenter";
    section.className="card metrics-card atlas-unified-command";
    section.innerHTML=`
      <div class="card-head">
        <div><strong>ATLAS UNIFIED COMMAND CENTER</strong><div class="muted small">Production → plan → portfolio → outcomes → learning → evidence. One read-only operational view.</div></div>
        <span id="atlasUnifiedHealth" class="pill neutral">SYNCING</span>
      </div>
      <div id="atlasUnifiedPrimary" class="atlas-unified-grid"></div>
      <div class="panel-title" style="margin-top:16px">EVIDENCE & LEARNING</div>
      <div id="atlasUnifiedEvidence" class="atlas-unified-grid"></div>
      <div class="panel-title" style="margin-top:16px">OPERATIONS</div>
      <div id="atlasUnifiedLinks" class="atlas-unified-links"></div>
      <div id="atlasUnifiedTruth" class="comparison-box muted small">This surface mirrors existing ATLAS authorities. It does not promote research evidence or mutate Production.</div>`;
    if(nav) main.insertBefore(section,nav); else main.prepend(section);
    const style=document.createElement("style");
    style.textContent=`
      .atlas-unified-command{margin:16px 0}
      .atlas-unified-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
      .atlas-unified-tile{padding:12px;border:1px solid var(--border,#2a3344);border-radius:12px;background:var(--panel,#111827)}
      .atlas-unified-tile span,.atlas-unified-tile small{display:block;font-size:11px;opacity:.72}
      .atlas-unified-tile b{display:block;font-size:16px;margin:5px 0;word-break:break-word}
      .atlas-unified-links{display:flex;gap:8px;flex-wrap:wrap}
      .atlas-unified-links a{padding:8px 11px;border:1px solid var(--border,#2a3344);border-radius:9px;text-decoration:none;color:inherit}
    `;
    document.head.appendChild(style);
    document.getElementById("atlasUnifiedLinks").innerHTML=LINKS.map(([n,h])=>`<a href="${h}">${n}</a>`).join("");
  }
  function sync(){
    ensure();
    const p=document.getElementById("atlasUnifiedPrimary"), e=document.getElementById("atlasUnifiedEvidence");
    if(!p||!e) return;
    const decision=read("cmdMasterValue",read("signalState","WAITING"));
    p.innerHTML=[
      tile("PRODUCTION",decision,read("cmdMasterSub","Canonical authority")),
      tile("PLAN",read("cmdPlanValue"),read("cmdPlanSub","Entry · SL · TP · R:R")),
      tile("REGIME",read("cmdRegimeValue"),"HTF structure"),
      tile("PORTFOLIO RISK",read("cmdRiskValue",read("portfolioRiskBadge")),"Correlation-aware"),
      tile("ENTRY",read("entry"),"Current geometry"),
      tile("STOP",read("stop"),"Invalidation"),
      tile("TARGET",read("target"),"Take profit"),
      tile("R:R",read("rr"),"Risk / reward")
    ].join("");
    e.innerHTML=[
      tile("OUTCOMES",read("outcomeCalibrationBadge",read("trialBadge","NO DATA")),"Forward evidence"),
      tile("PAPER PORTFOLIO",read("paperPortfolioBadge",read("portfolioRiskBadge","WAITING")),"$10k research ledger"),
      tile("LEARNING",read("learningBadge","COLLECTING"),"Post-trade attribution"),
      tile("VALIDATION",read("validationBadge","WAITING"),"OOS / promotion evidence"),
      tile("DRIFT",read("cmdDriftValue","CHECKING"),"Edge health"),
      tile("CLOUD",read("cmdCloudValue","CHECKING"),"24/7 research"),
      tile("ALERTS",read("confirmedAlertBadge","ARMING"),"Production only"),
      tile("MASTER",read("masterBadge","WAITING"),"Conviction context")
    ].join("");
    const health=document.getElementById("atlasUnifiedHealth");
    if(health){health.textContent="LIVE VIEW"; health.className="pill live";}
  }
  removeLiteralScriptSeparator();
  window.addEventListener("DOMContentLoaded",()=>{ensure();sync();setInterval(sync,2000);});
})();