"""Kayock Writer single-page UI (no build step, no external assets).

Upgraded interface with a left navigation tree grouping Novel Forge,
Poetry Forge, Short Story Forge, Story Forge, The Weaver, My Writing and
Settings. Responsive: the sidebar collapses on narrow screens; all sizing
uses clamp()/percent so the app reads well on phone, tablet, and desktop.
"""
from __future__ import annotations

_CSS = r"""
:root{
  --bg:#0f1117; --bg2:#151823; --bg3:#1c2030; --panel:#181c29;
  --ink:#e8e6df; --ink-dim:#a9a79f; --ink-faint:#6e6d68;
  --accent:#c8a24a; --accent2:#8fb573; --accent3:#7ba8c9;
  --danger:#c96a5b; --line:#2a2f42; --ok:#7fbf8a;
  --radius:10px; --shadow:0 6px 24px rgba(0,0,0,.35);
  --sidebar-w: clamp(220px, 22vw, 300px);
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:linear-gradient(160deg,var(--bg) 0%,#12141d 55%,#151119 100%);
  color:var(--ink);
  font-family:Georgia,'Times New Roman',serif;
  font-size:clamp(15px,1.05vw,17px);
  line-height:1.55;
  min-height:100vh;
}
button,input,select,textarea{font-family:inherit;font-size:.95em;color:var(--ink)}
a{color:var(--accent)}
#appbar{
  display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  padding:10px clamp(12px,2vw,26px);
  background:rgba(15,17,23,.9);border-bottom:1px solid var(--line);
  position:sticky;top:0;z-index:30;backdrop-filter:blur(6px);
}
#appbar .brand{font-size:clamp(1.1rem,2.2vw,1.45rem);color:var(--accent);letter-spacing:.04em}
#appbar .brand small{color:var(--ink-dim);font-style:italic}
#modelDot{width:10px;height:10px;border-radius:50%;background:#666;display:inline-block;margin-right:6px}
#modelDot.online{background:var(--ok);box-shadow:0 0 8px rgba(127,191,138,.8)}
#modelDot.offline{background:var(--danger)}
#appbar .status{font-size:.85em;color:var(--ink-dim)}
#burger{display:none;background:none;border:1px solid var(--line);color:var(--ink);
  border-radius:8px;padding:6px 12px;cursor:pointer}
#layout{display:flex;min-height:calc(100vh - 58px)}
nav#tree{
  width:var(--sidebar-w);flex:0 0 var(--sidebar-w);
  background:var(--bg2);border-right:1px solid var(--line);
  padding:14px 10px 40px;overflow-y:auto;
}
nav#tree .group{margin:10px 0 2px;font-size:.8em;letter-spacing:.14em;
  text-transform:uppercase;color:var(--accent3)}
nav#tree button.nav{
  display:block;width:100%;text-align:left;background:none;border:0;
  color:var(--ink);padding:7px 12px;border-radius:8px;cursor:pointer;
  font-size:.95em;margin:1px 0;
}
nav#tree button.nav:hover{background:var(--bg3)}
nav#tree button.nav.active{background:linear-gradient(90deg,rgba(200,162,74,.18),transparent);
  color:var(--accent);border-left:3px solid var(--accent)}
nav#tree .sub{padding-left:18px}
main{flex:1;padding:clamp(14px,2.5vw,34px);max-width:1200px;margin:0 auto;width:100%}
section.page{display:none}
section.page.active{display:block}
.hero{margin:6px 0 18px}
.hero h1{margin:0 0 6px;font-size:clamp(1.4rem,3.2vw,2.1rem);color:var(--accent);font-weight:600}
.hero p{margin:0;color:var(--ink-dim);font-style:italic}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px 18px;box-shadow:var(--shadow)}
.card h3{margin:0 0 10px;font-size:1.02em;color:var(--accent2);letter-spacing:.02em}
.card.wide{grid-column:1/-1}
label{display:block;margin:10px 0 4px;color:var(--ink-dim);font-size:.9em}
input[type=text],input[type=number],input[type=password],select,textarea{
  width:100%;background:var(--bg3);border:1px solid var(--line);border-radius:8px;
  padding:9px 11px;color:var(--ink);
}
textarea{min-height:110px;resize:vertical;line-height:1.6}
textarea.big{min-height:260px}
input:focus,select:focus,textarea:focus{outline:1px solid var(--accent);border-color:var(--accent)}
.btn,button.btn{
  display:inline-block;background:linear-gradient(180deg,#242a3c,#1d2233);
  border:1px solid var(--line);border-radius:8px;padding:8px 16px;cursor:pointer;
  color:var(--ink);margin:4px 6px 4px 0;
}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.btn.primary{background:linear-gradient(180deg,#8a6f2f,#6f5a26);border-color:#a5852f;color:#fff8e6}
.btn.primary:hover{color:#fff}
.btn.danger{border-color:#7a4038;color:#e0a49a}
.btn:disabled{opacity:.45;cursor:not-allowed}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}
.row>div{flex:1;min-width:160px}
.row>.fixed{flex:0 0 auto;min-width:0}
.small{font-size:.86em;color:var(--ink-dim)}
.status{background:var(--bg3);border:1px dashed var(--line);border-radius:8px;
  padding:9px 12px;color:var(--ink-dim);font-size:.92em;white-space:pre-wrap}
.status.ok{border-color:rgba(127,191,138,.5);color:var(--ok)}
.status.err{border-color:rgba(201,106,91,.6);color:#e0a49a}
.chip{display:inline-block;background:var(--bg3);border:1px solid var(--line);
  border-radius:999px;padding:2px 10px;margin:2px 4px 2px 0;font-size:.8em;color:var(--ink-dim)}
.chip.gold{color:var(--accent);border-color:rgba(200,162,74,.5)}
.chip.green{color:var(--ok);border-color:rgba(127,191,138,.5)}
.chip.red{color:#e0a49a;border-color:rgba(201,106,91,.5)}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:.9em}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--accent3);font-weight:600;background:var(--bg2)}
tr:hover td{background:rgba(200,162,74,.05)}
.badge{font-size:.75em;letter-spacing:.1em;text-transform:uppercase;
  color:var(--ink-faint);margin-left:8px}
.navtree-note{color:var(--ink-faint);font-size:.8em;padding:10px 12px;font-style:italic}
.notice{border-left:3px solid var(--accent);padding:8px 14px;background:rgba(200,162,74,.06);
  border-radius:0 8px 8px 0;margin:10px 0;color:var(--ink-dim);font-size:.92em}
.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 16px;font-size:.92em}
.kv .k{color:var(--ink-faint)}
#toast{position:fixed;bottom:18px;right:18px;max-width:min(420px,80vw);
  background:var(--bg3);border:1px solid var(--accent);border-radius:10px;
  padding:10px 16px;box-shadow:var(--shadow);z-index:99;display:none;font-size:.95em}
#toast.err{border-color:var(--danger);color:#e8b0a7}
#toast.ok{color:var(--ok);border-color:rgba(127,191,138,.6)}
.altbox{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0;background:var(--bg3)}
.altbox .meta{color:var(--ink-faint);font-size:.8em;margin-bottom:4px}
details{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:8px 0;background:var(--bg2)}
summary{cursor:pointer;color:var(--accent3)}
.cardrow{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}
@media (max-width:900px){
  #burger{display:inline-block}
  nav#tree{position:fixed;left:0;top:58px;bottom:0;z-index:40;transform:translateX(-105%);
    transition:transform .18s ease;box-shadow:var(--shadow)}
  nav#tree.open{transform:translateX(0)}
  #layout{min-height:calc(100vh - 100px)}
  main{padding:14px}
}
"""

_JS = r"""
/* ============================ helpers ============================ */
const q=(id)=>document.getElementById(id);
const esc=(s)=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, payload, method){
  const opts={method:method||(payload?'POST':'GET'),headers:{'Content-Type':'application/json'}};
  if(payload!==undefined&&payload!==null)opts.body=JSON.stringify(payload);
  const r=await fetch(path,opts);
  let d;
  try{d=await r.json();}catch(e){d={ok:false,message:`HTTP ${r.status}: unreadable response`};}
  if(!r.ok&&!d.message)d.message=`HTTP ${r.status}`;
  return d;
}
let toastTimer=null;
function toast(msg,kind){
  const t=q('toast');t.textContent=msg;t.className=kind||'';
  t.style.display='block';clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>{t.style.display='none';},5200);
}
function show(page){
  document.querySelectorAll('section.page').forEach(s=>s.classList.remove('active'));
  const el=q('pg-'+page);if(el)el.classList.add('active');
  document.querySelectorAll('nav#tree button.nav').forEach(b=>{
    const key=b.dataset.navkey;
    const wanted=key? key===S.uiKey : b.dataset.page===page;
    b.classList.toggle('active',wanted);
  });
  closeTree();
  const renderers={
    home:renderHome, studio:()=>renderStudio(), archive:()=>renderArchive(),
    novelforge:()=>renderNovelForge(), weaver:()=>renderWeaver(),
    storyoverview:renderStoryOverview, storycreate:renderStoryCreate,
    storychapters:renderStoryChapters, storyeditor:renderStoryEditor,
    storydrafts:renderStoryDrafts, storyprose:renderStoryProse,
    mywriting:()=>renderArchive('mywriting'), finishing:renderFinishing, settings:renderSettings,
  };
  if(renderers[page])renderers[page]();
  window.scrollTo({top:0});
}
function openTree(){q('tree').classList.toggle('open');}
function closeTree(){q('tree').classList.remove('open');}

/* ============================ state ============================ */
const S={
  voices:[], archive:[], projects:[], config:null,
  studio:{type:'poem',mode:'create',last:null,polished:null,alts:[],sel:null},
  novel:{universes:[],active:null},
  story:{project:'',book:'book_1'},
  weaver:{last:null},
};

/* ============================ home ============================ */
async function renderHome(){
  const st=await api('/api/status');
  const d=st||{};
  q('homeStatus').innerHTML=`
    <div class="kv">
      <span class="k">Application</span><span>${esc(d.app||'Kayock Writer')} ${esc(d.version||'')}</span>
      <span class="k">Model endpoint</span><span>${esc((d.model&&d.model.base_url)||'—')} (${esc((d.model&&d.model.model)||'')})</span>
      <span class="k">Model status</span><span>${d.model&&d.model.online?'<span class="chip green">online</span>':'<span class="chip red">offline — check Settings</span>'}</span>
      <span class="k">Data folder</span><span>${esc(d.data_dir||'')}</span>
      <span class="k">Eric private voice pack</span><span>${d.voice_pack&&d.voice_pack.loaded?`<span class="chip gold">loaded (${d.voice_pack.source_count} source poems)</span>`:'<span class="chip">not installed — derived style settings active</span>'}</span>
    </div>`;
}

/* ============================ voices / studio ============================ */
async function loadVoices(){
  if(S.voices.length)return;
  const d=await api('/api/voices');
  S.voices=(d&&d.voices)||[];
}
const GENERIC_VOICES=['Lyrical','Spare and direct','Narrative','Dark and mythic','Hopeful and intimate','Spoken-word energy'];
function voiceOptions(forStory){
  let html='<option>My natural voice</option>';
  for(const v of S.voices){
    if(v.id==='eric_short_fiction'&&!forStory)continue;
    html+=`<option>${esc(v.name)}</option>`;
  }
  for(const g of GENERIC_VOICES)html+=`<option>${esc(g)}</option>`;
  return html;
}
function strengthsFor(voiceName){
  const v=S.voices.find(v=>v.name===voiceName);
  if(!v||!v.strengths||!v.strengths.length)return[];
  const opts=[v.default_strength,...v.strengths.filter(s=>s!==v.default_strength)];
  return opts;
}
async function renderStudio(){
  await loadVoices();
  const st=S.studio;const isStory=st.type==='short_story';
  q('studioTitle').textContent=isStory?'Short Story Forge — Creator & Polisher':'Poetry Forge — Creator & Polisher';
  q('studioHero').textContent=isStory
    ?'Create and polish short fiction with the Eric — Short Fiction fingerprint and public-domain archetypes.'
    :'Create and polish poems with the Eric — Poet/Narrator fingerprint and the full voice pack.';
  q('studioType').value=st.type;
  q('poemVoice').innerHTML=voiceOptions(isStory);
  updateVoiceControls();
  updateCraftControls();
}
function setStudio(type,mode,uiKey){
  S.studio.type=type;S.studio.mode=mode;S.uiKey=uiKey||('studio-'+type+'-'+mode);
  q('studioCreate').style.display=mode==='create'?'block':'none';
  q('studioPolish').style.display=mode==='polish'?'block':'none';
  show('studio');
}
function updateVoiceControls(){
  const voice=q('poemVoice').value;
  const box=q('voiceProfileControls');
  const strengths=strengthsFor(voice);
  const v=S.voices.find(v=>v.name===voice);
  if(v&&strengths.length){
    box.style.display='block';
    q('voiceProfileHead').innerHTML=`<b>${esc(v.name)}</b> <span class="chip">${esc(v.kind)}</span>`;
    q('poemVoiceStrength').innerHTML=strengths.map((s,i)=>`<option${i===0?' selected':''}>${esc(s)}</option>`).join('');
    q('voiceProfileSources').innerHTML=v.source_titles.length
      ?'<span class="small">Read-only source references: '+v.source_titles.map(t=>`<span class="chip">${esc(t)}</span>`).join('')+'</span>'
      :'<span class="small">No copyrighted source text is stored in this profile.</span>';
    q('voiceProfileBadges').innerHTML=
      (v.has_private_sources?'<span class="chip gold">private source poems active</span>':'')
      +(v.id==='eric_poet_narrator'?'<span class="chip green">fingerprint: Eric — Poet/Narrator</span>':'')
      +(v.id==='eric_short_fiction'?'<span class="chip green">fingerprint: Eric — Short Fiction</span>':'');
  }else{
    box.style.display='none';
    q('poemVoiceStrength').innerHTML='<option>Recognizably Eric</option>';
    q('voiceProfileBadges').innerHTML='';
  }
}
function updateCraftControls(){
  const isStory=q('studioType').value==='short_story';
  q('poemOnlyCraftControls').style.display=isStory?'none':'block';
  q('storyLengthControl').style.display=isStory?'block':'none';
  q('rhymeTargetPreview').textContent=isStory
    ?'Rhyme and meter controls are unused in short-story mode (prose output).'
    :'Rhyme and rhythm preferences never override meaning or voice.';
}

async function studioCreate(){
  const payload={
    writing_type:q('studioType').value,
    theme:q('poemTheme').value,emotion:q('poemEmotion').value,
    imagery:q('poemImagery').value,speaker:q('poemSpeaker').value,
    personal_memory:q('poemMemory').value,audience:q('poemAudience').value,
    voice:q('poemVoice').value,voice_strength:q('poemVoiceStrength').value,
    form:q('poemForm').value,
    rhyme_preference:q('poemRhymePreference').value,
    rhythm_preference:q('poemRhythmPreference').value,
    length:q('poemLength').value,canon:q('poemCanon').value,
    opening_line:q('poemOpening').value,variation:q('poemVariation').checked,
  };
  const btn=q('createButton');btn.disabled=true;
  q('creatorStatus').textContent='Working with '+q('poemVoice').value+'…';
  const d=await api('/api/writer/poetry/create',payload);
  btn.disabled=false;
  if(!d.ok){q('creatorStatus').textContent=d.message||'Creation failed.';toast(d.message||'Creation failed.','err');return;}
  S.studio.last=d;
  q('poemResult').value=d.poem||'';
  q('poemResultTitle').value=d.suggested_title||'';
  q('creatorStatus').textContent=`${d.message} · voice: ${d.voice_profile||'natural'} · model: ${d.model_name||''}`;
  toast(d.message,'ok');
}
async function studioSaveDraft(kind){
  const d=S.studio.last;
  const payload={
    poem:q('poemResult').value,
    title:q('poemResultTitle').value,
    writing_type:q('studioType').value,
    version_kind:kind,
    settings:d&&d.settings||{},
  };
  const res=await api('/api/writer/poetry/save',payload);
  toast(res.message||'Saved.',res.ok?'ok':'err');
  if(res.ok)loadArchive();
}
async function studioPolish(){
  const isStory=q('studioType').value==='short_story';
  const payload={
    writing_type:q('studioType').value,
    poem:q('poemPolisherInput').value,
    focus:q('poemPolishFocus').value,
    voice:q('poemVoice').value,voice_strength:q('poemVoiceStrength').value,
    speaker:q('poemSpeaker').value,personal_memory:q('poemMemory').value,
    audience:q('poemAudience').value,canon:q('poemCanon').value,
    opening_line:q('poemOpening').value,
  };
  const btn=q('polishButton');btn.disabled=true;
  q('poemPolishStatus').textContent='Polishing…';
  const d=await api('/api/writer/poetry/polish',payload);
  btn.disabled=false;
  if(!d.ok){q('poemPolishStatus').textContent=d.message||'Polish failed.';toast(d.message||'Polish failed.','err');return;}
  S.studio.polished=d;
  q('poemPolishedResult').value=d.poem||'';
  q('poemPolishStatus').textContent=`${d.message} · focus: ${d.focus}`;
  toast(d.message,'ok');
}
function polishKeepOriginal(){q('poemPolishedResult').value='';S.studio.polished=null;toast('Kept the original. Polished copy discarded.');}
function polishUsePolished(){
  if(!S.studio.polished){toast('Nothing polished yet.','err');return;}
  q('poemPolisherInput').value=S.studio.polished.poem;
  S.studio.polished=null;q('poemPolishedResult').value='';
  toast('Polished version moved into the work area.','ok');
}
async function polishSaveBoth(){
  const isStory=q('studioType').value==='short_story';
  const group='polish_'+Date.now();
  const settings={writing_type:q('studioType').value,voice:q('poemVoice').value,
    voice_strength:q('poemVoiceStrength').value,speaker:q('poemSpeaker').value,
    personal_memory:q('poemMemory').value,audience:q('poemAudience').value,
    canon:q('poemCanon').value,opening_line:q('poemOpening').value};
  const base={writing_type:q('studioType').value,settings,version_group:group};
  const r1=await api('/api/writer/poetry/save',{...base,poem:q('poemPolisherInput').value,
    title:q('poemPolisherTitle').value,version_kind:'original',source_mode:'polisher',
    polish_focus:q('poemPolishFocus').value});
  const r2=await api('/api/writer/poetry/save',{...base,poem:q('poemPolishedResult').value,
    title:(q('poemPolisherTitle').value||'Untitled')+' — polished',
    version_kind:'polished',source_mode:'polisher',polish_focus:q('poemPolishFocus').value});
  toast((r1.message||'')+' '+((r2.ok&&r2.message)||''),(r1.ok&&r2.ok)?'ok':'err');
  if(r1.ok||r2.ok)loadArchive();
}

/* selection workshop */
function captureSelection(){
  const ta=q('poemPolisherInput');
  const start=ta.selectionStart,end=ta.selectionEnd;
  const sel=ta.value.slice(start,end);
  if(!sel.trim()){toast('Select lines inside the poem first.','err');return;}
  S.studio.sel={poem:ta.value,selection:sel,selection_start:start,selection_end:end};
  q('selPreview').textContent=sel;
  q('selStatus').textContent=`Captured characters ${start}–${end} (${sel.split(/\n/).filter(x=>x.trim()).length} nonblank lines).`;
}
async function createAlternatives(){
  if(!S.studio.sel){captureSelection();if(!S.studio.sel)return;}
  const payload={...S.studio.sel,
    title:q('poemPolisherTitle').value,
    focus:q('poemSelectionFocus').value,note:q('poemSelectionNote').value,
    voice:q('poemVoice').value,voice_strength:q('poemVoiceStrength').value};
  const btn=q('altButton');btn.disabled=true;
  q('selStatus').textContent='Creating three alternatives…';
  const d=await api('/api/writer/poetry/revise-selection',payload);
  btn.disabled=false;
  if(!d.ok){q('selStatus').textContent=d.message||'Workshop failed.';toast(d.message||'Workshop failed.','err');return;}
  S.studio.alts=d.alternatives||[];
  q('poemSelectionAlternatives').innerHTML=S.studio.alts.map((a,i)=>`
    <div class="altbox"><div class="meta">Alternative ${i+1} — verified positions ${d.verified_selection_start}–${d.verified_selection_end}</div>
    <pre style="white-space:pre-wrap;margin:0;font-family:inherit">${esc(a)}</pre>
    <button class="btn primary" onclick="useAlternative(${i})">Use this alternative</button></div>`).join('');
  q('selStatus').textContent=d.message;
  toast(d.message,'ok');
}
function useAlternative(i){
  const alt=S.studio.alts[i];if(alt===undefined)return;
  const ta=q('poemPolisherInput');const sel=S.studio.sel;
  const start=sel.selection_start,end=sel.selection_end;
  if(ta.value.slice(start,end)!==sel.selection){
    toast('The poem changed since capture — reselect the passage.','err');return;}
  ta.value=ta.value.slice(0,start)+alt+ta.value.slice(end);
  q('selStatus').textContent='Alternative '+String(i+1)+' applied to the work area.';
  toast('Alternative applied.','ok');
}

/* ============================ archive ============================ */
async function loadArchive(){
  const d=await api('/api/writer/poetry/archive');
  S.archive=(d&&d.groups)||[];
  return d;
}
async function renderArchive(ctx){
  await loadArchive();
  q('archiveSummary').textContent=`${S.archive.length} saved work group(s) in the archive. Every file is scanned read-only.`;
  renderArchiveList();
}
function archiveFiltered(){
  const term=String(q('archiveSearch').value||'').toLowerCase();
  const filter=q('archiveFilter').value;
  return S.archive.filter(g=>{
    if(filter==='poem'&&g.content_type!=='poem')return false;
    if(filter==='short_story'&&g.content_type!=='short_story')return false;
    if(filter==='legacy'&&!g.legacy)return false;
    if(filter==='for_akaysha'&&!g.for_akaysha)return false;
    if(filter==='for_nevaeh'&&!g.for_nevaeh)return false;
    if(term){
      const hay=[g.title,g.author,g.voice,g.theme,g.emotion,g.speaker,g.personal_memory,g.audience].join(' ').toLowerCase();
      if(!hay.includes(term))return false;
    }
    return true;
  });
}
function renderArchiveList(){
  const list=archiveFiltered();
  q('archiveList').innerHTML=list.length?list.map(g=>`
    <div class="card">
      <h3>${esc(g.title)} <span class="chip ${g.content_type==='poem'?'':'gold'}">${esc(g.content_type||'poem')}</span>
      ${g.legacy?'<span class="chip gold">legacy</span>':''}${g.for_akaysha?'<span class="chip">for Akaysha</span>':''}${g.for_nevaeh?'<span class="chip">for Nevaeh</span>':''}</h3>
      <div class="small">${esc(g.latest_created_display||'')} · ${g.version_total} version(s) · voice: ${esc(g.voice||'—')}</div>
      <div>${g.version_counts.draft?`<span class="chip">${g.version_counts.draft} draft</span>`:''}${g.version_counts.original?`<span class="chip green">${g.version_counts.original} original</span>`:''}${g.version_counts.polished?`<span class="chip gold">${g.version_counts.polished} polished</span>`:''}</div>
      <div class="small">Theme: ${esc(g.theme||'—')} · Emotion: ${esc(g.emotion||'—')}</div>
      <button class="btn" onclick="openArchiveItem('${esc(g.latest_any)}')">Open latest</button>
      <button class="btn" onclick="openArchiveVersions('${esc(g.key)}')">All versions</button>
    </div>`).join('')
    :'<div class="status">No archive entries match. Saved poems and stories appear here automatically.</div>';
}
async function openArchiveItem(filename){
  const d=await api('/api/writer/poetry/archive/read?name='+encodeURIComponent(filename));
  if(!d.ok){toast(d.message||'Not found.','err');return;}
  q('archiveDetail').innerHTML=`
    <div class="card wide"><h3>${esc(d.title)} <span class="chip">${esc(d.version)}</span></h3>
    <div class="small">by ${esc(d.author||'')} ${d.copyright?'· '+esc(d.copyright):''} · created ${esc(d.created_display||'')} · model ${esc(d.model||'—')}</div>
    <pre style="white-space:pre-wrap;font-family:inherit;margin:12px 0">${esc(d.poem||'')}</pre>
    <details><summary>Craft settings carried with this draft</summary>
      <div class="kv" style="margin-top:8px">
        <span class="k">Voice</span><span>${esc(d.voice||'—')} (${esc(d.voice_strength||'—')})</span>
        <span class="k">Form / length</span><span>${esc(d.form||'—')} / ${esc(d.length||'—')}</span>
        <span class="k">Rhyme / rhythm</span><span>${esc(d.rhyme_preference||'—')} / ${esc(d.rhythm_preference||'—')}</span>
        <span class="k">Canon</span><span>${esc(d.canon||'—')}</span>
        <span class="k">Opening line</span><span>${esc(d.opening_line||'—')}</span>
      </div></details>
    </div>`;
  q('archiveDetail').scrollIntoView({behavior:'smooth'});
}
function openArchiveVersions(key){
  const g=S.archive.find(x=>x.key===key);if(!g)return;
  q('archiveDetail').innerHTML=`<div class="card wide"><h3>${esc(g.title)} — all versions</h3>
    <div class="tablewrap"><table><tr><th>File</th><th>Version</th><th>Created</th><th>Voice</th><th></th></tr>
    ${g.versions.map(v=>`<tr><td>${esc(v.filename)}</td><td>${esc(v.version)}</td><td>${esc(v.created_display)}</td><td>${esc(v.voice||'')}</td>
    <td><button class="btn" onclick="openArchiveItem('${esc(v.filename)}')">Read</button></td></tr>`).join('')}
    </table></div>
    <h3 style="margin-top:14px">Recordings</h3>
    <div class="small">${esc(g.recordings&&g.recordings.master_policy||'')}</div>
    <div>${g.recordings&&g.recordings.found_count?`<span class="chip green">${g.recordings.found_count} recording slot(s) found</span>`:'<span class="chip">no recordings yet</span>'}</div>
    <div class="row" style="margin-top:10px">
      <button class="btn" onclick="prepareRecordings('${esc(g.title)}')">Prepare recording folder</button>
      <button class="btn" onclick="openRecordings('${esc(g.title)}')">Open folder on server</button>
    </div>
    <h3 style="margin-top:14px">Legacy & dedication flags</h3>
    <label><input type="checkbox" id="flagLegacy" ${g.legacy?'checked':''}> Legacy work</label>
    <label><input type="checkbox" id="flagAkaysha" ${g.for_akaysha?'checked':''}> For Akaysha</label>
    <label><input type="checkbox" id="flagNevaeh" ${g.for_nevaeh?'checked':''}> For Nevaeh</label>
    <button class="btn" onclick="saveLegacyFlags('${esc(g.title)}')">Save flags</button>
    ${g.legacy_notes?`<div class="notice">Notes: ${esc(g.legacy_notes)}</div>`:''}
  </div>`;
}
async function prepareRecordings(title){
  const d=await api('/api/writer/poetry/recordings/prepare',{title});
  toast(d.message||'Done.',d.ok?'ok':'err');
}
async function openRecordings(title){
  const d=await api('/api/writer/poetry/recordings/open?title='+encodeURIComponent(title));
  toast(d.message||'Done.','ok');
}
async function saveLegacyFlags(title){
  for(const [field,id] of [['legacy','flagLegacy'],['for_akaysha','flagAkaysha'],['for_nevaeh','flagNevaeh']]){
    const value=q(id).checked;
    await api('/api/writer/poetry/legacy',{title,field,value});
  }
  toast('Legacy flags saved.','ok');loadArchive();
}

/* ============================ novel forge ============================ */
async function renderNovelForge(){
  const d=await api('/api/novelforge/list');
  S.novel.universes=(d&&d.universes)||[];
  q('nfDashboard').innerHTML=S.novel.universes.length
    ?`<div class="tablewrap"><table><tr><th>Universe</th><th>Characters</th><th>Locations</th><th>Artifacts</th><th>Timeline</th><th>Mysteries</th><th>Scenes</th><th>Modified</th><th></th></tr>
      ${S.novel.universes.map(u=>`<tr><td>${esc(u.universe)}</td><td>${u.characters}</td><td>${u.locations}</td><td>${u.artifacts}</td><td>${u.timeline}</td><td>${u.mysteries}</td><td>${u.scenes}</td><td>${esc(u.modified)}</td>
      <td><button class="btn" onclick="loadUniverse('${esc(u.name)}')">Load</button>
      <button class="btn" onclick="duplicateUniverse('${esc(u.name)}','${esc(u.universe)}')">Copy</button>
      <button class="btn" onclick="renameUniverse('${esc(u.name)}','${esc(u.universe)}')">Rename</button>
      <button class="btn danger" onclick="deleteUniverse('${esc(u.name)}','${esc(u.universe)}')">Delete</button></td></tr>`).join('')}
      </table></div><div class="small" style="margin-top:6px">Folder: ${esc(d.folder||'')}</div>`
    :'<div class="status">No universes yet. Give the forge a name and a premise below, then Save Universe.</div>';
  updateNovelCounts();
  renderCanon();
}
async function renderCanon(){
  const area=q('nfCanonList');
  if(!area)return;
  if(!S.novel.active){
    area.textContent='Load or save a universe first. No canon changes occur automatically.';
    return;
  }
  const d=await api('/api/novelforge/canon?name='+encodeURIComponent(S.novel.active));
  if(!d.ok){area.textContent=d.message||'Could not load canon.';return;}
  const facts=d.facts||[];
  if(!facts.length){
    area.textContent='No canon facts yet. Propose a fact with a source passage below.';
    return;
  }
  const counts=['proposed','approved','rejected']
    .map(state=>'<span class="chip">'+state+': '+facts.filter(f=>f.state===state).length+'</span>').join(' ');
  area.innerHTML=counts+facts.map(f=>{
    const evidence=(f.evidence||[]).map(e=>'<div class="small">'+esc(e.source)+': “'+esc(e.quote)+'”</div>').join('');
    const action=f.state==='proposed'
      ?'<div class="row"><button class="btn primary" onclick="reviewCanonFact(\''+f.id+'\',\'approved\')">Approve</button> '+
       '<button class="btn" onclick="reviewCanonFact(\''+f.id+'\',\'rejected\')">Reject</button></div>'
      :'';
    return '<div class="card" style="margin-top:10px"><strong>'+esc(f.kind)+': '+esc(f.subject)+'</strong> '+
      '<span class="chip">'+esc(f.state)+'</span><p>'+esc(f.claim)+'</p>'+
      (f.chapter?'<div class="small">Chapter: '+esc(f.chapter)+'</div>':'')+
      (f.world_time?'<div class="small">World time: '+esc(f.world_time)+'</div>':'')+
      evidence+action+'</div>';
  }).join('');
}
async function proposeCanonFact(){
  if(!S.novel.active){toast('Save or load a universe before proposing canon.','err');return;}
  const payload={
    universe:S.novel.active, kind:q('nfCanonKind').value,
    subject:q('nfCanonSubject').value,claim:q('nfCanonClaim').value,
    source:q('nfCanonSource').value,quote:q('nfCanonQuote').value,
    chapter:q('nfCanonChapter').value,world_time:q('nfCanonWorldTime').value,
    narrative_order:q('nfCanonNarrative').value,
  };
  const d=await api('/api/novelforge/canon/propose',payload);
  toast(d.message||(d.ok?'Fact proposed for review.':'Proposal rejected.'),d.ok?'ok':'err');
  if(d.ok){
    ['nfCanonSubject','nfCanonClaim','nfCanonSource','nfCanonQuote'].forEach(id=>q(id).value='');
    renderCanon();
  }
}
async function reviewCanonFact(factId,decision){
  if(!S.novel.active || !['approved','rejected'].includes(decision))return;
  if(!confirm((decision==='approved'?'Approve':'Reject')+' this proposed canon fact?'))return;
  const d=await api('/api/novelforge/canon/review',{
    universe:S.novel.active,fact_id:factId,decision});
  toast(d.message||(d.ok?'Fact '+decision+'.':'Review failed.'),d.ok?'ok':'err');
  if(d.ok)renderCanon();
}
function updateNovelCounts(){
  const cnt=list=>q(list).value.split('\n').filter(x=>x.trim()).length;
  q('nfCounts').innerHTML=['characters','locations','artifacts','timeline','mysteries','scenes']
    .map(k=>`<span class="chip">${k}: ${cnt('nf'+k.charAt(0).toUpperCase()+k.slice(1))}</span>`).join('');
}
async function loadUniverse(name){
  const d=await api('/api/novelforge/read?name='+encodeURIComponent(name));
  if(!d.ok){toast(d.message||'Universe not found.','err');return;}
  S.novel.active=d.file_name||name;
  q('nfUniverse').value=d.universe||'';
  q('nfPremise').value=d.premise||'';
  for(const k of ['characters','locations','artifacts','timeline','mysteries','scenes']){
    q('nf'+k.charAt(0).toUpperCase()+k.slice(1)).value=(d[k]||[]).join('\n');
  }
  q('nfNotes').value=d.notes||'';
  q('nfStatus').textContent=`Loaded universe: ${d.universe||name}`;
  updateNovelCounts();renderCanon();toast('Universe loaded.','ok');
}
async function saveUniverse(){
  const payload={
    universe:q('nfUniverse').value.trim()||'Untitled Universe',
    premise:q('nfPremise').value,
    characters:q('nfCharacters').value,locations:q('nfLocations').value,
    artifacts:q('nfArtifacts').value,timeline:q('nfTimeline').value,
    mysteries:q('nfMysteries').value,scenes:q('nfScenes').value,
    notes:q('nfNotes').value,
  };
  const d=await api('/api/novelforge/save',payload);
  if(d&&d.ok){S.novel.active=d.name;q('nfStatus').textContent=d.message;toast(d.message,'ok');renderNovelForge();}
  else toast((d&&d.message)||'Save failed.','err');
}
async function duplicateUniverse(name,title){
  const new_title=prompt('Duplicate universe as:',(title||name)+' Copy');
  if(!new_title)return;
  const d=await api('/api/novelforge/duplicate',{name,new_title});
  toast(d.message||'Done.',d.ok?'ok':'err');renderNovelForge();
}
async function renameUniverse(name,title){
  const new_title=prompt('Rename universe to:',title||name);
  if(!new_title)return;
  const d=await api('/api/novelforge/rename',{name,new_title});
  if(d.ok && S.novel.active===name)S.novel.active=d.name;
  toast(d.message||'Done.',d.ok?'ok':'err');renderNovelForge();
}
async function deleteUniverse(name,title){
  if(!confirm(`Delete the universe "${title||name}"? Its JSON and Markdown mirror are removed. Separate canon records are retained for recovery.`))return;
  const d=await api('/api/novelforge/delete',{name});
  if(d.ok && S.novel.active===name)S.novel.active=null;
  toast(d.message||'Done.',d.ok?'ok':'err');renderNovelForge();
}
/* codex card helpers: structured input -> list line */
function addCharacterCard(){
  const line=[q('nfCharName').value,q('nfCharRole').value,q('nfCharStatus').value]
    .filter(x=>x.trim()).join(' — ');
  const details=q('nfCharDetails').value.trim(),tags=q('nfCharTags').value.trim();
  if(!line){toast('Give the character at least a name.','err');return;}
  q('nfCharacters').value+=(q('nfCharacters').value?'\n':'')+line+(details?` | ${details}`:'')+(tags?` | tags: ${tags}`:'');
  q('nfCharName').value=q('nfCharRole').value=q('nfCharStatus').value=q('nfCharDetails').value=q('nfCharTags').value='';
  updateNovelCounts();toast('Character card appended to the Characters list.','ok');
}
function addLocationCard(){
  const line=[q('nfLocName').value,q('nfLocType').value].filter(x=>x.trim()).join(' — ');
  if(!line){toast('Give the location at least a name.','err');return;}
  const extra=['Characters: '+q('nfLocCharacters').value,'Description: '+q('nfLocDescription').value,
    'Secrets: '+q('nfLocSecrets').value,'Mysteries: '+q('nfLocMysteries').value]
    .filter(x=>x.split(': ')[1]&&x.split(': ')[1].trim()).join(' | ');
  q('nfLocations').value+=(q('nfLocations').value?'\n':'')+line+(extra?' | '+extra:'');
  ['nfLocName','nfLocType','nfLocCharacters','nfLocDescription','nfLocSecrets','nfLocMysteries'].forEach(i=>q(i).value='');
  updateNovelCounts();toast('Location card appended.','ok');
}
function addArtifactCard(){
  const line=[q('nfArtName').value,q('nfArtType').value].filter(x=>x.trim()).join(' — ');
  if(!line){toast('Give the artifact at least a name.','err');return;}
  const extra=['Characters: '+q('nfArtCharacters').value,'Function: '+q('nfArtFunction').value,
    'History: '+q('nfArtHistory').value,'Rules: '+q('nfArtRules').value,'Mysteries: '+q('nfArtMysteries').value]
    .filter(x=>x.split(': ')[1]&&x.split(': ')[1].trim()).join(' | ');
  q('nfArtifacts').value+=(q('nfArtifacts').value?'\n':'')+line+(extra?' | '+extra:'');
  ['nfArtName','nfArtType','nfArtCharacters','nfArtFunction','nfArtHistory','nfArtRules','nfArtMysteries'].forEach(i=>q(i).value='');
  updateNovelCounts();toast('Artifact card appended.','ok');
}
function addTimelineCard(){
  const line=[q('nfEventEra').value,q('nfEventTitle').value,q('nfEventDetails').value,q('nfEventTags').value]
    .filter(x=>x.trim()).join(' — ');
  if(!line){toast('Give the event at least a title.','err');return;}
  q('nfTimeline').value+=(q('nfTimeline').value?'\n':'')+line;
  ['nfEventEra','nfEventTitle','nfEventDetails','nfEventTags'].forEach(i=>q(i).value='');
  updateNovelCounts();toast('Timeline event appended.','ok');
}
function addMysteryCard(){
  const line=[q('nfMysteryTitle').value,q('nfMysteryStatus').value,q('nfMysteryDetails').value]
    .filter(x=>x.trim()).join(' — ');
  if(!line){toast('Give the mystery at least a title.','err');return;}
  q('nfMysteries').value+=(q('nfMysteries').value?'\n':'')+line;
  ['nfMysteryTitle','nfMysteryDetails'].forEach(i=>q(i).value='');
  updateNovelCounts();toast('Mystery appended.','ok');
}
function novelForgeContext(){
  const lists={};
  for(const k of ['characters','locations','artifacts','timeline','mysteries','scenes']){
    lists[k]=q('nf'+k.charAt(0).toUpperCase()+k.slice(1)).value.split('\n').filter(x=>x.trim());
  }
  return lists;
}
async function exportStoryBible(){
  const lists=novelForgeContext();
  const u=q('nfUniverse').value.trim()||'Untitled Universe';
  const bible=[
    `# ${u} — Story Bible (draft)`,``,`## Premise`,``,q('nfPremise').value||'(no premise yet)','',
    `## Characters`,'',...lists.characters.map(x=>'- '+x),'',
    `## Locations`,'',...lists.locations.map(x=>'- '+x),'',
    `## Artifacts`,'',...lists.artifacts.map(x=>'- '+x),'',
    `## Timeline`,'',...lists.timeline.map(x=>'- '+x),'',
    `## Mysteries / Unresolved Threads`,'',...lists.mysteries.map(x=>'- '+x),'',
    `## Notes`,'',q('nfNotes').value,'',
  ].join('\n');
  const payload={
    universe:u,
    summary:{characters:lists.characters.length,locations:lists.locations.length,
      artifacts:lists.artifacts.length,timeline:lists.timeline.length,
      mysteries:lists.mysteries.length,readiness:q('nfReadiness').value||'draft'},
    codex:lists,story_bible:bible,
  };
  const d=await api('/api/novelforge/export',payload);
  if(d&&d.ok){q('nfExportStatus').textContent=`${d.message}\nJSON: ${d.json}\nMarkdown: ${d.markdown}\nText: ${d.text}`;toast(d.message,'ok');}
  else toast((d&&d.message)||'Export failed.','err');
}

/* ============================ story forge ============================ */
async function loadProjects(){
  const d=await api('/api/writer/story/projects');
  S.projects=(d&&d.projects)||[];
  return S.projects;
}
function projectOptions(sel){
  return S.projects.map(p=>`<option value="${esc(p.project_id)}"${p.project_id===sel?' selected':''}>${esc(p.title)}</option>`).join('')
    ||'<option value="">— no projects yet —</option>';
}
async function renderStoryOverview(){
  await loadProjects();
  const d=await api('/api/writer/story/overview');
  q('storyOverviewStatus').innerHTML=d&&d.ok
    ?`<div class="kv">
       <span class="k">Projects</span><span>${d.summary.project_count} in ${esc(d.folders.projects_root)}</span>
      </div>
      <div class="grid" style="margin-top:10px">${(d.sections||[]).map(s=>`
        <div class="card"><h3>${esc(s.title)}</h3><div class="small">${esc(s.description)}</div></div>`).join('')}</div>
      <div class="notice">Safety contract: ${esc(Object.entries(d.safety||{}).map(([k,v])=>k+'='+v).join(' · '))}</div>`
    :`<div class="status err">${esc((d&&d.message)||'Overview failed.')}</div>`;
  renderStoryProjectPicker('storyChaptersProject');
}
async function renderStoryCreate(){
  const rows=q('storyBooks');
  if(!rows.children.length)addBookRow();
}
function addBookRow(){
  const div=document.createElement('div');div.className='card';div.style.marginTop='8px';
  div.innerHTML=`
    <div class="row"><div><label>Book title</label><input type="text" class="sb-title" placeholder="Book 1"></div></div>
    <label>Summary / seed outline</label><textarea class="sb-summary" placeholder="What happens in this book?"></textarea>`;
  q('storyBooks').appendChild(div);
}
async function storyCreateGate(execute){
  const books=[...q('storyBooks').children].map((el,i)=>({
    id:'book_'+(i+1),title:el.querySelector('.sb-title').value||('Book '+(i+1)),
    summary:el.querySelector('.sb-summary').value,
  }));
  const payload={title:q('storyCreateTitle').value,project_id:q('storyCreateId').value,
    author:q('storyCreateAuthor').value,books,
    approval_phrase:q('storyCreatePhrase').value,execute:!!execute};
  const d=await api(execute?'/api/writer/story/create_project_action':'/api/writer/story/create_project_gate',payload);
  q('storyCreateStatus').textContent=d.ok?JSON.stringify({message:d.message,blockers:d.blockers,summary:d.summary,
    written:d.written_files,created:d.created_dirs},null,2)
    :(d.message||'Gate failed.');
  q('storyCreateStatus').className='status '+(d.ok?'ok':'err');
  if(execute&&d.ok)loadProjects();
}
async function renderStoryChapters(){
  await loadProjects();
  renderStoryProjectPicker('storyChaptersProject');
}
function renderStoryProjectPicker(id){
  const el=q(id);if(el)el.innerHTML=projectOptions(S.story.project);
}
async function storyChaptersChanged(){
  S.story.project=q('storyChaptersProject').value;
  S.story.book=q('storyChaptersBook').value;
  const d=await api(`/api/writer/story/saved_chapter_dashboard?project_id=${encodeURIComponent(S.story.project)}&book_id=${encodeURIComponent(S.story.book)}`);
  q('storyChaptersSaved').innerHTML=d&&d.ok
    ?`<b>${esc(d.health_label)}</b> <span class="small">(${d.summary.chapter_cards_saved} cards, ${d.summary.markdown_cards_found} markdown files, ${d.summary.checks_passed}/${d.summary.checks_total} checks)</span>
      ${d.chapter_cards.map(c=>`<div class="chip">Ch ${c.chapter_number}: ${esc(c.title)}</div>`).join('')}`
    :(d&&d.message)||'No saved cards yet.';
}
function addChapterRow(){
  const div=document.createElement('div');div.className='card';div.style.marginTop='8px';
  div.innerHTML=`
    <div class="row">
      <div><label>Chapter #</label><input type="number" class="ch-num" style="width:90px"></div>
      <div><label>Title</label><input type="text" class="ch-title"></div>
      <div><label>POV</label><input type="text" class="ch-pov"></div>
      <div><label>Location</label><input type="text" class="ch-loc"></div>
    </div>
    <div class="row">
      <div><label>Goal</label><textarea class="ch-goal" style="min-height:64px"></textarea></div>
      <div><label>Conflict</label><textarea class="ch-conflict" style="min-height:64px"></textarea></div>
      <div><label>Reveal</label><textarea class="ch-reveal" style="min-height:64px"></textarea></div>
      <div><label>Ending hook</label><textarea class="ch-hook" style="min-height:64px"></textarea></div>
    </div>
    <label>Continuity notes (one per line)</label><textarea class="ch-notes" style="min-height:54px"></textarea>
    <label>Handoff tags (JSON, optional)</label><input type="text" class="ch-tags" placeholder='{"prophecy":"Book 1"}'>`;
  q('storyChapterCards').appendChild(div);
}
function collectChapterCards(){
  return [...q('storyChapterCards').children].map(el=>({
    chapter_number:el.querySelector('.ch-num').value,
    title:el.querySelector('.ch-title').value,
    pov:el.querySelector('.ch-pov').value,
    location:el.querySelector('.ch-loc').value,
    goal:el.querySelector('.ch-goal').value,
    conflict:el.querySelector('.ch-conflict').value,
    reveal:el.querySelector('.ch-reveal').value,
    hook:el.querySelector('.ch-hook').value,
    continuity_notes:el.querySelector('.ch-notes').value.split('\n').filter(x=>x.trim()),
    handoff_tags:(()=>{try{return JSON.parse(el.querySelector('.ch-tags').value||'{}');}catch(e){return{};}})(),
  }));
}
async function storyChaptersPlan(stage){
  const payload={project_id:q('storyChaptersProject').value,book_id:q('storyChaptersBook').value,
    chapter_cards:collectChapterCards(),approval_phrase:q('storyChaptersPhrase').value,
    execute:stage==='action'};
  const route=stage==='preview'?'/api/writer/story/chapter_planner_preview'
    :stage==='gate'?'/api/writer/story/chapter_save_gate':'/api/writer/story/chapter_save_action';
  const d=await api(route,payload);
  const box=stage==='preview'?q('storyChaptersPreview'):q('storyChaptersGate');
  box.textContent=d.ok?JSON.stringify({message:d.message,summary:d.summary,
    blockers:d.blockers,overwrite_risks:d.overwrite_risks,
    preflight:(d.preflight||[]).map(p=>({id:p.id,exists:p.exists,would_overwrite:p.would_overwrite}))},null,2)
    :(d.message||'Failed.');
  box.className='status '+(d.ok?'ok':'err');
}
async function renderStoryEditor(){
  await loadProjects();
  q('storyEditorProject').innerHTML=projectOptions(S.story.project);
  storyEditorListFiles();
}
async function storyEditorListFiles(){
  const d=await api(`/api/writer/story/dashboard?project_id=${encodeURIComponent(q('storyEditorProject').value)}`);
  const files=(d&&d.ok&&d.structure&&d.structure.Chapters&&d.structure.Chapters.files)||[];
  q('storyEditorFile').innerHTML=files.map(f=>`<option>${esc(f)}</option>`).join('')
    ||'<option value="">— no chapter files —</option>';
}
async function storyEditorLoad(){
  const d=await api(`/api/writer/story/chapter_editor_preview?project_id=${encodeURIComponent(q('storyEditorProject').value)}&filename=${encodeURIComponent(q('storyEditorFile').value)}`);
  if(!d.ok){toast(d.message||'Not found.','err');return;}
  q('storyEditorOriginal').value=d.content;
  q('storyEditorContent').value=d.content;
  q('storyEditorInfo').textContent=`${d.filename} · ${d.word_count} words · sha ${String(d.content_sha256).slice(0,12)}… · modified ${d.modified}`;
}
async function storyEditorCompare(){
  const payload={project_id:q('storyEditorProject').value,filename:q('storyEditorFile').value,
    edited_content:q('storyEditorContent').value};
  const gate=await api('/api/writer/story/chapter_edit_gate',payload);
  q('storyEditorStatus').textContent=gate.ok
    ?JSON.stringify({gate_ready:gate.gate_ready,diff_metrics:gate.diff_metrics,blockers:gate.blockers,
      phrase_required:gate.approval_phrase_required},null,2)
    :(gate.message||'Gate failed.');
  q('storyEditorStatus').className='status '+(gate.ok?'ok':'err');
  return gate;
}
async function storyEditorApply(){
  const payload={project_id:q('storyEditorProject').value,filename:q('storyEditorFile').value,
    edited_content:q('storyEditorContent').value,
    approval_phrase:q('storyEditorPhrase').value,execute:true};
  const d=await api('/api/writer/story/chapter_edit_action',payload);
  q('storyEditorStatus').textContent=d.ok?JSON.stringify({message:d.message,backup:d.backup,diff_metrics:d.diff_metrics},null,2)
    :(d.message||'Edit failed.');
  q('storyEditorStatus').className='status '+(d.ok?'ok':'err');
  if(d.ok)storyEditorLoad();
}
async function renderStoryDrafts(){
  await loadProjects();
  q('storyDraftsProject').innerHTML=projectOptions(S.story.project);
  storyDraftsRefresh();
}
async function storyDraftsRefresh(){
  const d=await api(`/api/writer/story/draft_workspace?project_id=${encodeURIComponent(q('storyDraftsProject').value)}&book_id=${encodeURIComponent(q('storyDraftsBook').value)}&chapter=${encodeURIComponent(q('storyDraftsChapter').value)}`);
  if(d&&d.ok){
    const vs=d.versions||[];
    q('storyDraftsInfo').textContent=`${vs.length} version(s) saved for this chapter.`;
    const opts=vs.map(v=>`<option>${esc(v.filename)}</option>`).join('');
    q('storyDraftsLeft').innerHTML=opts;q('storyDraftsRight').innerHTML=opts;
  }
  const h=await api(`/api/writer/story/draft_version_history?project_id=${encodeURIComponent(q('storyDraftsProject').value)}&book_id=${encodeURIComponent(q('storyDraftsBook').value)}&chapter=${encodeURIComponent(q('storyDraftsChapter').value)}`);
  if(h&&h.ok){
    q('storyDraftsHistory').innerHTML=(h.versions||[]).length
      ?`<div class="tablewrap"><table><tr><th>Version</th><th>File</th><th>Words</th><th>Created</th><th>Model</th></tr>
        ${h.versions.map(v=>`<tr><td>v${String(v.version).padStart(3,'0')}</td><td>${esc(v.filename)}</td><td>${v.word_count}</td><td>${esc(v.created)}</td><td>${esc(v.model||'')}</td></tr>`).join('')}
        </table></div>`
      :'<div class="status">No draft versions yet.</div>';
  }
}
async function storyDraftsSave(stage){
  const payload={project_id:q('storyDraftsProject').value,book_id:q('storyDraftsBook').value,
    chapter:q('storyDraftsChapter').value||'Untitled Chapter',
    content:q('storyDraftsContent').value,execute:stage==='action'};
  const d=await api(stage==='action'?'/api/writer/story/draft_save_action':'/api/writer/story/draft_save_gate',payload);
  q('storyDraftsStatus').textContent=d.ok?JSON.stringify({message:d.message,next_version:d.next_version,
    growth_check:d.growth_check,word_count:d.word_count},null,2):(d.message||'Failed.');
  q('storyDraftsStatus').className='status '+(d.ok?'ok':'err');
  if(stage==='action'&&d.ok)storyDraftsRefresh();
}
async function storyDraftsContinue(stage){
  const payload={project_id:q('storyDraftsProject').value,book_id:q('storyDraftsBook').value,
    chapter:q('storyDraftsChapter').value,content:q('storyDraftsContent').value,execute:stage==='action'};
  const d=await api(stage==='action'?'/api/writer/story/draft_continue_action':'/api/writer/story/draft_continue_gate',payload);
  q('storyDraftsStatus').textContent=d.ok?JSON.stringify({message:d.message||'Gate ready.',growth_check:d.growth_check,
    base_version:d.base_version},null,2):(d.message||'Failed.');
  q('storyDraftsStatus').className='status '+(d.ok?'ok':'err');
  if(stage==='action'&&d.ok)storyDraftsRefresh();
}
async function storyDraftsCompare(){
  const d=await api('/api/writer/story/draft_compare',{project_id:q('storyDraftsProject').value,
    book_id:q('storyDraftsBook').value,left_filename:q('storyDraftsLeft').value,
    right_filename:q('storyDraftsRight').value});
  q('storyDraftsCompare').textContent=d.ok
    ?JSON.stringify({left:d.left_words,right:d.right_words,diff_metrics:d.diff_metrics,
      diff_preview:d.unified_diff_preview},null,2)
    :(d.message||'Compare failed.');
}
async function renderStoryProse(){
  await loadProjects();
  q('storyProseProject').innerHTML=projectOptions(S.story.project);
  storyProseRefresh();
}
async function storyProseRefresh(){
  const d=await api(`/api/writer/story/prose_status?project_id=${encodeURIComponent(q('storyProseProject').value)}`);
  const files=(d&&d.ok&&d.versions)||[];
  q('storyProseFile').innerHTML=files.map(v=>`<option>${esc(v.filename)}</option>`).join('')
    ||'<option value="">— no prose versions —</option>';
  q('storyProseInfo').textContent=files.length
    ?files.map(v=>`${v.filename}: ${v.word_count} words (${v.modified})`).join('\n')
    :'No prose versions yet.';
}
async function storyProseSave(){
  const d=await api('/api/writer/story/prose_draft_save',{project_id:q('storyProseProject').value,
    label:q('storyProseLabel').value||'manuscript',content:q('storyProseContent').value});
  toast(d.message||'Failed.',d.ok?'ok':'err');
  if(d.ok)storyProseRefresh();
}
async function storyProseLoad(){
  const d=await api(`/api/writer/story/prose_editor_preview?project_id=${encodeURIComponent(q('storyProseProject').value)}&filename=${encodeURIComponent(q('storyProseFile').value)}`);
  if(!d.ok){toast(d.message||'Not found.','err');return;}
  q('storyProseEditor').value=d.content;
  q('storyProseEditInfo').textContent=`${d.filename} · ${d.word_count} words · sha ${String(d.content_sha256).slice(0,12)}…`;
}
async function storyProseCompare(){
  const d=await api('/api/writer/story/prose_refresh_compare',{project_id:q('storyProseProject').value,
    filename:q('storyProseFile').value,edited_content:q('storyProseEditor').value});
  q('storyProseEditStatus').textContent=d.ok
    ?JSON.stringify({identical:d.identical,diff_metrics:d.diff_metrics,diff_preview:d.unified_diff_preview},null,2)
    :(d.message||'Compare failed.');
}
async function storyProseEditApply(){
  const d=await api('/api/writer/story/prose_edit_save',{project_id:q('storyProseProject').value,
    filename:q('storyProseFile').value,edited_content:q('storyProseEditor').value,
    approval_phrase:q('storyProsePhrase').value,execute:true});
  q('storyProseEditStatus').textContent=d.ok?JSON.stringify({message:d.message,backup:d.backup,
    diff_metrics:d.diff_metrics},null,2):(d.message||'Edit failed.');
  if(d.ok)storyProseRefresh();
}

/* ============================ weaver ============================ */
const WEAVER_FORMAT_HELP={
  poem:'Poem output preserves intentional line and stanza breaks.',
  short_story:'Short-story output is prose paragraphs with an earned ending.',
  clean_prose:'Clean prose keeps deliberate paragraph and scene breaks.',
  twine:'Twine output returns :: Start plus named passages with optional [[Choice->Passage]] links.',
};
function buildWeaverSources(){
  const grid=q('weaverSources');
  if(grid.children.length)return;
  for(let i=1;i<=4;i++){
    const card=document.createElement('div');card.className='card';
    card.innerHTML=`<h3>Source ${i}${i>2?' (optional)':''}</h3>
      <label>Source title</label><input id="weaverSourceName${i}" type="text" placeholder="Poem or story title">
      <label>Paste the source text</label><textarea id="weaverSourceText${i}" placeholder="${i<3?'Paste source '+i+' here…':'Paste an optional source here…'}"></textarea>`;
    grid.appendChild(card);
  }
}
function updateWeaverFormatHelp(){
  q('weaverFormatHelp').textContent=WEAVER_FORMAT_HELP[q('weaverOutputType').value]||'';
}
async function renderWeaver(){
  await loadVoices();
  q('weaverVoice').innerHTML=voiceOptions(true);
  buildWeaverSources();
}
async function weaverGenerate(){
  const sources=[1,2,3,4].map(i=>({
    title:q('weaverSourceName'+i).value,content:q('weaverSourceText'+i).value,
  }));
  const payload={sources,mode:q('weaverMode').value,output_type:q('weaverOutputType').value,
    voice:q('weaverVoice').value,length:q('weaverLength').value,direction:q('weaverDirection').value};
  const btn=q('weaverGenerateButton');btn.disabled=true;
  q('weaverStatus').textContent='Planning and weaving…';
  const d=await api('/api/writer/weaver/generate',payload);
  btn.disabled=false;
  if(!d.ok){q('weaverStatus').textContent=d.message||'Weaver failed.';toast(d.message||'Weaver failed.','err');return;}
  S.weaver.last=d;
  q('weaverTitle').value=d.title||'';
  q('weaverOutput').value=d.output||'';
  q('weaverSourceMap').textContent=JSON.stringify(d.source_map,null,2);
  q('weaverWarnings').textContent=(d.warnings&&d.warnings.length?d.warnings.join('\n'):'No copy-similarity warnings.')
    +`\n\nCopy metrics: ${JSON.stringify(d.copy_metrics)}`;
  q('weaverStatus').textContent=`${d.message} (${d.word_count} words, ${d.attempts} attempt(s), ${d.output_type_label})`;
  toast(d.message,'ok');
}
async function weaverSave(){
  const d=S.weaver.last;
  const res=await api('/api/writer/weaver/save',{output:q('weaverOutput').value,
    output_type:q('weaverOutputType').value,title:q('weaverTitle').value,
    mode:q('weaverMode').value,voice:q('weaverVoice').value,length:q('weaverLength').value,
    direction:q('weaverDirection').value,provenance:d&&d.provenance||{}});
  toast(res.message||'Failed.',res.ok?'ok':'err');
}

/* ============================ settings ============================ */
async function renderSettings(){
  const d=await api('/api/config');
  S.config=d&&d.config||null;
  if(S.config){
    const m=S.config.model||{};
    q('cfgBaseUrl').value=m.base_url||'';
    q('cfgModel').value=m.model||'';
    q('cfgChatPath').value=m.chat_path||'';
    q('cfgHealthPath').value=m.health_path||'';
    q('cfgHealthKind').value=m.health_kind||'auto';
    q('cfgTimeout').value=m.timeout_seconds||420;
    q('cfgApiKey').placeholder=m.api_key_set?'API key is set (leave blank to keep)':'API key (optional)';
    q('cfgCraftUrl').value=(S.config.integrations&&S.config.integrations.craft_suite_url)||'';
    q('cfgServerInfo').innerHTML=`<div class="kv">
      <span class="k">LAN address</span><span>${esc(m.api_key_set?'':'')}${esc(S.config.server.host)}:${S.config.server.port}</span>
      <span class="k">Data folder</span><span>${esc((S.config._resolved&&S.config._resolved.data_dir)||'')}</span>
      <span class="k">Config file</span><span>${esc('config.json next to kayock_writer.py')}</span>
      <span class="k">Approval phrase required</span><span>${S.config.writing&&S.config.writing.require_approval_phrase?'yes':'no'}</span>
    </div>`;
  }
  const vs=await api('/api/voice/pack/status');
  q('cfgVoicePack').innerHTML=vs&&vs.loaded
    ?`<span class="chip gold">Private Eric pack active — ${vs.source_count} source poem(s) available as read-only style references.</span>`
    :'<span class="chip">Private Eric pack not installed — the Eric — Poet/Narrator profile uses derived style settings only.</span>';
}
async function saveModelConfig(){
  const payload={base_url:q('cfgBaseUrl').value,model:q('cfgModel').value,
    chat_path:q('cfgChatPath').value,health_path:q('cfgHealthPath').value,
    health_kind:q('cfgHealthKind').value,timeout_seconds:Number(q('cfgTimeout').value)||420};
  const key=q('cfgApiKey').value.trim();
  if(key)payload.api_key=key;
  const d=await api('/api/config/model',payload);
  toast(d.message||'Failed.',d.ok?'ok':'err');
  renderHome();
}
async function testModelConfig(){
  q('cfgTestStatus').textContent='Probing endpoint…';
  const d=await api('/api/config/model/test',{});
  q('cfgTestStatus').textContent=JSON.stringify(d,null,2);
  q('cfgTestStatus').className='status '+(d.ok?'ok':'err');
  renderHome();
}

/* ============================ optional finishing desk ============================ */
function renderFinishing(){} // keep unsaved editing text when moving between rooms
function finishingImport(source){
  const ids={
    'studio':'poemResult', 'polisher':'poemPolisherInput', 'polished':'poemPolishedResult',
    'story-draft':'storyDraftsContent', 'story-prose':'storyProseContent',
    'story-edited':'storyProseEditor', 'weaver':'weaverOutput'
  };
  const id=ids[source];const element=id?q(id):null;
  if(!element || !element.value.trim()){
    toast('No text in that work area. Choose a different source or paste your draft.','err');return;
  }
  q('finishText').value=element.value;
  q('finishType').value=(source==='studio'||source==='polisher'||source==='polished')
    ? (q('studioType').value==='short_story'?'short_story':'poem')
    : (source==='weaver'&&q('weaverOutputType').value==='poem'?'poem':'prose');
  if(source==='studio') q('finishTitle').value=q('poemResultTitle').value||'';
  if(source==='weaver')q('finishTitle').value=q('weaverTitle').value||'';
  toast('Copied from the work area. Your original draft was not changed.','ok');
}
let editorialGeneration=null;
let editorialBusy=false;
function editorialPayload(){
  return {text:q('finishText').value,mode:q('finishMode').value,
    title:q('finishTitle').value,writing_type:q('finishType').value,
    direction:q('finishDirection').value};
}
async function finishingReview(){
  if(editorialBusy)return;
  const payload=editorialPayload();
  if(!payload.text.trim()){toast('Paste or import a passage first.','err');return;}
  editorialBusy=true;editorialGeneration=null;
  q('finishStop').disabled=true;
  q('finishResult').value='';
  q('finishStatus').textContent='Connecting to the configured model stream…';
  q('finishStatus').className='status';
  let terminal=false;
  try{
    const response=await fetch('/api/writer/editorial/stream',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(!response.ok){
      let err;try{err=await response.json();}catch(e){}
      throw new Error(err&&err.message||'HTTP '+response.status);
    }
    if(!response.body)throw new Error('This browser does not support streamed responses.');
    const reader=response.body.getReader();
    const decoder=new TextDecoder();
    let buffer='';
    function handleFrame(frame){
      let event='';
      const data=[];
      for(const line of frame.split(/\r?\n/)){
        if(line.startsWith('event:'))event=line.slice(6).trim();
        if(line.startsWith('data:'))data.push(line.slice(5).replace(/^ /,''));
      }
      if(!event||!data.length)return;
      let item;
      try{item=JSON.parse(data.join('\n'));}catch(e){throw new Error('Invalid stream event from server.');}
      if(event==='start'){
        editorialGeneration=item.generation_id;
        q('finishStop').disabled=false;
        q('finishStatus').textContent='Generating live review…';
      }else if(event==='token'){
        q('finishResult').value+=item.text||'';
        q('finishResult').scrollTop=q('finishResult').scrollHeight;
      }else if(event==='done'){
        terminal=true;
        q('finishStatus').textContent='Review complete. Original text unchanged.';
        q('finishStatus').className='status ok';
      }else if(event==='cancelled'){
        terminal=true;
        q('finishStatus').textContent='Stopped. Partial response is unsaved; original text unchanged.';
        q('finishStatus').className='status';
      }else if(event==='error'){
        terminal=true;
        q('finishStatus').textContent=item.message||'Streaming failed.';
        q('finishStatus').className='status err';
      }
    }
    while(true){
      const next=await reader.read();
      if(next.done)break;
      buffer+=decoder.decode(next.value,{stream:true});
      let match;
      while((match=buffer.match(/\r?\n\r?\n/))){
        const frame=buffer.slice(0,match.index);
        buffer=buffer.slice(match.index+match[0].length);
        handleFrame(frame);
      }
    }
    if(!terminal)throw new Error('Stream closed before completion; partial text is unsaved.');
  }catch(e){
    q('finishStatus').textContent=(e&&e.message||String(e))+' Try Classic review if streaming is unsupported.';
    q('finishStatus').className='status err';
  }finally{
    editorialBusy=false;editorialGeneration=null;q('finishStop').disabled=true;
  }
}
async function finishingCancel(){
  if(!editorialGeneration)return;
  q('finishStop').disabled=true;
  q('finishStatus').textContent='Stopping model generation…';
  const result=await api('/api/generation/'+encodeURIComponent(editorialGeneration)+'/cancel',{});
  if(!result.ok)q('finishStatus').textContent=result.message||'Could not stop generation.';
}
async function finishingReviewClassic(){
  if(editorialBusy)return;
  const payload=editorialPayload();
  if(!payload.text.trim()){toast('Paste or import a passage first.','err');return;}
  editorialBusy=true;
  q('finishStatus').textContent='Asking configured model (classic response)…';
  try{
    const d=await api('/api/writer/editorial/review',payload);
    q('finishStatus').textContent=d.message||'No result.';
    q('finishStatus').className='status '+(d.ok?'ok':'err');
    if(d.ok){q('finishResult').value=d.text||'';
      q('finishStatus').textContent+=' Original text remains untouched.';}
  }finally{editorialBusy=false;}
}
function finishingExport(format){
  const text=q('finishText').value;
  if(!text.trim()){toast('Add a passage to export.','err');return;}
  const title=(q('finishTitle').value.trim()||'Untitled');
  const kind=q('finishType').value;
  const safe=(title.normalize('NFKC').replace(/[^a-zA-Z0-9_-]+/g,'_').slice(0,80)||'Kayock_Writing');
  const body=String(text).replace(/\r\n/g,'\n');
  let content,mime,ext;
  if(format==='html'){
    const blocks=body.split(/\n\s*\n/);
    const rendered=blocks.map(p=>{
      const escaped=esc(p);
      return kind==='poem'?'<div class="stanza">'+escaped.replace(/\n/g,'<br>')+'</div>'
        :'<p>'+escaped.replace(/\n/g,'<br>')+'</p>';
    }).join('\n');
    content='<!doctype html><html lang="en"><head><meta charset="utf-8">'+
      '<meta name="viewport" content="width=device-width,initial-scale=1">'+
      '<title>'+esc(title)+'</title><style>body{font:17px/1.7 Georgia,serif;'+
      'max-width:780px;margin:55px auto;padding:0 24px;color:#202020}'+
      'h1{font-size:1.8em}.stanza{margin:0 0 1.4em;white-space:normal}'+
      'p{margin:0 0 1.2em}@media print{body{margin:0;max-width:none}}'+
      '</style></head><body><h1>'+esc(title)+'</h1>'+rendered+'</body></html>';
    mime='text/html;charset=utf-8';ext='html';
  }else if(format==='md'){
    content='# '+title.replace(/\r?\n/g,' ')+'\n\n'+body;
    mime='text/markdown;charset=utf-8';ext='md';
  }else{
    content=title+'\n\n'+body;mime='text/plain;charset=utf-8';ext='txt';
  }
  const blob=new Blob([content],{type:mime});const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download=safe+'.'+ext;
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast('File downloaded locally; no Craft Suite API call was made.','ok');
}
async function finishingOpenCraft(){
  const d=await api('/api/config');
  const url=d.config&&d.config.integrations&&d.config.integrations.craft_suite_url;
  if(!url){toast('Configure the Craft Suite URL in Settings first.','err');return;}
  try{
    const parsed=new URL(url);
    if(!['http:','https:'].includes(parsed.protocol))throw new Error('invalid scheme');
    window.open(parsed.href,'_blank','noopener,noreferrer');
    toast('Craft Suite opened in a separate tab. Import your exported document there.','ok');
  }catch(e){toast('Invalid Craft Suite URL. Check Settings.','err');}
}
async function saveCraftConfig(){
  const d=await api('/api/config/craft_suite',{craft_suite_url:q('cfgCraftUrl').value});
  toast(d.message||'Failed.',d.ok?'ok':'err');
}

/* ============================ boot ============================ */
window.addEventListener('DOMContentLoaded',()=>{
  show('home');renderHome();setInterval(async()=>{
    const st=await api('/api/status');const dot=q('modelDot');
    dot.className=(st&&st.model&&st.model.online)?'online':'offline';
    q('modelLabel').textContent=(st&&st.model&&st.model.online)?'model online':'model offline';
  },20000);
  api('/api/status').then(st=>{const dot=q('modelDot');
    dot.className=(st&&st.model&&st.model.online)?'online':'offline';
    q('modelLabel').textContent=(st&&st.model&&st.model.online)?'model online':'model offline';});
});
"""

_HTML = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kayock Writer</title>
<style>__CSS__</style>
</head><body>
<header id="appbar">
  <button id="burger" onclick="openTree()">☰ Menu</button>
  <span class="brand">Kayock Writer <small>— Novel Forge · Poetry Forge · Short Story Forge</small></span>
  <span style="flex:1"></span>
  <span class="status"><span id="modelDot"></span><span id="modelLabel">checking model…</span></span>
</header>
<div id="layout">
<nav id="tree">
  <button class="nav active" data-page="home" onclick="show('home')">Writer Home</button>

  <div class="group">Poetry Forge</div>
  <div class="sub">
    <button class="nav" data-page="studio" data-navkey="studio-poem-create" onclick="setStudio('poem','create','studio-poem-create')">Poem Creator</button>
    <button class="nav" data-page="studio" data-navkey="studio-poem-polish" onclick="setStudio('poem','polish','studio-poem-polish')">Poem Polisher</button>
    <button class="nav" data-page="studio" data-navkey="studio-poem-selection" onclick="setStudio('poem','polish','studio-poem-selection');setTimeout(captureSelection,80)">Selection Workshop</button>
    <button class="nav" data-page="archive" data-navkey="archive-poem" onclick="S.uiKey='archive-poem';show('archive')">Poem Archive</button>
  </div>

  <div class="group">Short Story Forge</div>
  <div class="sub">
    <button class="nav" data-page="studio" data-navkey="studio-story-create" onclick="setStudio('short_story','create','studio-story-create')">Story Creator</button>
    <button class="nav" data-page="studio" data-navkey="studio-story-polish" onclick="setStudio('short_story','polish','studio-story-polish')">Story Polisher</button>
    <button class="nav" data-page="archive" data-navkey="archive-story" onclick="S.uiKey='archive-story';q('archiveFilter').value='short_story';show('archive')">Story Archive</button>
  </div>

  <div class="group">Novel Forge</div>
  <div class="sub">
    <button class="nav" data-page="novelforge" onclick="show('novelforge')">Universes &amp; Codex</button>
    <button class="nav" data-page="novelforge" onclick="show('novelforge');setTimeout(()=>q('nfExportStatus').scrollIntoView({behavior:'smooth'}),120)">Story Bible Export</button>
  </div>

  <div class="group">Story Forge</div>
  <div class="sub">
    <button class="nav" data-page="storyoverview" onclick="show('storyoverview')">Overview</button>
    <button class="nav" data-page="storycreate" onclick="show('storycreate')">Create Project</button>
    <button class="nav" data-page="storychapters" onclick="show('storychapters')">Chapter Planner &amp; Cards</button>
    <button class="nav" data-page="storyeditor" onclick="show('storyeditor')">Chapter Editor</button>
    <button class="nav" data-page="storydrafts" onclick="show('storydrafts')">Draft Workspace</button>
    <button class="nav" data-page="storyprose" onclick="show('storyprose')">Prose Workspace</button>
  </div>

  <div class="group">Shared Library</div>
  <div class="sub">
    <button class="nav" data-page="weaver" onclick="show('weaver')">The Weaver</button>
    <button class="nav" data-page="mywriting" onclick="show('mywriting')">My Writing</button>
    <button class="nav" data-page="finishing" onclick="show('finishing')">Editorial &amp; Craft Handoff</button>
  </div>

  <div class="group">System</div>
  <div class="sub">
    <button class="nav" data-page="settings" onclick="show('settings')">Settings</button>
  </div>
  <div class="navtree-note">Opening a room never changes your saved work.</div>
</nav>
<main>

<!-- ============ HOME ============ -->
<section class="page active" id="pg-home">
  <div class="hero"><h1>Writer Home</h1>
  <p>What would you like to work on? Opening a room never changes your saved work.</p></div>
  <div class="card wide"><h3>Studio status</h3><div id="homeStatus" class="status">Loading…</div></div>
  <div class="grid">
    <div class="card"><h3>Poetry Forge</h3>
      <p class="small">Create and polish poems with the Eric — Poet/Narrator fingerprint, Edgar Allan Poe — Gothic Lyric, and the full voice pack.</p>
      <button class="btn primary" onclick="setStudio('poem','create')">Create a Poem</button>
      <button class="btn" onclick="setStudio('poem','polish')">Polish a Poem</button>
      <button class="btn" onclick="show('archive')">Browse the Poem Archive</button></div>
    <div class="card"><h3>Short Story Forge</h3>
      <p class="small">Short fiction with the Eric — Short Fiction fingerprint plus public-domain archetypes: Robin Hood, Zorro, Dracula, Sherlock Holmes.</p>
      <button class="btn primary" onclick="setStudio('short_story','create')">Start a Story</button>
      <button class="btn" onclick="setStudio('short_story','polish')">Polish a Story</button>
      <button class="btn" onclick="show('archive')">Browse Story Archive</button></div>
    <div class="card"><h3>Novel Forge</h3>
      <p class="small">Universes, story bibles, characters, locations, artifacts, timelines, and mysteries.</p>
      <button class="btn primary" onclick="show('novelforge')">Open Novel Forge</button></div>
    <div class="card"><h3>Story Forge</h3>
      <p class="small">Approval-gated story projects: chapter cards, continuity handoffs, versioned drafts, and prose.</p>
      <button class="btn primary" onclick="show('storyoverview')">Open Story Forge</button></div>
    <div class="card"><h3>The Weaver</h3>
      <p class="small">Weave two to four sources into one new poem, story, clean prose, or Twine piece.</p>
      <button class="btn primary" onclick="show('weaver')">Open The Weaver</button></div>
    <div class="card"><h3>My Writing</h3>
      <p class="small">Every saved poem, story, and version — grouped, searchable, and read-only.</p>
      <button class="btn primary" onclick="show('mywriting')">Browse My Writing</button></div>
  </div>
</section>

<!-- ============ STUDIO (creator + polisher + selection workshop) ============ -->
<section class="page" id="pg-studio">
  <div class="hero"><h1 id="studioTitle">Poetry Forge</h1><p id="studioHero"></p></div>
  <div class="row">
    <div><label>Writing type</label>
      <select id="studioType" onchange="updateCraftControls()">
        <option value="poem">Poem</option>
        <option value="short_story">Short story</option>
      </select></div>
  </div>
  <div id="studioCreate">
    <div class="card wide" style="margin-top:10px"><h3>Guided creation</h3>
      <div class="row">
        <div><label>Theme</label><input id="poemTheme" type="text" placeholder="memory, eternity, grief, wonder, home"></div>
        <div><label>Emotion</label><input id="poemEmotion" type="text" placeholder="haunted, hopeful, tender, furious, quietly joyful"></div>
        <div><label>Audience</label><input id="poemAudience" type="text" placeholder="For myself; for Akaysha; for anyone who has felt this"></div>
      </div>
      <label>Scene or imagery</label>
      <textarea id="poemImagery" placeholder="A porch light in falling snow; an empty city after midnight…"></textarea>
      <div class="row">
        <div><label>Speaker / narrator voice</label><input id="poemSpeaker" type="text" placeholder="Me now; my younger self; an unnamed traveler"></div>
        <div><label>Length</label>
          <select id="poemLength"><option>Short</option><option selected>Medium</option><option>Long</option></select></div>
      </div>
      <label>Personal memory or truth the writing must protect</label>
      <textarea id="poemMemory" placeholder="A real detail, moment, promise, place, or feeling the writing should protect"></textarea>
      <label>Canon or established details that must remain true</label>
      <textarea id="poemCanon" placeholder="Names, facts, world details, promises, or continuity that must remain true"></textarea>
      <div class="row">
        <div><label>Opening line (used exactly)</label><input id="poemOpening" type="text"></div>
        <div class="fixed"><label style="margin-top:26px"><input type="checkbox" id="poemVariation"> Request a different variation</label></div>
      </div>
    </div>
    <div class="card wide"><h3>Voice</h3>
      <div class="row">
        <div><label>Creative voice</label><select id="poemVoice" onchange="updateVoiceControls()"></select></div>
        <div><label>Voice strength</label><select id="poemVoiceStrength"></select></div>
      </div>
      <div id="voiceProfileControls" style="display:none;margin-top:8px">
        <div id="voiceProfileHead"></div>
        <div id="voiceProfileSources" style="margin:6px 0"></div>
        <div id="voiceProfileBadges"></div>
      </div>
    </div>
    <div class="card wide" id="poemOnlyCraftControls"><h3>Craft (poem mode)</h3>
      <div class="row">
        <div><label>Poetic form</label><select id="poemForm">
          <option>Free verse</option><option>Rhymed</option><option>Sonnet</option><option>Haiku</option><option>Spoken word</option></select></div>
        <div><label>Rhyme preference</label><select id="poemRhymePreference">
          <option>Natural — let the poem decide</option><option>No required rhyme</option>
          <option>Couplets — AABB</option><option>Alternating — ABAB</option>
          <option>Monorhyme — AAAA</option><option>Internal and slant rhyme</option></select></div>
        <div><label>Rhythm preference</label><select id="poemRhythmPreference">
          <option>Natural spoken cadence</option><option>Steady lyrical pulse</option>
          <option>Loose conversational rhythm</option><option>Performance / spoken-word cadence</option>
          <option>Formal meter where possible</option></select></div>
      </div>
      <div class="small" id="rhymeTargetPreview" style="margin-top:6px"></div>
    </div>
    <div class="card wide" id="storyLengthControl" style="display:none"><h3>Story length</h3>
      <p class="small">Short ≈ 300–600 words · Medium ≈ 700–1,200 · Long ≈ 1,300–2,000. Prose rhythm and paragraphing are handled automatically.</p>
    </div>
    <div class="card wide">
      <button class="btn primary" id="createButton" onclick="studioCreate()">Create</button>
      <span id="creatorStatus" class="status" style="display:inline-block;max-width:70%">Ready.</span>
      <label>Result</label>
      <div class="row"><div><input id="poemResultTitle" type="text" placeholder="Suggested title (editable)"></div>
      <div class="fixed"><button class="btn" onclick="studioSaveDraft('draft')">Save draft</button>
      <button class="btn" onclick="studioSaveDraft('original')">Save original</button></div></div>
      <textarea id="poemResult" class="big" placeholder="The finished work will appear here…"></textarea>
    </div>
  </div>

  <div id="studioPolish" style="display:none">
    <div class="card wide" style="margin-top:10px"><h3>Polisher</h3>
      <div class="row">
        <div><label>Polish focus</label><select id="poemPolishFocus">
          <option>Balanced polish</option><option>Light touch</option><option>Bold rewrite</option>
          <option>Preserve voice with minimal changes</option>
          <option>Light cleanup</option><option>Pacing and scene flow</option>
          <option>Dialogue and character voice</option><option>Imagery and atmosphere</option>
          <option>Emotional impact</option><option>Clarity and word choice</option>
          <option>Deep polish — preserve story</option></select></div>
        <div><label>Title</label><input id="poemPolisherTitle" type="text" placeholder="Untitled"></div>
      </div>
      <label>Poem or story to polish</label>
      <textarea id="poemPolisherInput" class="big" placeholder="Send a work here from the creator, or paste one."></textarea>
      <button class="btn primary" id="polishButton" onclick="studioPolish()">Polish</button>
      <span id="poemPolishStatus" class="status" style="display:inline-block;max-width:70%">Ready.</span>
      <label>Polished version</label>
      <textarea id="poemPolishedResult" class="big" placeholder="The finished polished version will appear here."></textarea>
      <button class="btn" onclick="polishKeepOriginal()">Keep original</button>
      <button class="btn" onclick="polishUsePolished()">Use polished version</button>
      <button class="btn primary" onclick="polishSaveBoth()">Save original + polished</button>
    </div>
    <div class="card wide"><h3>Selected Lines &amp; Stanza Workshop</h3>
      <p class="small">Select lines inside the work area above, capture them, and create exactly three replacement passages. The rest of the work is never touched.</p>
      <div class="row">
        <div><label>Workshop focus</label><select id="poemSelectionFocus">
          <option>Keep meaning, improve the lines</option><option>Stronger imagery</option>
          <option>Smoother rhyme and rhythm</option><option>More emotional impact</option>
          <option>Clearer wording</option><option>Make it stranger and more memorable</option>
          <option>Preserve voice with minimal changes</option></select></div>
        <div><label>Additional direction</label><input id="poemSelectionNote" type="text"></div>
        <div class="fixed"><button class="btn" onclick="captureSelection()">Capture selection</button>
        <button class="btn primary" id="altButton" onclick="createAlternatives()">Create 3 Alternatives</button></div>
      </div>
      <div class="small" id="selPreview" style="white-space:pre-wrap;border-left:3px solid var(--accent);padding:6px 10px;margin:8px 0"></div>
      <div id="selStatus" class="status">Capture a passage to begin.</div>
      <div id="poemSelectionAlternatives"></div>
    </div>
  </div>
</section>

<!-- ============ ARCHIVE / MY WRITING ============ -->
<section class="page" id="pg-archive">
  <div class="hero"><h1>Poem &amp; Story Archive</h1>
  <p>Every saved draft, original, and polished version — scanned read-only, grouped by title.</p></div>
  <div class="card wide"><div class="row">
    <div><label>Search</label><input id="archiveSearch" type="text" placeholder="title, voice, author, theme, memory, audience" oninput="renderArchiveList()"></div>
    <div><label>Filter</label><select id="archiveFilter" onchange="renderArchiveList()">
      <option value="">All works</option><option value="poem">Poems</option>
      <option value="short_story">Short stories</option><option value="legacy">Legacy work</option>
      <option value="for_akaysha">For Akaysha</option><option value="for_nevaeh">For Nevaeh</option></select></div>
    <div class="fixed"><button class="btn" onclick="renderArchive()">Refresh</button></div>
  </div>
  <div id="archiveSummary" class="small" style="margin-top:8px"></div></div>
  <div class="grid" id="archiveList"></div>
  <div id="archiveDetail"></div>
</section>

<!-- ============ NOVEL FORGE ============ -->
<section class="page" id="pg-novelforge">
  <div class="hero"><h1>Novel Forge</h1>
  <p>Universes, story bibles, characters, locations, artifacts, timelines, and mysteries.</p></div>
  <div class="card wide"><h3>Universes</h3><div id="nfDashboard">Loading…</div></div>
  <div class="card wide"><h3>Editor</h3>
    <div class="row"><div><label>Universe name</label><input id="nfUniverse" type="text" placeholder="Example: Slipping into Darkness"></div></div>
    <label>Premise</label><textarea id="nfPremise" placeholder="What is this universe about?"></textarea>
    <label>Characters (one per line — card builders below append here)</label><textarea id="nfCharacters"></textarea>
    <details><summary>Character card builder</summary>
      <div class="row">
        <div><label>Name</label><input id="nfCharName" type="text" placeholder="Anthony / Whisper"></div>
        <div><label>Role</label><input id="nfCharRole" type="text" placeholder="Protagonist, mentor, antagonist…"></div>
        <div><label>Status</label><input id="nfCharStatus" type="text" placeholder="Alive, turned, dead, unknown…"></div>
      </div>
      <label>Details</label><textarea id="nfCharDetails" placeholder="Core motivation, powers, wound, secret, relationship to prophecy, canon facts."></textarea>
      <div class="row"><div><label>Tags</label><input id="nfCharTags" type="text" placeholder="Anthony, Kayock, prophecy, Book 1"></div>
      <div class="fixed"><button class="btn" onclick="addCharacterCard()">Append card</button></div></div>
    </details>
    <label>Locations</label><textarea id="nfLocations" placeholder="Pueblo tunnels&#10;Olmec pyramid&#10;Kayock's lair"></textarea>
    <details><summary>Location card builder</summary>
      <div class="row">
        <div><label>Name</label><input id="nfLocName" type="text" placeholder="Pueblo tunnels"></div>
        <div><label>Type</label><input id="nfLocType" type="text" placeholder="City, lair, ancient ruin, prison, sanctuary"></div>
        <div><label>Characters</label><input id="nfLocCharacters" type="text" placeholder="Anthony, Kayock, Jokaya"></div>
      </div>
      <label>Description</label><textarea id="nfLocDescription" placeholder="What is this place, what does it feel like, and why does it matter?"></textarea>
      <label>Secrets</label><textarea id="nfLocSecrets" style="min-height:60px"></textarea>
      <label>Mysteries</label><textarea id="nfLocMysteries" style="min-height:60px"></textarea>
      <button class="btn" onclick="addLocationCard()">Append card</button>
    </details>
    <label>Artifacts</label><textarea id="nfArtifacts" placeholder="Crystal skulls&#10;Silver cross&#10;Ancient blood vats"></textarea>
    <details><summary>Artifact card builder</summary>
      <div class="row">
        <div><label>Name</label><input id="nfArtName" type="text" placeholder="Crystal skulls"></div>
        <div><label>Type</label><input id="nfArtType" type="text" placeholder="Relic, weapon, prophecy key, vessel, record"></div>
        <div><label>Characters</label><input id="nfArtCharacters" type="text" placeholder="Anthony, Kayock, Thoth"></div>
      </div>
      <label>Function</label><textarea id="nfArtFunction" style="min-height:60px"></textarea>
      <label>History</label><textarea id="nfArtHistory" style="min-height:60px"></textarea>
      <label>Rules / costs / limits</label><textarea id="nfArtRules" style="min-height:60px"></textarea>
      <label>Mysteries</label><textarea id="nfArtMysteries" style="min-height:60px"></textarea>
      <button class="btn" onclick="addArtifactCard()">Append card</button>
    </details>
    <label>Timeline (one event per line)</label><textarea id="nfTimeline" placeholder="Book 1: Anthony learns the prophecy…&#10;Kayock dies…"></textarea>
    <details><summary>Timeline event builder</summary>
      <div class="row">
        <div><label>Era / book</label><input id="nfEventEra" type="text" placeholder="Book 1, Ancient Egypt, Modern Pueblo"></div>
        <div><label>Event</label><input id="nfEventTitle" type="text" placeholder="Anthony learns the prophecy"></div>
      </div>
      <label>Details</label><textarea id="nfEventDetails" style="min-height:60px"></textarea>
      <div class="row"><div><label>Tags</label><input id="nfEventTags" type="text" placeholder="Anthony, Kayock, prophecy"></div>
      <div class="fixed"><button class="btn" onclick="addTimelineCard()">Append event</button></div></div>
    </details>
    <label>Mysteries / unresolved threads (one per line)</label><textarea id="nfMysteries" placeholder="What happened to the ex?&#10;How did Croatoan escape?"></textarea>
    <details><summary>Mystery builder</summary>
      <div class="row">
        <div><label>Mystery</label><input id="nfMysteryTitle" type="text" placeholder="What exactly did Anthony's ex become?"></div>
        <div><label>Status</label><select id="nfMysteryStatus"><option>Unresolved</option><option>Partially revealed</option><option>Resolved</option><option>Withheld</option></select></div>
      </div>
      <label>Details / payoff plan</label><textarea id="nfMysteryDetails" style="min-height:60px"></textarea>
      <button class="btn" onclick="addMysteryCard()">Append mystery</button>
    </details>
    <label>Scenes (one per line)</label><textarea id="nfScenes"></textarea>
    <label>Notes</label><textarea id="nfNotes"></textarea>
    <div class="row" style="margin-top:10px">
      <button class="btn primary" onclick="saveUniverse()">Save Universe</button>
      <button class="btn" onclick="renderNovelForge()">Refresh list</button>
      <span id="nfCounts"></span>
    </div>
    <div id="nfStatus" class="status">No universe loaded.</div>
  </div>
  <div class="card wide"><h3>Living Story Bible — Canon Review</h3>
    <p class="small">Facts stay proposed until approved. Only approved facts qualify as canon. No manuscript or existing universe lists are changed here.</p>
    <div id="nfCanonList" class="status">Load or save a universe to review canon.</div>
    <details><summary>Propose a sourced canon fact</summary>
      <div class="row">
        <div><label>Type</label><select id="nfCanonKind"><option value="character">Character</option><option value="location">Location</option><option value="artifact">Artifact</option><option value="event">Event</option><option value="relationship">Relationship</option><option value="thread">Plot thread</option><option value="rule">World rule</option></select></div>
        <div><label>Subject</label><input id="nfCanonSubject" type="text" placeholder="Character or event name"></div>
      </div>
      <label>Proposed fact</label><textarea id="nfCanonClaim" placeholder="State the specific fact in your own words."></textarea>
      <div class="row">
        <div><label>Evidence source</label><input id="nfCanonSource" type="text" placeholder="Chapter 3, scene 2"></div>
        <div><label>Chapter (optional)</label><input id="nfCanonChapter" type="text" placeholder="03"></div>
      </div>
      <label>Exact supporting excerpt</label><textarea id="nfCanonQuote" placeholder="Copy a short passage from the original manuscript."></textarea>
      <div class="row">
        <div><label>Fictional world time (optional)</label><input id="nfCanonWorldTime" type="text" placeholder="Day 4"></div>
        <div><label>Narrative order (optional)</label><input id="nfCanonNarrative" type="text" placeholder="Book 1, Chapter 3"></div>
      </div>
      <button class="btn primary" onclick="proposeCanonFact()">Submit for review</button>
    </details>
  </div>
  <div class="card wide"><h3>Story Bible Export</h3>
    <div class="row"><div><label>Readiness note</label><input id="nfReadiness" type="text" placeholder="draft, review, publish-ready…"></div>
    <div class="fixed"><button class="btn primary" onclick="exportStoryBible()">Export Story Bible (JSON + Markdown + Text)</button></div></div>
    <div id="nfExportStatus" class="status">Exports are written to the NovelForge/Exports folder.</div>
  </div>
</section>

<!-- ============ STORY FORGE ============ -->
<section class="page" id="pg-storyoverview">
  <div class="hero"><h1>Story Forge</h1>
  <p>Approval-gated story projects: manifest, chapter cards, continuity handoffs, versioned drafts, and prose.</p></div>
  <div class="card wide"><h3>Overview</h3><div id="storyOverviewStatus" class="status">Loading…</div></div>
</section>

<section class="page" id="pg-storycreate">
  <div class="hero"><h1>Create Story Project</h1>
  <p>A gate builds the plan first; nothing is written until you approve with the exact phrase.</p></div>
  <div class="card wide"><h3>Project</h3>
    <div class="row">
      <div><label>Title</label><input id="storyCreateTitle" type="text" placeholder="Slipping into Darkness"></div>
      <div><label>Project id (optional)</label><input id="storyCreateId" type="text" placeholder="auto from title"></div>
      <div><label>Author</label><input id="storyCreateAuthor" type="text" value="Eric Z. Fox"></div>
    </div>
    <label>Approval phrase</label><input id="storyCreatePhrase" type="text" placeholder="CREATE STORY PROJECT">
    <h3 style="margin-top:12px">Books</h3>
    <div id="storyBooks"></div>
    <button class="btn" onclick="addBookRow()">Add another book</button>
    <div class="row" style="margin-top:10px">
      <button class="btn" onclick="storyCreateGate(false)">Run approval gate (no writes)</button>
      <button class="btn primary" onclick="storyCreateGate(true)">Create project (approve)</button>
    </div>
    <div id="storyCreateStatus" class="status">The gate previews every folder and file before anything is written.</div>
  </div>
</section>

<section class="page" id="pg-storychapters">
  <div class="hero"><h1>Chapter Planner &amp; Cards</h1>
  <p>Plan chapter cards, preview every file the save will create, then approve.</p></div>
  <div class="card wide"><h3>Target</h3>
    <div class="row">
      <div><label>Project</label><select id="storyChaptersProject" onchange="S.story.project=this.value"></select></div>
      <div><label>Book id</label><input id="storyChaptersBook" type="text" value="book_1"></div>
      <div class="fixed"><button class="btn" onclick="storyChaptersChanged()">Check saved cards</button></div>
    </div>
    <div id="storyChaptersSaved" class="status">No saved-card check run yet.</div>
  </div>
  <div class="card wide"><h3>Chapter cards</h3>
    <div id="storyChapterCards"></div>
    <button class="btn" onclick="addChapterRow()">Add chapter card</button>
    <label style="margin-top:10px">Approval phrase (for save)</label>
    <input id="storyChaptersPhrase" type="text" placeholder="SAVE CHAPTER CARDS">
    <div class="row" style="margin-top:10px">
      <button class="btn" onclick="storyChaptersPlan('preview')">Preview plan (no writes)</button>
      <button class="btn" onclick="storyChaptersPlan('gate')">Run save gate</button>
      <button class="btn primary" onclick="storyChaptersPlan('action')">Save chapter cards (approve)</button>
    </div>
    <div id="storyChaptersPreview" class="status">Preview shows the exact files that would be created.</div>
    <div id="storyChaptersGate" class="status" style="margin-top:8px">Gate result appears here.</div>
  </div>
</section>

<section class="page" id="pg-storyeditor">
  <div class="hero"><h1>Chapter Editor</h1>
  <p>Edit a saved chapter card with diff verification; the original is always backed up first.</p></div>
  <div class="card wide">
    <div class="row">
      <div><label>Project</label><select id="storyEditorProject" onchange="storyEditorListFiles()"></select></div>
      <div><label>Chapter file</label><select id="storyEditorFile"></select></div>
      <div class="fixed"><button class="btn" onclick="storyEditorLoad()">Load</button></div>
    </div>
    <div id="storyEditorInfo" class="small"></div>
    <label>Original</label><textarea id="storyEditorOriginal" readonly class="big"></textarea>
    <label>Edited version</label><textarea id="storyEditorContent" class="big"></textarea>
    <label>Approval phrase</label><input id="storyEditorPhrase" type="text" placeholder="APPROVE CHAPTER EDIT">
    <div class="row" style="margin-top:8px">
      <button class="btn" onclick="storyEditorCompare()">Verify diff (gate)</button>
      <button class="btn primary" onclick="storyEditorApply()">Apply edit (approve)</button>
    </div>
    <div id="storyEditorStatus" class="status">Load a chapter to begin.</div>
  </div>
</section>

<section class="page" id="pg-storydrafts">
  <div class="hero"><h1>Draft Workspace</h1>
  <p>Versioned chapter drafts: save, continue, history, and side-by-side compare.</p></div>
  <div class="card wide">
    <div class="row">
      <div><label>Project</label><select id="storyDraftsProject" onchange="storyDraftsRefresh()"></select></div>
      <div><label>Book id</label><input id="storyDraftsBook" type="text" value="book_1" onchange="storyDraftsRefresh()"></div>
      <div><label>Chapter name</label><input id="storyDraftsChapter" type="text" placeholder="Chapter 01 — The Prophecy" onchange="storyDraftsRefresh()"></div>
    </div>
    <div id="storyDraftsInfo" class="small"></div>
    <label>Draft text (each save becomes a new version)</label>
    <textarea id="storyDraftsContent" class="big" placeholder="Write or paste the chapter draft here. Continuing? Paste the FULL new version — it is saved as the next version."></textarea>
    <div class="row" style="margin-top:8px">
      <button class="btn" onclick="storyDraftsSave('gate')">Save gate</button>
      <button class="btn primary" onclick="storyDraftsSave('action')">Save version</button>
      <button class="btn" onclick="storyDraftsContinue('gate')">Continue gate</button>
      <button class="btn" onclick="storyDraftsContinue('action')">Save continuation</button>
      <button class="btn" onclick="storyDraftsRefresh()">Refresh</button>
    </div>
    <div id="storyDraftsStatus" class="status">Versions accumulate; nothing is ever overwritten.</div>
  </div>
  <div class="card wide"><h3>Version history</h3><div id="storyDraftsHistory">Choose a project, book, and chapter.</div></div>
  <div class="card wide"><h3>Compare versions</h3>
    <div class="row">
      <div><label>Left</label><select id="storyDraftsLeft"></select></div>
      <div><label>Right</label><select id="storyDraftsRight"></select></div>
      <div class="fixed"><button class="btn" onclick="storyDraftsCompare()">Compare</button></div>
    </div>
    <div id="storyDraftsCompare" class="status">Diff metrics and a unified-diff preview appear here.</div>
  </div>
</section>

<section class="page" id="pg-storyprose">
  <div class="hero"><h1>Prose Workspace</h1>
  <p>Real prose manuscript versions with verified, backed-up edits.</p></div>
  <div class="card wide"><h3>Manuscript versions</h3>
    <div class="row">
      <div><label>Project</label><select id="storyProseProject" onchange="storyProseRefresh()"></select></div>
      <div><label>Label</label><input id="storyProseLabel" type="text" placeholder="manuscript" value="manuscript"></div>
    </div>
    <div id="storyProseInfo" class="status">No prose versions yet.</div>
    <label>New prose version</label><textarea id="storyProseContent" class="big"></textarea>
    <button class="btn primary" onclick="storyProseSave()">Save prose version (no overwrite)</button>
  </div>
  <div class="card wide"><h3>Prose editor</h3>
    <div class="row">
      <div><label>File</label><select id="storyProseFile"></select></div>
      <div class="fixed"><button class="btn" onclick="storyProseLoad()">Load</button></div>
    </div>
    <div id="storyProseEditInfo" class="small"></div>
    <label>Edited prose</label><textarea id="storyProseEditor" class="big"></textarea>
    <label>Approval phrase</label><input id="storyProsePhrase" type="text" placeholder="APPROVE PROSE EDIT">
    <div class="row" style="margin-top:8px">
      <button class="btn" onclick="storyProseCompare()">Refresh compare</button>
      <button class="btn primary" onclick="storyProseEditApply()">Apply edit (approve)</button>
    </div>
    <div id="storyProseEditStatus" class="status">Load a prose file to begin.</div>
  </div>
</section>

<!-- ============ WEAVER ============ -->
<section class="page" id="pg-weaver">
  <div class="hero"><h1>The Weaver</h1>
  <p>Weave two to four sources into one new poem, short story, clean prose, or Twine-ready passages.</p></div>
  <div class="card wide"><h3>Weave setup</h3>
    <div class="row">
      <div><label>Weave mode</label><select id="weaverMode">
        <option value="shared_soul">Shared soul — one new work from what the sources share</option>
        <option value="braided_voices">Braided voices — threads stay distinct</option>
        <option value="best_threads">Best threads — strongest passages joined</option>
        <option value="new_tapestry">New tapestry — new original work inspired by sources</option></select></div>
      <div><label>Output type</label><select id="weaverOutputType" onchange="updateWeaverFormatHelp()">
        <option value="poem">Poem</option><option value="short_story">Short story</option>
        <option value="clean_prose" selected>Clean prose</option><option value="twine">Twine-ready passages</option></select></div>
      <div><label>Creative voice</label><select id="weaverVoice"></select></div>
      <div><label>Length</label><select id="weaverLength"><option>Short</option><option selected>Medium</option><option>Long</option></select></div>
    </div>
    <label>Direction for the weave</label>
    <textarea id="weaverDirection" placeholder="Keep the emotional turn from Source 1, the setting from Source 2, and the final image from Source 3…"></textarea>
    <div id="weaverFormatHelp" class="small" style="margin-top:6px">Clean prose keeps deliberate paragraph and scene breaks.</div>
  </div>
  <div class="grid" id="weaverSources"></div>
  <div class="card wide"><h3>Result</h3>
    <button class="btn primary" id="weaverGenerateButton" onclick="weaverGenerate()">Weave sources</button>
    <span id="weaverStatus" class="status" style="display:inline-block;max-width:70%">Add at least two sources.</span>
    <div class="row"><div><label>Title</label><input id="weaverTitle" type="text"></div></div>
    <label>Woven work</label><textarea id="weaverOutput" class="big" placeholder="The clean woven work will appear here…"></textarea>
    <button class="btn primary" onclick="weaverSave()">Save (separate revision, never overwrite)</button>
    <label>Source map (editorial artifact)</label><div id="weaverSourceMap" class="status">The planner's concise source map appears here.</div>
    <label>Originality warnings</label><div id="weaverWarnings" class="status">Copy-similarity metrics appear here.</div>
  </div>
</section>

<!-- ============ EDITORIAL / CRAFT SUITE HANDOFF ============ -->
<section class="page" id="pg-finishing">
  <div class="hero"><h1>Editorial &amp; Craft Handoff</h1>
    <p>Optional editorial feedback and publication-format exports. Nothing is overwritten or sent to Craft Suite automatically.</p></div>
  <div class="card wide"><h3>Working passage (unsaved)</h3>
    <div class="row">
      <div><label>Title</label><input id="finishTitle" type="text" value="Untitled"></div>
      <div><label>Type</label><select id="finishType"><option value="poem">Poem</option><option value="short_story">Short story</option><option value="novel">Novel chapter</option><option value="prose" selected>Prose</option></select></div>
    </div>
    <label>Import from an existing work area</label>
    <div class="row"><div><select id="finishSource">
      <option value="studio">Creator output</option><option value="polisher">Polisher input</option>
      <option value="polished">Suggested polished copy</option><option value="story-draft">Story chapter draft</option>
      <option value="story-prose">Prose workspace</option><option value="story-edited">Prose editor</option>
      <option value="weaver">The Weaver</option></select></div>
      <div class="fixed"><button class="btn" onclick="finishingImport(q('finishSource').value)">Copy into finishing desk</button></div></div>
    <label>Paste or edit the passage here</label><textarea id="finishText" class="big" placeholder="Your original passage stays unchanged in its Forge."></textarea>
    <div class="row"><div><label>Editorial mode</label><select id="finishMode">
      <option value="review">Critique: actionable notes only</option>
      <option value="suggestion">Optional revised passage (never auto-apply)</option></select></div>
      <div><label>Direction / areas of concern</label><input id="finishDirection" type="text" placeholder="Keep my voice; focus on pacing…"></div>
      <div class="fixed"><button class="btn primary" onclick="finishingReview()">Stream review</button>
      <button class="btn" id="finishStop" onclick="finishingCancel()" disabled>Stop</button>
      <button class="btn" onclick="finishingReviewClassic()">Classic review</button></div></div>
    <div id="finishStatus" class="status">A review uses the model endpoint configured in Settings. No model is started or reserved by this tool.</div>
    <label>Model response — review or suggested revision</label><textarea id="finishResult" class="big" readonly placeholder="Suggestions appear here, separate from your original."></textarea>
  </div>
  <div class="card wide"><h3>Craft Suite handoff</h3>
    <p class="small">Download a manuscript file and import it into WordCraft or another editor. There is no assumed Craft Suite import API.</p>
    <button class="btn primary" onclick="finishingExport('html')">Download print-style HTML</button>
    <button class="btn" onclick="finishingExport('md')">Download Markdown</button>
    <button class="btn" onclick="finishingExport('txt')">Download plain text</button>
    <button class="btn" onclick="finishingOpenCraft()">Open Craft Suite (configured URL)</button>
  </div>
</section>

<!-- ============ SETTINGS ============ -->
<section class="page" id="pg-settings">
  <div class="hero"><h1>Settings</h1>
  <p>Model endpoint, LAN server, storage, and voice pack.</p></div>
  <div class="card wide"><h3>OpenAI-compatible model endpoint</h3>
    <p class="small">Works with llama.cpp llama-server, LM Studio, Ollama, llamafile, vLLM, text-generation-webui, or any hosted API speaking the OpenAI chat protocol. Changes are saved to config.json and take effect immediately.</p>
    <div class="row">
      <div><label>Base URL</label><input id="cfgBaseUrl" type="text" placeholder="http://127.0.0.1:8080"></div>
      <div><label>Model name</label><input id="cfgModel" type="text" placeholder="local-model"></div>
    </div>
    <div class="row">
      <div><label>Chat path</label><input id="cfgChatPath" type="text" placeholder="/v1/chat/completions"></div>
      <div><label>Health path</label><input id="cfgHealthPath" type="text" placeholder="/health"></div>
      <div><label>Health check kind</label><select id="cfgHealthKind">
        <option value="auto">auto</option><option value="http_status">http_status</option>
        <option value="openai_models">openai_models</option></select></div>
      <div><label>Timeout (seconds)</label><input id="cfgTimeout" type="number" value="420"></div>
    </div>
    <label>API key (optional — stored in config.json; prefer the KAYOCK_MODEL_API_KEY environment variable)</label>
    <input id="cfgApiKey" type="password" autocomplete="off">
    <div class="row" style="margin-top:10px">
      <button class="btn primary" onclick="saveModelConfig()">Save endpoint settings</button>
      <button class="btn" onclick="testModelConfig()">Test connection</button>
    </div>
    <div id="cfgTestStatus" class="status">The test lists reachable endpoints and probes one chat completion.</div>
  </div>
  <div class="card wide"><h3>Optional Craft Suite browser handoff</h3>
    <p class="small">Enter the LAN address of your Craft Suite homepage. This only opens the site in a separate tab; export/import remains manual until its APIs are verified.</p>
    <div class="row"><div><label>Craft Suite URL</label><input id="cfgCraftUrl" type="text" placeholder="https://LAN-HOST:PORT"></div>
      <div class="fixed"><button class="btn" onclick="saveCraftConfig()">Save Craft Suite link</button></div></div>
  </div>
  <div class="card wide"><h3>Server &amp; storage</h3><div id="cfgServerInfo">Loading…</div>
    <div class="notice">Host and port are read at startup from config.json or CLI flags
    (<code>--host 0.0.0.0 --port 8765</code>). Restart the app after changing them.</div>
  </div>
  <div class="card wide"><h3>Private voice pack (Eric — Poet/Narrator)</h3>
    <div id="cfgVoicePack"></div>
    <p class="small">The four source poems are copyrighted and are <b>not</b> bundled with the public release.
    To restore the full original prompt (the poems as read-only style references), place
    <code>eric_poet_narrator_private.json</code> in <code>&lt;data_dir&gt;/voice_packs/</code>
    or <code>addons/private_eric_poet_narrator/</code>, then restart. See docs/PRIVATE_VOICE_PACK.md.</p>
  </div>
</section>

</main>
</div>
<div id="toast"></div>
<script>__JS__</script>
</body></html>
"""


def render_page() -> str:
    html = _HTML.replace('__CSS__', _CSS).replace('__JS__', _JS)
    return html
