const data=window.CANOPY;
const $=id=>document.getElementById(id);
const fmt=(d,opts={day:'numeric',month:'short'})=>new Date(d+'T00:00:00Z').toLocaleDateString('en-GB',{...opts,timeZone:'UTC'});
const num=x=>x.toFixed(3);
const pct=x=>(100*x).toFixed(1)+'%';
const signed=x=>(x>=0?'+':'−')+Math.abs(x).toFixed(3);
const escapeText=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
let selected='',showObserved=false, visibleRows=[];
const marks={};
const reviewOptions=['Unreviewed','Colour change visible','No clear colour change','Image obscured or uncertain'];
const annotationKey=(issue,r,channel)=>[issue,r.code,r.date,channel].join('/');
let storageAvailable=true;
try {Object.assign(marks,JSON.parse(localStorage.getItem('canopy-compare-marks')||'{}'));}
catch {storageAvailable=false;}
const exactControl=document.createElement('label');
exactControl.className='fixed-date';
exactControl.innerHTML='<input id="exact" type="checkbox"> Use this date only';
const dateLabel=$('end').parentElement;
const dateGroup=document.createElement('div');
dateLabel.replaceWith(dateGroup);dateGroup.append(dateLabel,exactControl);
const options=()=>({issue:$('issue').value,channel:$('channel').value,end:$('end').value,threshold:Number($('threshold').value),search:$('search').value,exact:$('exact').checked});

function changeIssue(){
  const issue=$('issue').value;
  $('end').min=addDays(issue,1);$('end').max=addDays(issue,7);$('end').value=addDays(issue,7);
  selected='';showObserved=false;render();
}
function render(){
  const opt=options(), result=plan(data,opt), budget=Number($('budget').value);
  visibleRows=result.rows;
  const count=visibleRows.length, exportCount=Math.min(count,budget), strong=visibleRows.filter(r=>r.strong).length;
  $('download').disabled=!count;$('export-status').textContent='';
  $('queue-note').textContent=result.error ? 'Check the archive date.' : `${count} sites · ${strong} meet shift · ${exportCount} in log`+(result.excluded?` · ${result.excluded} lack a matched pair or recent baseline`: '');
  if (!visibleRows.some(r=>r.code===selected)) selected=visibleRows[0]?.code || '';
  $('rows').replaceChildren(...visibleRows.map((r,i)=>{
    const b=document.createElement('button');b.className='row';b.dataset.site=r.code;b.setAttribute('aria-pressed',String(r.code===selected));
    b.setAttribute('aria-label',`${i+1}, ${r.meta.name}, ${r.strong?'flagged':'below threshold'}, ${fmt(r.date)}`);
    b.innerHTML=`<span class="rank">${String(i+1).padStart(2,'0')}</span><span><strong>${escapeText(r.code)}</strong><small>${escapeText(r.meta.name)}</small></span><span class="date">${fmt(r.date)}<small>${r.strong?'Flagged':'Below'}${i<budget?' · log':''}</small></span>`;
    b.onclick=event=>{selected=r.code;render();if(event.detail===0) document.querySelector(`[data-site="${r.code}"]`).focus();};return b;
  }));
  const r=visibleRows.find(x=>x.code===selected);
  if (!r){
    $('detail').innerHTML=`<div class="empty"><p class="eyebrow">NO ARCHIVE PAIR</p><h2>${result.error?'Date outside this archive':'No matching camera'}</h2><p>${escapeText(result.error || 'Clear the search or use another historical window to see available sites.')}</p><button id="restore" class="secondary">${result.error?'Use the archived week':'Show all sites'}</button></div>`;
    $('restore').onclick=()=>{if(result.error){$('end').value=addDays(opt.issue,7);$('exact').checked=false;}else{$('search').value='';}render();};return;
  }
  const shot=data.images[opt.issue+'/'+r.code],label=opt.channel==='gcc_90'?'Greenness':'Redness';
  const obs=r.s.obs,last=obs.at(-1)[0],replay=true;
  const actual=` Observed shift ${signed(r.truth-r.s.base)}.`;
  const action=r.strong?'Flagged change in the '+fmt(r.date)+' archive':'Below threshold on '+fmt(r.date);
  const rationale=r.strong?`The uncertainty-adjusted shift exceeds ${num(opt.threshold)}. Check the two archived frames to interpret the signal.`:`The uncertainty-adjusted shift stays below ${num(opt.threshold)}. Both frames remain available for comparison.`;
  $('detail').innerHTML=`<div class="detail-top"><div><p class="eyebrow">${escapeText(r.code)} / ${escapeText(r.meta.state)} / ${escapeText(r.meta.vegetation.toUpperCase())}</p><h2>${escapeText(r.meta.name)}</h2><p class="meta">${label} · ${escapeText(r.meta.roi)} canopy region · <a href="${escapeText(r.meta.url)}">Site record ↗</a></p></div>${shot?`<figure class="photo"><a href="${escapeText(shot.original)}"><img src="${escapeText(shot.file)}" alt="Archived ${escapeText(r.meta.name)} canopy photograph from ${fmt(shot.date)}"></a><figcaption>NEON / PhenoCam · ${fmt(shot.date)} ${shot.local_time} archive time</figcaption></figure>`:''}</div>
  <div class="recommend"><div><strong>${action}</strong><p>${rationale}</p></div><button class="primary" id="compare">Compare images</button></div>
  <div class="metrics"><div class="metric"><small>Recent baseline</small><b>${num(r.s.base)}</b></div><div class="metric"><small>Predicted change</small><b>${signed(r.delta)}</b></div><div class="metric"><small>Conservative shift</small><b>${signed(r.score)}</b></div></div>
  <div class="chart-head"><h3>${label} across the image window</h3>${replay?`<label><input id="reveal" type="checkbox" ${showObserved?'checked':''}>Reveal later observations</label>`:''}</div>
  <canvas class="chart" id="chart" role="img" aria-label="${label} time series. Baseline ${num(r.s.base)}, forecast ${num(r.mu)} on ${fmt(r.date)}, central 80 percent interval ${num(r.mu-1.28155*r.sd)} to ${num(r.mu+1.28155*r.sd)}."></canvas>
  <div class="legend"><span><i class="key observed"></i>Observed</span><span><i class="key forecast"></i>Forecast mean</span><span><i class="key band"></i>Central 80% range</span>${showObserved&&replay?'<span><i class="key outcome"></i>Later observed</span>':''}</div>
  ${showObserved?`<p id="outcome" class="outcome"><strong>Observed on ${fmt(r.date)}: ${num(r.truth)}</strong> · actual change ${signed(r.truth-r.s.base)} · predicted ${signed(r.delta)}</p>`:''}
  <details id="reason" class="explain"><summary>How the model flagged this date</summary><p>Recent baseline is the median of available observations in the four-day window ending ${fmt(last)}. Forecast mean on ${fmt(r.date)} is ${num(r.mu)} with standard deviation ${num(r.sd)}. The queue ranks absolute change minus 0.842 standard deviations. A negative score means direction remains uncertain.${showObserved&&replay?actual:''}</p><p>Thresholds are selectable review priorities. Snow, lighting and camera movement can change these colour indices. Inspect the archived frames before interpreting a vegetation change. <a href="https://phenocam.nau.edu/webcam/sites/${escapeText(r.meta.camera)}/">Camera archive ↗</a></p></details>`;
  if($('reveal')) $('reveal').onchange=e=>{showObserved=e.target.checked;render();$('reveal').focus({preventScroll:true});};
  if(shot){
    const a=$('detail').querySelector('.photo a');
    a.setAttribute('aria-label','Inspect the archived camera photograph');
    const openPair=event=>{event.preventDefault();const pair=r.after;
      const verifiedFrame=entry=>{
        const frame=window.CANOPY_REGIONS.frames[entry.file];
        return frame?.status==='verified'?{...frame,...window.CANOPY_REGIONS.masks[frame.mask]}:null;
      };
      const regions=[verifiedFrame(shot),verifiedFrame(pair)];
      const photoFig=(entry,label,region)=>`<figure><div class="region-photo"><img src="${escapeText(entry.file)}" alt="${escapeText(r.meta.name)} canopy on ${fmt(entry.date)}">${region?`<img hidden class="region-overlay" alt="" src="${escapeText(region.overlay)}">`:''}</div><figcaption><strong>${label} · ${fmt(entry.date)}</strong> ${entry.local_time} archive time · <a href="${escapeText(entry.original)}">Original ↗</a></figcaption><div class="region-note" hidden>${region?`<a href="${escapeText(region.source)}">PhenoCam mask ↗</a> · ${pct(region.fraction)} of frame`:'No verified mask for this frame.'}</div></figure>`;
      const key=annotationKey(opt.issue,r,opt.channel),mark=marks[key]||'Unreviewed';
      $('sheet-body').innerHTML=`<p class="eyebrow">${escapeText(r.code)} / CAMERA ARCHIVE</p><h2 id="sheet-title">${escapeText(r.meta.name)}</h2>${regions.some(Boolean)?`<label class="region-switch"><input type="checkbox" id="show-region"> Show measured canopy region · ${escapeText(r.meta.roi)}</label>`:'<p class="subdued">These frames have no verified canopy mask.</p>'}<div class="lightbox pair">${photoFig(shot,'Reference frame',regions[0])}${photoFig(pair,'Comparison frame',regions[1])}</div><p class="subdued">Near-noon frames from NEON / PhenoCam Network. The daily index summarizes a canopy region across observations. Interpret lighting, snow and camera alignment before marking a change.</p><label for="review-mark"><strong>What can you see in the photographs?</strong></label><div class="markline"><select id="review-mark">${reviewOptions.map(v=>`<option ${v===mark?'selected':''}>${v}</option>`).join('')}</select><span id="marked" role="status">${storageAvailable?(mark==='Unreviewed'?'Marks stay on this device':'Saved on this device'):'Session only · export to retain'}</span></div>`;
      if($('show-region')) $('show-region').onchange=event=>{
        $('sheet-body').querySelectorAll('.region-overlay,.region-note').forEach(el=>el.hidden=!event.target.checked);
      };
      $('review-mark').onchange=()=>{marks[key]=$('review-mark').value;try{localStorage.setItem('canopy-compare-marks',JSON.stringify(marks));$('marked').textContent='Saved on this device';}catch{storageAvailable=false;$('marked').textContent='Session only · export to retain';}};
      $('sheet').showModal();};
    a.onclick=openPair;$('compare').onclick=openPair;
  }
  drawChart(r,opt);
}

function drawChart(r,opt){
  const el=$('chart'),w=el.clientWidth,h=el.clientHeight;
  if(!w||!h)return;
  const dpr=window.devicePixelRatio||1;el.width=w*dpr;el.height=h*dpr;const ctx=el.getContext('2d');ctx.scale(dpr,dpr);
  const start=addDays(opt.issue,-14),end=opt.end, yObs=r.s.obs.filter(v=>v[0]>=start), fc=r.s.fc.filter(v=>v[0]<=end);
  const all=[...yObs.map(v=>v[1]),...fc.flatMap(v=>[v[1]-1.28155*v[2],v[1]+1.28155*v[2]]),...(showObserved?fc.map(v=>v[3]).filter(v=>v!==null):[])];
  const floor=Math.min(...all)-.003,ceil=Math.max(...all)+.003,top=21,left=43,right=w-9,bottom=h-24;
  const X=date=>left+(dayNumber(date)-dayNumber(start))/(dayNumber(end)-dayNumber(start))*(right-left);
  const Y=v=>bottom-(v-floor)/(ceil-floor)*(bottom-top);
  ctx.font='10px DM Sans, Arial';ctx.fillStyle='#637367';
  for(let i=0;i<4;i++){const val=floor+(ceil-floor)*i/3,y=Y(val);ctx.strokeStyle='#e1e6da';ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText(val.toFixed(3),1,y+3);}
  const chunks=series=>{const parts=[];for(const p of series){const tail=parts.at(-1);if(!tail||dayNumber(p[0])-dayNumber(tail.at(-1)[0])>1)parts.push([p]);else tail.push(p);}return parts;};
  for(const pts of chunks(fc)){ctx.fillStyle='#d7e8c9';ctx.beginPath();pts.forEach((v,i)=>ctx[i?'lineTo':'moveTo'](X(v[0]),Y(v[1]+1.28155*v[2])));[...pts].reverse().forEach(v=>ctx.lineTo(X(v[0]),Y(v[1]-1.28155*v[2])));ctx.closePath();ctx.fill();}
  function line(series,color,dash){ctx.strokeStyle=color;ctx.lineWidth=2.2;ctx.setLineDash(dash);for(const pts of chunks(series)){ctx.beginPath();pts.forEach((v,i)=>ctx[i?'lineTo':'moveTo'](X(v[0]),Y(v[1])));ctx.stroke();for(const v of pts){ctx.fillStyle=color;ctx.beginPath();ctx.arc(X(v[0]),Y(v[1]),1.7,0,2*Math.PI);ctx.fill();}}ctx.setLineDash([]);}
  line(yObs,'#34493c',[]);line(fc,'#347657',[]);if(showObserved)line(fc.filter(v=>v[3]!==null).map(v=>[v[0],v[3]]),'#b3532e',[4,3]);
  const marker=X(opt.issue);ctx.setLineDash([3,3]);ctx.strokeStyle='#8a998c';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(marker,top);ctx.lineTo(marker,bottom);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#495c4d';ctx.fillText('Issue',Math.min(marker+3,right-21),top-4);
  ctx.fillStyle='#193d30';ctx.beginPath();ctx.arc(X(r.date),Y(r.mu),4.2,0,2*Math.PI);ctx.fill();ctx.strokeStyle='white';ctx.stroke();
  for(const [date,align] of [[start,'left'],[opt.issue,'center'],[end,'right']]){ctx.textAlign=align;ctx.fillStyle='#536459';ctx.fillText(fmt(date),X(date),h-5);}ctx.textAlign='left';
}

function evidence(){
  const e=data.validation, rows=e.decision;
  $('evidence-content').innerHTML=`<div class="evidence-grid"><article class="e-card"><p class="eyebrow">FORECAST QUALITY</p><h2>Predicting canopy colour</h2><p>Gradient-boosted trees correct a seasonal and historical-analogue forecast. Training ends in 2022. Error scales use 2023. Lower CRPS means better probability forecasts.</p><table><thead><tr><th>Evaluation year</th><th>Model</th><th>Recent colour</th><th>Seasonal</th></tr></thead><tbody>${Object.entries(e.forecast).map(([year,v])=>`<tr><td>${year}</td><td>${v.model.crps.toFixed(4)}</td><td>${v.current.crps.toFixed(4)}</td><td>${v.season.crps.toFixed(4)}</td></tr>`).join('')}</tbody></table><p>The central 80% interval covered ${pct(e.coverage.gcc_90)} of green and ${pct(e.coverage.rcc_90)} of red observations across the archived horizons. Coverage varies by site and season.</p></article>
  <article class="e-card"><p class="eyebrow">ARCHIVE REPLAY</p><h2>Three image pairs per issue</h2><p>74 historical issue dates per colour. Select three cameras and check whether the observed absolute shift reached 0.010. Each method sees the same eligible cameras.</p><table><thead><tr><th>Review policy</th><th>Green hits</th><th>Red hits</th></tr></thead><tbody>${[['planner','Flexible date'],['planner, fixed day 7','Fixed day 7'],['recent trend','Recent trend · day 7']].map(([m,label])=>`<tr><td>${label}</td>${['gcc_90','rcc_90'].map(c=>`<td>${pct(rows.find(v=>v.channel===c&&v.method===m).hit_rate)}</td>`).join('')}</tr>`).join('')}</tbody></table><p>The model flagged more green changes than the trend list. The trend list found more red changes. Counts refer to index shifts, not verified plant events or equipment faults.</p></article></div>
  <article class="e-card"><h2>What you can check</h2><p>Choose a historical window, open the two photographs and reveal the later observations. Log the visual interpretation beside the model flag. Later observations are hidden from the ranking code. Historical panels used for the comparison require seven observed target days and two usable pre-issue windows. The model was evaluated at 14 sites reporting recently on 26 November 2026. This viewer offers two completed historical weeks with matched archive photographs.</p><a href="https://projects.ecoforecast.org/neon4cast-docs/Phenology.html">EFI target definitions ↗</a> · <a href="https://www.neonscience.org/data-collection/phenocams">NEON camera methods ↗</a></article>`;
}
function view(name){const p=name==='plan';$('planner').hidden=!p;$('evidence').hidden=p;$('view-plan').classList.toggle('active',p);$('view-evidence').classList.toggle('active',!p);if(!p)evidence();else render();}
$('issue').onchange=changeIssue;
for(const id of ['channel','end','threshold','budget','exact']) $(id).onchange=()=>{selected='';render()};
$('search').oninput=()=>{selected='';render()};
$('download').onclick=()=>{const rows=visibleRows.slice(0,Number($('budget').value)), opt=options();const blob=new Blob([exportRounds(rows,opt,marks)],{type:'text/csv;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`canopy-review-${opt.issue}-${opt.channel}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);$('export-status').textContent=`Exported ${rows.length} image pairs with flags, observations and original image links.`;
  $('sheet-body').innerHTML=`<p class="eyebrow">ARCHIVE REVIEW / CSV EXPORT</p><h2 id="sheet-title">Your camera review log</h2><p class="subdued">Historical issue ${fmt(opt.issue)} · ${opt.channel==='gcc_90'?'Greenness':'Redness'} · minimum shift ${num(opt.threshold)}</p><table><thead><tr><th>Site</th><th>Image date</th><th>Model flag</th><th>Visual review</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${r.code}</td><td>${fmt(r.date)}</td><td>${r.strong?'Flagged':'Below threshold'}</td><td>${escapeText(marks[annotationKey(opt.issue,r,opt.channel)]||'Unreviewed')}</td></tr>`).join('')}</tbody></table><p class="subdued">The CSV includes both archived image links, the observed index, forecast mean, uncertainty and your visual interpretation.</p>`;$('sheet').showModal();};
$('view-plan').onclick=$('back').onclick=()=>view('plan');$('view-evidence').onclick=()=>view('evidence');
window.addEventListener('resize',()=>{const r=visibleRows.find(v=>v.code===selected);if(r&&$('chart'))drawChart(r,options());});
changeIssue();
