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
    sumClean:"Aman",sumMod:"Perhatikan",sumBan:"Terbatas",
    histTitle:"📜 Riwayat Scan",histSub:"Semua scan dari pengunjung — klik buat lihat hasilnya.",
    histEmpty:"Belum ada riwayat. Jadilah yang pertama scan! 🦫",
    chatTitle:"CapyAi 🦫",chatStatus:"Tanya apa aja soal akun X",
    chatPh:"Tulis pesan buat Capy...",chatTargetPh:"target username",
    chatGreet:"Hai! 🦫 Aku CapyAi. Tulis username X yang mau kamu tanyain di atas, terus pilih topik atau ketik pertanyaanmu.",
    chatNeedUser:"Isi target username dulu ya di atas 🌿",
    chatThinking:"Capy lagi mikir...",
    tpl_profile:"Saran profilku",tpl_niche:"Saran niche",tpl_recover:"Cara recovery",tpl_growth:"Strategi growth",tpl_content:"Ide konten",
    deepBtn:"Deep Analysis pakai CapyAi",
    deepSub:"Powered by CapyAi Engine · analisis mendalam + 10 solusi",
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
    deepErr:"CapyAi lagi rewel, coba lagi bentar ya 🦫",
    chatAuth:"Capy lagi butuh auth ulang. Pantau aja ya 🦫",
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
    sumClean:"Safe",sumMod:"Watch",sumBan:"Limited",
    histTitle:"📜 Scan History",histSub:"All scans from visitors — tap to view results.",
    histEmpty:"No history yet. Be the first to scan! 🦫",
    chatTitle:"CapyAi 🦫",chatStatus:"Ask anything about an X account",
    chatPh:"Type a message for Capy...",chatTargetPh:"target username",
    chatGreet:"Hi! 🦫 I'm CapyAi. Type the X username you want to ask about above, then pick a topic or type your question.",
    chatNeedUser:"Fill in the target username above first 🌿",
    chatThinking:"Capy is thinking...",
    tpl_profile:"Profile tips",tpl_niche:"Niche advice",tpl_recover:"How to recover",tpl_growth:"Growth strategy",tpl_content:"Content ideas",
    deepBtn:"Deep Analysis with CapyAi",
    deepSub:"Powered by CapyAi Engine · deep analysis + 10 solutions",
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
    deepErr:"CapyAi is fussy, try again in a bit 🦫",
    chatAuth:"Capy needs re-auth. Hang tight 🦫",
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
  renderGrid();
  renderHealthScore(data.health_score||0);
  renderFeatureMenu(data.username||(data.profile&&data.profile.username)||"", data.analytics||{});
  renderRecovery(data.recovery||[]);
  loadTimeline(data.username||(data.profile&&data.profile.username)||"");
  renderNonFollowersButton(data.username||(data.profile&&data.profile.username)||"");
  // reset deep panel
  $("#deepPanel").classList.remove("show");
  $("#deepPanel").innerHTML="";
  $("#deepBtn").disabled=false;
}

function renderGrid(){
  const layers=window.__layers||[];
  // summary counts — always visible so section never looks empty
  const cnt={safe:0,warning:0,banned:0};
  layers.forEach(l=>{const s=l.status||"safe";cnt[s]=(cnt[s]||0)+1;});
  const sum=$("#layerSummary");
  if(sum){
    sum.innerHTML=`
      <div class="ls-pill safe"><span class="ls-num">${cnt.safe}</span><span class="ls-lbl">${t("sumClean")}</span></div>
      <div class="ls-pill warning"><span class="ls-num">${cnt.warning}</span><span class="ls-lbl">${t("sumMod")}</span></div>
      <div class="ls-pill banned"><span class="ls-num">${cnt.banned}</span><span class="ls-lbl">${t("sumBan")}</span></div>`;
  }
  const g=$("#grid");g.innerHTML="";
  layers.forEach((l,i)=>{
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
    requestAnimationFrame(()=>{setTimeout(()=>{const bar=d.querySelector(".conf i");if(bar)bar.style.width=(l.confidence||0)+"%";},i*60+120);});
  });
}

/* ---------- recovery checklist ---------- */
function renderRecovery(recovery){
  const el=$("#recoverySection");
  if(!el) return;
  if(!recovery||!recovery.length){
    el.innerHTML=`<div class="recovery-empty">✅ Semua layer aman — tidak ada action yang perlu diambil. Tetap jaga kualitas konten ya 🌿</div>`;
    return;
  }
  let html=`<div class="recovery-wrap"><div class="recovery-title">🩹 Recovery Checklist</div>`;
  recovery.forEach(r=>{
    const steps=r.steps.map(s=>`<li>${escapeHtml(s)}</li>`).join("");
    html+=`<div class="recovery-card ${r.priority}">
      <div class="recovery-head">
        <span class="recovery-badge ${r.priority}">${r.priority}</span>
        <h4>${escapeHtml(r.title)}</h4>
      </div>
      <ul class="recovery-steps">${steps}</ul>
    </div>`;
  });
  html+=`</div>`;
  el.innerHTML=html;
}

/* ---------- scan history timeline ---------- */
async function loadTimeline(username){
  const el=$("#timelineSection");
  if(!el||!username) return;
  try{
    const r=await fetch(`/api/scan-history/${encodeURIComponent(username)}`);
    const data=await r.json();
    if(!data.scans||!data.scans.length){
      el.innerHTML=`<div class="timeline-wrap"><div class="timeline-title">📊 Riwayat Scan</div><div class="timeline-empty">Belum ada riwayat scan sebelumnya. Scan ulang nanti untuk lihat trend perubahan.</div></div>`;
      return;
    }
    const trendIcon=data.trend==="improving"?"📈":data.trend==="degrading"?"📉":"➡️";
    const trendLabel=data.trend==="improving"?"Membaik":data.trend==="degrading"?"Memburuk":"Stabil";
    let dots="";
    data.scans.forEach((s,i)=>{
      const d=s.timestamp?new Date(s.timestamp):new Date();
      const dateStr=d.toLocaleDateString("id-ID",{day:"numeric",month:"short"});
      dots+=`<div class="timeline-dot ${s.overall}" title="${dateStr}: ${s.overall}">
        <span>${i+1}</span>
        <div class="timeline-dot-tooltip">${dateStr} · ${s.overall}</div>
      </div>`;
    });
    el.innerHTML=`<div class="timeline-wrap">
      <div class="timeline-title">📊 Riwayat Scan
        <span class="timeline-trend ${data.trend}">${trendIcon} ${trendLabel}</span>
        <span style="font-size:11px;color:var(--muted);font-weight:600;margin-left:auto">${data.count} scan</span>
      </div>
      <div class="timeline-bar">${dots}</div>
    </div>`;
  }catch(e){
    el.innerHTML="";
  }
}

/* ---------- non-followers ---------- */
let NF_BATCH=0, NF_LOADING=false;

function renderNonFollowersButton(username){
  const el=$("#nonFollowersSection");
  if(!el) return;
  NF_BATCH=0; NF_LOADING=false;
  el.innerHTML=`<div class="nf-wrap">
    <button class="nf-btn" id="nfBtn" onclick="loadNonFollowers('${escapeAttr(username)}')">
      👀 Cek siapa yang belum follow back
    </button>
    <div class="nf-progress" id="nfProgress">
      <div class="nf-bar"><div class="nf-bar-fill" id="nfBarFill" style="width:0%"></div></div>
      <div class="nf-bar-text">
        <span id="nfBarLeft">Mengambil data...</span>
        <span id="nfBarRight"></span>
      </div>
    </div>
    <div class="nf-list" id="nfList"></div>
  </div>`;
}

async function loadNonFollowers(username){
  if(NF_LOADING) return;
  NF_LOADING=true;
  const btn=$("#nfBtn");
  const prog=$("#nfProgress");
  const fill=$("#nfBarFill");
  const left=$("#nfBarLeft");
  const right=$("#nfBarRight");
  const list=$("#nfList");

  if(btn) btn.disabled=true;
  if(prog) prog.classList.add("show");

  try{
    const r=await fetch(`/api/non-followers/${encodeURIComponent(username)}?batch=${NF_BATCH}`);
    const data=await r.json();

    if(data.error){
      if(left) left.textContent="Error: "+data.error;
      if(btn) btn.disabled=false;
      NF_LOADING=false;
      return;
    }

    const p=data.progress||{};
    if(fill) fill.style.width=(p.pct||0)+"%";
    if(left) left.textContent=`Following ${p.following_fetched||0}/${p.following_total||0} · Followers ${p.followers_fetched||0}/${p.followers_total||0}`;
    if(right) right.textContent=p.est_str||"";

    // Render non-followers
    if(data.non_followers&&data.non_followers.length){
      let html="";
      data.non_followers.forEach(u=>{
        const ava=u.avatar?`<img src="${u.avatar}" onerror="this.src='/assets/logo.png'" alt=""/>`:`<img src="/assets/logo.png" alt=""/>`;
        html+=`<div class="nf-user">
          ${ava}
          <div class="nf-user-info">
            <div class="nf-user-name">${escapeHtml(u.name||u.screen_name)} ${u.verified?"✓":""}</div>
            <div class="nf-user-handle">@${escapeHtml(u.screen_name)}</div>
          </div>
          <div class="nf-user-stats">${fmt(u.followers)} followers</div>
        </div>`;
      });
      list.insertAdjacentHTML("beforeend",html);
    }

    NF_BATCH++;

    if(data.has_more){
      // Show "load more" button
      const existingBtn=list.querySelector(".nf-more-btn");
      if(existingBtn) existingBtn.remove();
      const done=data.all_done;
      list.insertAdjacentHTML("beforeend",
        `<button class="nf-more-btn" onclick="loadNonFollowers('${escapeAttr(username)}')">
          ${done?"Tampilkan 5 lagi":"Muat 5 lagi... (masih mengambil data)"}
        </button>`);
      if(btn) btn.style.display="none";
    } else {
      // All done
      const existingBtn=list.querySelector(".nf-more-btn");
      if(existingBtn) existingBtn.remove();
      list.insertAdjacentHTML("beforeend",
        `<div class="nf-done">✅ Selesai — total ${data.total_non_followers} akun belum follow back</div>`);
      if(btn) btn.style.display="none";
    }

    if(right) right.textContent=data.total_non_followers?`${data.total_non_followers} belum follow back`:"";

  }catch(e){
    if(left) left.textContent="Error: "+(e.message||e);
  }finally{
    NF_LOADING=false;
  }
}

/* ---------- health score ---------- */
function renderHealthScore(score){
  const el=$("#healthScoreSection");
  if(!el) return;
  const s=Math.max(0,Math.min(100,score||0));
  const circ=2*Math.PI*28;
  const offset=circ-(s/100)*circ;
  const color=s>=70?'#7ab17a':s>=40?'#e8c84b':'#e89b9b';
  const label=s>=70?'Akun sehat':s>=40?'Perlu perhatian':'Akun bermasalah';
  el.innerHTML=`<div class="hs-wrap">
    <div class="hs-ring">
      <svg width="64" height="64" viewBox="0 0 64 64">
        <circle class="hs-ring-bg" cx="32" cy="32" r="28"/>
        <circle class="hs-ring-fg" cx="32" cy="32" r="28" stroke="${color}"
          stroke-dasharray="${circ}" stroke-dashoffset="${offset}"/>
      </svg>
      <div class="hs-ring-text" style="color:${color}">${s}</div>
    </div>
    <div class="hs-info">
      <div class="hs-label">Account Health Score</div>
      <div class="hs-desc">${label} — gabungan dari 8 layer audit di atas</div>
    </div>
  </div>`;
}

/* ---------- feature menu ---------- */
function renderFeatureMenu(username, analytics){
  const el=$("#featureMenu");
  if(!el) return;
  el.innerHTML=`<div class="fm-bar">
    <button class="fm-btn" onclick="togglePanel('analytics')">📊 Analytics</button>
    <button class="fm-btn" onclick="togglePanel('ghost')">👻 Ghost Followers</button>
    <button class="fm-btn" onclick="togglePanel('compare')">⚖️ Compare</button>
  </div>`;

  // Pre-render analytics (data already in response)
  if(analytics&&analytics.tweet_count){
    renderAnalytics(analytics);
  }
  // Pre-render compare inputs
  const cp=$("#comparePanel");
  if(cp) cp.innerHTML=`<div class="cp-wrap" id="cpWrap">
    <div class="cp-inputs">
      <input class="cp-input" id="cpUser1" placeholder="username 1" value="${escapeAttr(username)}"/>
      <input class="cp-input" id="cpUser2" placeholder="username 2"/>
      <button class="cp-btn" onclick="runCompare()">Bandingkan</button>
    </div>
    <div id="cpResult"></div>
  </div>`;
  // Pre-render ghost placeholder (lazy load on click)
  const gh=$("#ghostPanel");
  if(gh) gh.innerHTML=`<div class="gh-wrap" id="ghWrap" style="display:none"></div>`;
}

function togglePanel(name){
  const map={analytics:"analyticsPanel",ghost:"ghostPanel",compare:"comparePanel"};
  const id=map[name]; if(!id) return;
  const el=$("#"+id);
  if(!el) return;
  // Close others
  Object.values(map).forEach(k=>{
    if(k!==id){
      const e=$("#"+k);
      if(e){
        const w=e.querySelector(".an-wrap,.gh-wrap,.cp-wrap");
        if(w) w.style.display="none";
      }
    }
  });
  // Toggle this one
  const inner=el.querySelector(".an-wrap,.gh-wrap,.cp-wrap");
  if(!inner) return;
  // For ghost: if data not loaded yet and opening, load it
  const isHidden=inner.style.display==="none"||(!inner.style.display&&!inner.classList.contains("show"));
  if(isHidden){
    inner.style.display="block";
    inner.classList.add("show");
  } else {
    inner.style.display="none";
    inner.classList.remove("show");
  }
  // Lazy load ghost followers on first open
  if(name==="ghost"&&!inner.dataset.loaded){
    inner.dataset.loaded="1";
    inner.style.display="block";
    inner.classList.add("show");
    const uname=LAST?.username||LAST?.profile?.username||"";
    if(uname) loadGhostFollowers(uname);
    // Update menu active state
    document.querySelectorAll(".fm-btn").forEach(b=>b.classList.remove("active"));
    if(event&&event.target) event.target.classList.add("active");
    return; // skip toggle — loadGhostFollowers will set display
  }
}

/* ---------- analytics ---------- */
function renderAnalytics(a){
  const el=$("#analyticsPanel");
  if(!el||!a||!a.tweet_count) return;
  const fmt=n=>{if(n>=1e6)return(n/1e6).toFixed(1)+"M";if(n>=1e3)return(n/1e3).toFixed(1)+"K";return n;};
  // Content type colors
  const typeColors={text:"#aaa",image:"#7ab17a",video:"#e89b9b",link:"#a8a0c8",retweet:"#e8c84b"};
  const typeLabels={text:"Text",image:"Image",video:"Video",link:"Link",retweet:"RT"};
  let typesHtml="";
  Object.entries(a.content_types||{}).forEach(([k,v])=>{
    if(v>0) typesHtml+=`<div class="an-type">
      <span class="dot" style="background:${typeColors[k]||'#aaa'}"></span>
      <div class="count">${v}</div>
      <div class="name">${typeLabels[k]||k}</div>
    </div>`;
  });

  // Best time
  let bestHtml="";
  (a.best_time||[]).forEach(b=>{
    bestHtml+=`<div class="an-best-item">
      <div class="hr">${String(b.hour).padStart(2,'0')}:00</div>
      <div class="eng">${fmt(b.engagement)} eng</div>
    </div>`;
  });

  // Schedule heatmap
  let heatHtml='<div class="an-heat"><table><tr><td class="day-label"></td>';
  for(let h=0;h<24;h++){if(h%3===0)heatHtml+=`<td class="hr-label">${h}</td>`;else heatHtml+='<td></td>';}
  heatHtml+='</tr>';
  const maxCount=Math.max(1,...(a.schedule||[]).flatMap(d=>d.hours));
  (a.schedule||[]).forEach(d=>{
    heatHtml+=`<tr><td class="day-label">${d.day}</td>`;
    d.hours.forEach(c=>{
      const intensity=c>0?Math.min(1,c/maxCount):0;
      const bg=intensity>0?`rgba(170,160,200,${0.2+intensity*0.8})`:'var(--cloud)';
      heatHtml+=`<td style="background:${bg}" title="${d.day} — ${c} tweets"></td>`;
    });
    heatHtml+='</tr>';
  });
  heatHtml+='</table></div>';

  el.innerHTML=`<div class="an-wrap" id="anWrap">
    <div class="an-cards">
      <div class="an-card accent"><div class="val">${a.tweet_count}</div><div class="lbl">Tweets dianalisis</div></div>
      <div class="an-card"><div class="val">${fmt(a.total_views)}</div><div class="lbl">Total Views</div></div>
      <div class="an-card"><div class="val">${fmt(a.total_likes)}</div><div class="lbl">Total Likes</div></div>
      <div class="an-card"><div class="val">${fmt(a.total_replies)}</div><div class="lbl">Total Replies</div></div>
      <div class="an-card"><div class="val">${fmt(a.total_reposts)}</div><div class="lbl">Total Reposts</div></div>
      <div class="an-card"><div class="val">${fmt(a.total_bookmarks)}</div><div class="lbl">Bookmarks</div></div>
      <div class="an-card"><div class="val">${fmt(a.avg_views)}</div><div class="lbl">Avg Views</div></div>
      <div class="an-card engagement"><div class="val">${a.engagement_rate}%</div><div class="lbl">Engagement Rate</div></div>
    </div>
    <div class="an-section-title">📦 Tipe Konten</div>
    <div class="an-types">${typesHtml}</div>
    <div class="an-section-title">⏰ Waktu Terbaik Posting (by engagement)</div>
    <div class="an-best">${bestHtml||'<span style="color:var(--muted);font-size:12px">Data belum cukup</span>'}</div>
    <div class="an-section-title">📅 Jadwal Aktivitas</div>
    ${heatHtml}
  </div>`;
}

/* ---------- ghost followers ---------- */
async function loadGhostFollowers(username){
  const el=$("#ghostPanel");
  if(!el||!username) return;
  el.innerHTML=`<div class="gh-wrap show" id="ghWrap"><div style="text-align:center;padding:20px;color:var(--muted)">Mengambil data ghost followers...</div></div>`;
  try{
    const r=await fetch(`/api/ghost-followers/${encodeURIComponent(username)}`);
    const data=await r.json();
    if(data.error){
      el.innerHTML=`<div class="gh-wrap show"><div style="color:#e89b9b;padding:14px">Error: ${escapeHtml(data.error)}</div></div>`;
      return;
    }
    const gh=data.ghosts||[];
    let listHtml="";
    gh.forEach(u=>{
      const ava=u.avatar?`<img src="${u.avatar}" onerror="this.src='/assets/logo.png'" alt=""/>`:`<img src="/assets/logo.png" alt=""/>`;
      listHtml+=`<div class="nf-user">
        ${ava}
        <div class="nf-user-info">
          <div class="nf-user-name">${escapeHtml(u.name||u.screen_name)}</div>
          <div class="nf-user-handle">@${escapeHtml(u.screen_name)}</div>
        </div>
        <div class="nf-user-stats">0 tweets</div>
      </div>`;
    });
    el.innerHTML=`<div class="gh-wrap show" data-loaded="1" id="ghWrap" style="display:block">
      <div class="gh-stats">
        <div class="gh-stat ghost"><div class="val">${data.ghost_count}</div><div class="lbl">Ghost</div></div>
        <div class="gh-stat"><div class="val">${data.active_count}</div><div class="lbl">Active</div></div>
        <div class="gh-stat verified"><div class="val">${data.verified_count}</div><div class="lbl">Verified</div></div>
        <div class="gh-stat"><div class="val">${data.total_checked}</div><div class="lbl">Dicek</div></div>
      </div>
      ${gh.length?listHtml:'<div style="color:var(--muted);font-size:13px;padding:10px">Tidak ada ghost follower di 100 follower pertama</div>'}
      ${data.has_more?'<div style="font-size:11px;color:var(--muted);padding:8px">Menampilkan 100 follower pertama. Ada lebih banyak.</div>':''}
    </div>`;
  }catch(e){
    el.innerHTML=`<div class="gh-wrap show"><div style="color:#e89b9b;padding:14px">Error: ${escapeHtml(e.message||e)}</div></div>`;
  }
}

/* ---------- compare mode ---------- */
async function runCompare(){
  const u1=($("#cpUser1")||{}).value?.trim();
  const u2=($("#cpUser2")||{}).value?.trim();
  const res=$("#cpResult");
  if(!u1||!u2||!res) return;
  res.innerHTML='<div style="text-align:center;padding:20px;color:var(--muted)">Membandingkan...</div>';
  try{
    const [r1,r2]=await Promise.all([
      fetch("/api/check",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:u1})}).then(r=>r.json()),
      fetch("/api/check",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:u2})}).then(r=>r.json()),
    ]);
    function col(d){
      if(d.error) return `<div class="cp-col"><h4>@${escapeHtml(d.username||'?')}</h4><div style="color:#e89b9b">Error</div></div>`;
      const a=d.analytics||{};
      const hs=d.health_score||0;
      const hsColor=hs>=70?'#7ab17a':hs>=40?'#e8c84b':'#e89b9b';
      let rows=`<div class="cp-row"><span class="k">Health Score</span><span class="v" style="color:${hsColor}">${hs}/100</span></div>`;
      rows+=`<div class="cp-row"><span class="k">Overall</span><span class="v">${d.overall||'?'}</span></div>`;
      rows+=`<div class="cp-row"><span class="k">Followers</span><span class="v">${fmt((d.profile||{}).followers||0)}</span></div>`;
      rows+=`<div class="cp-row"><span class="k">Following</span><span class="v">${fmt((d.profile||{}).following||0)}</span></div>`;
      rows+=`<div class="cp-row"><span class="k">Avg Views</span><span class="v">${fmt(a.avg_views||0)}</span></div>`;
      rows+=`<div class="cp-row"><span class="k">Engagement Rate</span><span class="v">${a.engagement_rate||0}%</span></div>`;
      rows+=`<div class="cp-row"><span class="k">Total Likes</span><span class="v">${fmt(a.total_likes||0)}</span></div>`;
      rows+=`<div class="cp-row"><span class="k">Total Replies</span><span class="v">${fmt(a.total_replies||0)}</span></div>`;
      rows+=`<div class="cp-row"><span class="k">Total Reposts</span><span class="v">${fmt(a.total_reposts||0)}</span></div>`;
      rows+=`<div class="cp-row"><span class="k">Bookmarks</span><span class="v">${fmt(a.total_bookmarks||0)}</span></div>`;
      (d.layers||[]).forEach(l=>{
        const c=l.status==='safe'?'#7ab17a':l.status==='warning'?'#e8c84b':'#e89b9b';
        rows+=`<div class="cp-row"><span class="k">${l.name}</span><span class="v" style="color:${c}">${l.status}</span></div>`;
      });
      return `<div class="cp-col"><h4>@${escapeHtml(d.username||u1)}</h4>${rows}</div>`;
    }
    res.innerHTML=`<div class="cp-grid">${col(r1)}${col(r2)}</div>`;
  }catch(e){
    res.innerHTML=`<div style="color:#e89b9b;padding:14px">Error: ${escapeHtml(e.message||e)}</div>`;
  }
}

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

/* ---------- history drawer (shared) ---------- */
function fmtTime(ts){
  if(!ts) return "";
  try{
    const d=new Date(ts); if(isNaN(d)) return "";
    const diff=(Date.now()-d.getTime())/1000;
    if(diff<60) return LANG==="id"?"baru saja":"just now";
    if(diff<3600) return Math.floor(diff/60)+"m";
    if(diff<86400) return Math.floor(diff/3600)+"h";
    if(diff<604800) return Math.floor(diff/86400)+"d";
    return d.toLocaleDateString(LANG==="id"?"id-ID":"en-US",{day:"numeric",month:"short"});
  }catch(e){return "";}
}
function openDrawer(){$("#historyOv").classList.add("show");$("#historyDrawer").classList.add("show");$("#historyDrawer").setAttribute("aria-hidden","false");loadHistory();}
function closeDrawer(){$("#historyOv").classList.remove("show");$("#historyDrawer").classList.remove("show");$("#historyDrawer").setAttribute("aria-hidden","true");}
$("#historyBtn").onclick=openDrawer;
$("#historyClose").onclick=closeDrawer;
$("#historyOv").onclick=closeDrawer;

async function loadHistory(){
  const box=$("#histList");
  box.innerHTML=`<div class="hist-empty">…</div>`;
  try{
    const r=await fetch("/api/history?limit=50");const list=await r.json();
    if(!Array.isArray(list)||!list.length){box.innerHTML=`<div class="hist-empty">${t("histEmpty")}</div>`;return;}
    box.innerHTML="";
    list.forEach(it=>{
      const st=it.overall||"warning";
      const ava=it.avatar_url||"/assets/logo.png";
      const el=document.createElement("div");
      el.className="hist-item";
      el.innerHTML=`
        <img src="${escapeAttr(ava)}" onerror="this.src='/assets/logo.png'" alt=""/>
        <div class="hi-meta">
          <div class="hi-name">@${escapeHtml(it.username||"")}</div>
          <div class="hi-time">${escapeHtml(fmtTime(it.timestamp))}</div>
        </div>
        <span class="hi-badge ${st}">${st==="safe"?t("sumClean"):st==="banned"?t("sumBan"):t("sumMod")}</span>`;
      el.onclick=()=>openHistoryDetail(it.id,it.username);
      box.appendChild(el);
    });
  }catch(e){box.innerHTML=`<div class="hist-empty">${t("histEmpty")}</div>`;}
}

async function openHistoryDetail(id,uname){
  closeDrawer();
  show("stateLoading");
  window.scrollTo({top:$(".search-card").offsetTop-20,behavior:"smooth"});
  try{
    const r=await fetch("/api/history-detail/"+encodeURIComponent(id));
    if(!r.ok) throw new Error("not found");
    const data=await r.json();
    LAST=data;
    renderResult(data);
    show("result");
  }catch(e){
    // fallback: live re-scan
    if(uname) scan(uname);
    else{$("#errMsg").textContent=("history hilang 🍃");show("stateError");}
  }
}

/* ---------- CapyAi chat ---------- */
const CHAT_TPLS=["profile","niche","recover","growth","content"];
let CHAT_BOOTED=false;
function buildChatTemplates(){
  const box=$("#chatTemplates");box.innerHTML="";
  CHAT_TPLS.forEach(key=>{
    const b=document.createElement("button");
    b.className="tpl-chip";b.textContent=t("tpl_"+key);
    b.onclick=()=>sendChat("",key);
    box.appendChild(b);
  });
}
function chatMsg(text,who){
  const log=$("#chatLog");
  const m=document.createElement("div");
  m.className="msg "+who;
  m.textContent=text;
  log.appendChild(m);
  log.scrollTop=log.scrollHeight;
  return m;
}
function openChat(){
  $("#chatOv").classList.add("show");$("#chatBox").classList.add("show");$("#chatBox").setAttribute("aria-hidden","false");
  if(!CHAT_BOOTED){
    buildChatTemplates();
    chatMsg(t("chatGreet"),"capy");
    CHAT_BOOTED=true;
    // prefill target with last scanned username
    if(LAST){const u=(LAST.profile&&LAST.profile.username)||LAST.username;if(u)$("#chatUser").value=u;}
  }
  setTimeout(()=>$("#chatInput").focus(),300);
}
function closeChat(){$("#chatOv").classList.remove("show");$("#chatBox").classList.remove("show");$("#chatBox").setAttribute("aria-hidden","true");}
$("#capyFab").onclick=openChat;
$("#chatClose").onclick=closeChat;
$("#chatOv").onclick=closeChat;

let CHAT_BUSY=false;
function updateQuotaBadge(data){
  if(!data || typeof data.limit==="undefined") return;
  const st=$("#chatStatus");
  if(!st) return;
  const rem=(typeof data.remaining!=="undefined")?data.remaining:Math.max(0,data.limit-(data.used||0));
  const foll=data.follows?"✓":"";
  st.textContent=(LANG==="id"?`Sisa ${rem}/${data.limit} chat hari ini ${foll}`:`${rem}/${data.limit} chats left today ${foll}`);
}
function followCta(brand){
  const log=$("#chatLog");
  const wrap=document.createElement("div");
  wrap.className="msg capy";
  const url="https://x.com/"+encodeURIComponent(brand||"hyaerina");
  wrap.innerHTML=`${escapeHtml(LANG==="id"?"Mau kuota lebih? Follow dulu ya 👇":"Want more quota? Follow first 👇")}
    <a href="${url}" target="_blank" rel="noopener" class="follow-cta">🐦 Follow @${escapeHtml(brand||"hyaerina")}</a>`;
  log.appendChild(wrap);log.scrollTop=log.scrollHeight;
}
async function sendChat(message,template){
  if(CHAT_BUSY) return;
  const uname=($("#chatUser").value||"").trim().replace(/^@/,"");
  const msg=(message||$("#chatInput").value||"").trim();
  if(!template && !msg) return;
  if(!uname){chatMsg(t("chatNeedUser"),"capy");return;}
  // show user's bubble
  if(template && !msg) chatMsg(t("tpl_"+template),"me");
  else chatMsg(msg,"me");
  $("#chatInput").value="";
  CHAT_BUSY=true;$("#chatSend").disabled=true;
  const typing=chatMsg(t("chatThinking"),"typing");
  try{
    const r=await fetch("/api/capy-chat",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({username:uname,message:msg,template:template||""})});
    const data=await r.json();
    typing.remove();
    if(r.status===429){
      // quota exhausted
      chatMsg(data.reply||t("deepErr"),"capy");
      if(!data.follows) followCta(data.brand);
      updateQuotaBadge({limit:data.limit,used:data.used,remaining:0,follows:data.follows});
      return;
    }
    if(r.status===503 && data.code==="cline_auth"){
      chatMsg(data.reply||t("chatAuth"),"capy");
      return;
    }
    if(data.error && !data.reply) throw new Error(data.error);
    chatMsg(data.reply||"🦫","capy");
    updateQuotaBadge(data);
    // gentle nudge when guest is running low
    if(!data.follows && typeof data.remaining!=="undefined" && data.remaining<=2 && data.remaining>0){
      followCta(data.brand);
    }
  }catch(e){
    typing.remove();
    chatMsg(t("deepErr"),"capy");
  }finally{CHAT_BUSY=false;$("#chatSend").disabled=false;$("#chatInput").focus();}
}
$("#chatSend").onclick=()=>sendChat();
$("#chatInput").addEventListener("keydown",e=>{if(e.key==="Enter")sendChat();});


/* boot */
applyTheme();applyLang();buildSlides();loadRecent();
