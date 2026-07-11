// KeGhost — Cartoon Pastel Capybara front-end
const $=(s,r=document)=>r.querySelector(s);
const $$=(s,r=document)=>[...r.querySelectorAll(s)];

/* ---------- i18n ---------- */
const I18N={
  id:{
    tagline:"ditemani capy 🦫",
    heroTitle:"Akun X kamu kena shadowban?",
    heroSub:"Tenang. Capy bakal cek buat kamu — pelan-pelan, teliti, dan bakal baik-baik aja. 🍵",
    phUser:"username",
    scanBtn:"Mulai Scan",
    capyTitle:"Capy bilang: Halo!",
    capyMsg:"Cukup ketik username X (tanpa @), Capy urus sisanya. Data diambil langsung dari X — real-time.",
    emptyTitle:"Belum ada yang dicek",
    emptySub:"Ketik username di atas dan Capy langsung meluncur 🌿",
    loadTitle:"Capy lagi ngintip X...",
    loadSub:"Sabar ya, lagi periksa 8 lapisan visibility",
    errTitle:"Yah, Capy bingung",
    tabAll:"Semua",tabBan:"Ban",tabMod:"Mod",tabClean:"Clean",
    deepBtn:"Deep Analysis pakai CapyAi",
    deepSub:"Powered by Anthropic Claude Opus 4.8 · analisis mendalam + 10 solusi",
    exploreTitle:"🌏 Eksplorasi",
    footer:"KeGhost · dibuat dengan tenang, ala kapibara di onsen",
    resync:"↻ Resync",verified:"✓ verified",
    followers:"followers",following:"following",posts:"posts",
    overallSafe:"Aman! Akun kamu terlihat sehat 🌿",
    overallWarn:"Ada sinyal yang perlu diperhatikan ⚠️",
    overallBan:"Terdeteksi kemungkinan pembatasan 🚨",
    deepLoading:"CapyAi lagi menganalisis dalam-dalam...",
    deepSummary:"📋 Ringkasan CapyAi",
    growthTitle:"📈 Growth Insight",
    ratio:"Rasio F/F",engQ:"Kualitas Engagement",
    nonFollow:"Belum follow balik",
    chartVis:"Skor Visibility",chartLayer:"Confidence per Layer",
    solTitle:"💡 10 Solusi dari Capy",
    deepErr:"CapyAi lagi rewel, coba lagi bentar ya 🦫"
  },
  en:{
    tagline:"with capy 🦫",
    heroTitle:"Is your X account shadowbanned?",
    heroSub:"Relax. Capy will check for you — slowly, carefully, and it'll be okay. 🍵",
    phUser:"username",
    scanBtn:"Start Scan",
    capyTitle:"Capy says: Hi!",
    capyMsg:"Just type your X username (no @), Capy handles the rest. Data pulled live from X — real-time.",
    emptyTitle:"Nothing checked yet",
    emptySub:"Type a username above and Capy rolls out 🌿",
    loadTitle:"Capy is peeking at X...",
    loadSub:"Hang on, checking 8 visibility layers",
    errTitle:"Oops, Capy is confused",
    tabAll:"All",tabBan:"Ban",tabMod:"Mod",tabClean:"Clean",
    deepBtn:"Deep Analysis with CapyAi",
    deepSub:"Powered by Anthropic Claude Opus 4.8 · deep analysis + 10 solutions",
    exploreTitle:"🌏 Explore",
    footer:"KeGhost · made calmly, capybara-in-onsen style",
    resync:"↻ Resync",verified:"✓ verified",
    followers:"followers",following:"following",posts:"posts",
    overallSafe:"Safe! Your account looks healthy 🌿",
    overallWarn:"Some signals worth watching ⚠️",
    overallBan:"Possible restrictions detected 🚨",
    deepLoading:"CapyAi is analyzing deeply...",
    deepSummary:"📋 CapyAi Summary",
    growthTitle:"📈 Growth Insight",
    ratio:"F/F Ratio",engQ:"Engagement Quality",
    nonFollow:"Not following back",
    chartVis:"Visibility Score",chartLayer:"Confidence per Layer",
    solTitle:"💡 10 Solutions from Capy",
    deepErr:"CapyAi is fussy, try again in a bit 🦫"
  }
};
let LANG=localStorage.getItem("keghost-lang")||"id";
const t=k=>(I18N[LANG][k]??I18N.id[k]??k);
function applyLang(){
  $$("[data-i18n]").forEach(el=>el.textContent=t(el.dataset.i18n));
  $$("[data-i18n-ph]").forEach(el=>el.placeholder=t(el.dataset.i18nPh));
  $$("#langGroup button").forEach(b=>b.classList.toggle("active",b.dataset.lang===LANG));
  document.documentElement.lang=LANG;
  buildSlides();
  if(LAST) renderResult(LAST);
}
$$("#langGroup button").forEach(b=>b.onclick=()=>{LANG=b.dataset.lang;localStorage.setItem("keghost-lang",LANG);applyLang();});

/* ---------- theme ---------- */
let THEME=localStorage.getItem("keghost-theme")||"light";
function applyTheme(){
  document.documentElement.dataset.theme=THEME;
  $("#themeBtn").textContent=THEME==="light"?"🌙":"☀️";
}
$("#themeBtn").onclick=()=>{THEME=THEME==="light"?"dark":"light";localStorage.setItem("keghost-theme",THEME);applyTheme();};

/* ---------- layer meta ---------- */
const LAYER_IC={PROFILE:"👤",SEARCH:"🔍",SUGGEST:"💬",QRT:"🔁",SPAM:"🧹",RANK:"⭐",POST:"📝",INDEX:"📇"};
const LAYER_ICON=n=>LAYER_IC[(n||"").toUpperCase()]||"🌿";

/* ---------- scan ---------- */
let LAST=null, DEEP_CACHE={};
function show(id){["stateEmpty","stateLoading","stateError","result"].forEach(s=>$("#"+s).classList.toggle("hidden",s!==id));}

async function scan(username){
  username=(username||"").trim().replace(/^@/,"");
  if(!username) return;
  $("#scanBtn").disabled=true;
  show("stateLoading");
  try{
    const r=await fetch("/api/check",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username})});
    const data=await r.json();
    if(data.error && (!data.layers||!data.layers.length)){throw new Error(data.error);}
    LAST=data;
    renderResult(data);
    show("result");
    loadRecent();
  }catch(e){
    $("#errMsg").textContent=(""+(e.message||e))+" 🍃";
    show("stateError");
  }finally{$("#scanBtn").disabled=false;}
}

function fmt(n){n=+n||0;if(n>=1e6)return (n/1e6).toFixed(1).replace(".0","")+"M";if(n>=1e3)return (n/1e3).toFixed(1).replace(".0","")+"K";return ""+n;}

function renderResult(data){
  const p=data.profile||{};
  const ava=p.avatar||"/assets/logo.png";
  $("#profileCard").innerHTML=`
    <img class="ava" src="${ava}" onerror="this.src='/assets/logo.png'" alt="" />
    <div class="profile-meta">
      <div class="name">${escapeHtml(p.name||data.username||"—")} ${p.verified?`<span class="verified">${t("verified")}</span>`:""}</div>
      <div class="handle">@${escapeHtml(p.username||data.username||"")}</div>
    </div>
    <div class="stats">
      <div class="stat"><b>${fmt(p.followers)}</b><span>${t("followers")}</span></div>
      <div class="stat"><b>${fmt(p.following)}</b><span>${t("following")}</span></div>
      <div class="stat"><b>${fmt(p.tweets)}</b><span>${t("posts")}</span></div>
    </div>
    <button class="resync" onclick="scan('${escapeAttr(p.username||data.username||"")}')">${t("resync")}</button>`;

  const ov=$("#overall");
  const o=data.overall||"warning";
  ov.className="overall "+(o==="banned"?"banned":o==="warning"?"warning":"safe");
  const em=o==="banned"?"🚨":o==="warning"?"😟":"😌";
  const msg=o==="banned"?t("overallBan"):o==="warning"?t("overallWarn"):t("overallSafe");
  ov.innerHTML=`<span class="em">${em}</span><div><b>${msg}</b></div>`;

  window.__layers=data.layers||data.tests||[];
  renderGrid("all");
  // reset deep panel
  $("#deepPanel").classList.remove("show");
  $("#deepPanel").innerHTML="";
  $("#deepBtn").disabled=false;
}

function renderGrid(filter){
  const layers=window.__layers||[];
  const g=$("#grid");g.innerHTML="";
  layers.filter(l=>filter==="all"||l.status===filter).forEach((l,i)=>{
    const st=l.status||"safe";
    const d=document.createElement("div");
    d.className="cell "+st;
    d.style.animationDelay=(i*60)+"ms";
    d.innerHTML=`
      <div class="top"><span class="ic">${LAYER_ICON(l.name)}</span><span class="badge">${st}</span></div>
      <div class="lname">${escapeHtml(l.name||"")}</div>
      <div class="ldesc">${escapeHtml(l.desc||"")}</div>
      <div class="conf"><i></i></div>
      <div class="cval">${l.confidence||0}%</div>`;
    g.appendChild(d);
    requestAnimationFrame(()=>{setTimeout(()=>{d.querySelector(".conf i").style.width=(l.confidence||0)+"%";},i*60+120);});
  });
}
$$("#tabs button").forEach(b=>b.onclick=()=>{
  $$("#tabs button").forEach(x=>x.classList.remove("active"));
  b.classList.add("active");renderGrid(b.dataset.f);
});

/* ---------- deep analysis ---------- */
$("#deepBtn").onclick=async()=>{
  if(!LAST) return;
  const uname=(LAST.profile&&LAST.profile.username)||LAST.username;
  const panel=$("#deepPanel");
  panel.classList.add("show");
  panel.innerHTML=`<div class="state loading"><img src="/assets/capybara.png" alt=""/><h3>${t("deepLoading")}</h3><div class="dots"><span></span><span></span><span></span></div></div>`;
  $("#deepBtn").disabled=true;
  try{
    let data=DEEP_CACHE[uname];
    if(!data){
      const r=await fetch("/api/deep-analysis",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:uname})});
      data=await r.json();
      if(data.error) throw new Error(data.error);
      DEEP_CACHE[uname]=data;
    }
    renderDeep(data);
  }catch(e){
    panel.innerHTML=`<div class="state error"><img src="/assets/capybara-ghost.png" alt=""/><h3>${t("errTitle")}</h3><p>${escapeHtml(t("deepErr"))}<br><small style="opacity:.6">${escapeHtml(""+(e.message||e))}</small></p></div>`;
  }finally{$("#deepBtn").disabled=false;}
};

function renderDeep(data){
  const a=data.analysis||{};
  const gi=a.growth_insight||{};
  const eb=a.engagement_breakdown||{};
  const panel=$("#deepPanel");
  const verdictColor=(v)=>{v=(v||"").toLowerCase();return v.includes("sehat")||v.includes("health")?"var(--sage)":v.includes("masalah")||v.includes("bad")?"#e89b9b":"var(--butter)";};
  panel.innerHTML=`
    <div class="card">
      <div class="section-title" style="margin-top:0">${t("deepSummary")}</div>
      <p style="font-weight:600;line-height:1.6;color:var(--text)">${escapeHtml(a.summary||"")}</p>
    </div>
    <div class="section-title">${t("growthTitle")}</div>
    <div class="insight-grid">
      <div class="insight">
        <div class="lbl">${t("ratio")}</div>
        <div class="big">${gi.follower_following_ratio??"—"}</div>
        <span class="verdict-badge" style="background:${verdictColor(gi.verdict)};color:#4a3d30">${escapeHtml(gi.verdict||"")}</span>
        <div class="note">${escapeHtml(gi.note||"")}</div>
      </div>
      <div class="insight">
        <div class="lbl">${t("engQ")}</div>
        <div class="big">${eb.score??"—"}<span style="font-size:14px;color:var(--muted)">/100</span></div>
        <div class="note">${escapeHtml(eb.note||"")}</div>
      </div>
    </div>
    <div class="insight" style="margin-top:12px">
      <div class="lbl">${t("nonFollow")}</div>
      <div class="note" style="margin-top:8px;font-size:13px">${escapeHtml(a.non_followers_estimate||"")}</div>
    </div>
    <div class="charts-grid">
      <div class="chart-box"><h4>${t("chartVis")}</h4><canvas id="chartVis" height="200"></canvas></div>
      <div class="chart-box"><h4>${t("chartLayer")}</h4><canvas id="chartLayer" height="200"></canvas></div>
    </div>
    <div class="section-title">${t("solTitle")}</div>
    <div class="card"><div class="solutions">
      ${(a.solutions||[]).map(s=>`<div class="sol"><div class="num"></div><p>${escapeHtml(s)}</p></div>`).join("")}
    </div></div>`;
  drawCharts(a.charts||{});
}

let _charts=[];
function drawCharts(charts){
  _charts.forEach(c=>{try{c.destroy();}catch(e){}});_charts=[];
  const css=getComputedStyle(document.documentElement);
  const cocoa=css.getPropertyValue("--cocoa").trim()||"#C8A982";
  const sage=css.getPropertyValue("--sage").trim()||"#A8C4A0";
  const lav=css.getPropertyValue("--lav").trim()||"#D4C5E2";
  const grid=css.getPropertyValue("--border").trim()||"#E8D5C4";
  const txt=css.getPropertyValue("--muted").trim()||"#9A8571";
  Chart.defaults.font.family="Nunito";
  Chart.defaults.color=txt;
  const vis=charts.visibility||[];
  if(vis.length){
    _charts.push(new Chart($("#chartVis"),{type:"radar",data:{labels:vis.map(x=>x.label),
      datasets:[{data:vis.map(x=>x.value),backgroundColor:cocoa+"44",borderColor:cocoa,borderWidth:2,pointBackgroundColor:cocoa}]},
      options:{plugins:{legend:{display:false}},scales:{r:{min:0,max:100,grid:{color:grid},angleLines:{color:grid},pointLabels:{color:txt,font:{weight:"700"}},ticks:{display:false}}}}}));
  }
  const lc=charts.layer_confidence||[];
  if(lc.length){
    _charts.push(new Chart($("#chartLayer"),{type:"bar",data:{labels:lc.map(x=>x.label),
      datasets:[{data:lc.map(x=>x.value),backgroundColor:lc.map((_,i)=>[cocoa,sage,lav][i%3]),borderRadius:8}]},
      options:{plugins:{legend:{display:false}},indexAxis:"y",scales:{x:{min:0,max:100,grid:{color:grid}},y:{grid:{display:false}}}}}));
  }
}

/* ---------- recent chips ---------- */
async function loadRecent(){
  try{
    const r=await fetch("/api/recent");const list=await r.json();
    const box=$("#recent");box.innerHTML="";
    (list||[]).forEach((it,i)=>{
      const c=document.createElement("div");
      c.className="chip"+(i===0?" live":"");
      c.innerHTML=`${i===0?'<span class="live-dot"></span>':''}<img src="${it.avatar_url||'/assets/logo.png'}" onerror="this.src='/assets/logo.png'"/><span>@${escapeHtml(it.username)}</span>`;
      c.onclick=()=>scan(it.username);
      box.appendChild(c);
    });
  }catch(e){}
}

/* ---------- carousel ---------- */
const SLIDES={
  id:[
    {tag:"Tips",title:"Posting di jam ramai",desc:"Sebar postingan saat followers-mu paling aktif biar reach maksimal."},
    {tag:"Fakta",title:"Shadowban itu senyap",desc:"X jarang kasih notifikasi. Makanya cek berkala itu penting."},
    {tag:"Trik",title:"Kurangi link mentah",desc:"Terlalu banyak link eksternal bisa nurunin distribusi. Selingi dengan konten asli."},
    {tag:"Sehat",title:"Interaksi tulus menang",desc:"Balas & QRT organik ngasih sinyal positif ke algoritma."},
    {tag:"Hindari",title:"Jangan spam hashtag",desc:"Hashtag berlebihan bikin post-mu dianggap spam."},
    {tag:"Capy","title":"Sabar itu kunci","desc":"Recovery shadowban butuh waktu. Konsisten, jangan panik. 🦫"}
  ],
  en:[
    {tag:"Tip",title:"Post at peak hours",desc:"Publish when your followers are most active for max reach."},
    {tag:"Fact",title:"Shadowbans are silent",desc:"X rarely notifies you. That's why periodic checks matter."},
    {tag:"Trick",title:"Fewer raw links",desc:"Too many external links can lower distribution. Mix in native content."},
    {tag:"Healthy",title:"Genuine interaction wins",desc:"Organic replies & QRTs signal positively to the algorithm."},
    {tag:"Avoid",title:"Don't spam hashtags",desc:"Excessive hashtags make posts look spammy."},
    {tag:"Capy",title:"Patience is key",desc:"Shadowban recovery takes time. Stay consistent, don't panic. 🦫"}
  ]
};
let slideIdx=0;
function buildSlides(){
  const data=SLIDES[LANG]||SLIDES.id;
  const track=$("#slides");track.innerHTML="";
  data.forEach(s=>{
    const d=document.createElement("div");d.className="slide";
    d.innerHTML=`<div class="slide-inner"><span class="stag">${escapeHtml(s.tag)}</span><h4>${escapeHtml(s.title)}</h4><p>${escapeHtml(s.desc)}</p></div>`;
    track.appendChild(d);
  });
  const dn=$("#dotsNav");dn.innerHTML="";
  data.forEach((_,i)=>{const dot=document.createElement("i");if(i===0)dot.className="active";dot.onclick=()=>goSlide(i);dn.appendChild(dot);});
  slideIdx=0;goSlide(0);
}
function goSlide(i){
  const data=SLIDES[LANG]||SLIDES.id;
  slideIdx=(i+data.length)%data.length;
  $("#slides").style.transform=`translateX(-${slideIdx*100}%)`;
  $$("#dotsNav i").forEach((d,k)=>d.classList.toggle("active",k===slideIdx));
}
$("#prevSlide").onclick=()=>goSlide(slideIdx-1);
$("#nextSlide").onclick=()=>goSlide(slideIdx+1);
setInterval(()=>goSlide(slideIdx+1),6000);

/* ---------- misc ---------- */
$("#capyX").onclick=()=>$("#capyBanner").classList.add("hidden");
$("#scanBtn").onclick=()=>scan($("#username").value);
$("#username").addEventListener("keydown",e=>{if(e.key==="Enter")scan(e.target.value);});

function escapeHtml(s){return (""+(s??"")).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function escapeAttr(s){return escapeHtml(s).replace(/'/g,"&#39;");}

/* boot */
applyTheme();applyLang();buildSlides();loadRecent();
