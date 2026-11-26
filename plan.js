/* Prioritize verified archive date pairs in chromatic-coordinate units. */
const dayNumber = d => Date.parse(d+'T00:00:00Z') / 86400000;
const addDays = (date,n) => new Date((dayNumber(date)+n)*86400000).toISOString().slice(0,10);
const z80 = 0.8416212335729143;

function plan(data, {issue, channel, end, threshold, search='', exact=false}) {
  const horizon=dayNumber(end)-dayNumber(issue);
  if (!Number.isFinite(horizon) || horizon<1 || horizon>7) return {error:'Choose a date in the archived seven-day window.',rows:[]};
  const rows=[];
  let excluded=0;
  for (const [code,channels] of Object.entries(data.issues[issue])) {
    const meta=data.sites[code], s=channels[channel];
    if (![code,meta.name,meta.state,meta.vegetation].join(' ').toLowerCase().includes(search.trim().toLowerCase())) continue;
    const before=data.images[issue+'/'+code];
    if (!s || !before || !s.obs.length || !Number.isFinite(s.base) || dayNumber(issue)-dayNumber(s.obs.at(-1)[0])>7) {excluded++;continue;}
    const available=s.fc.filter(([date,mu,sd])=>date>issue && date<=end && (!exact || date===end) && Number.isFinite(mu) && sd>0 && data.images[issue+'/'+code+'/'+date]);
    if (!available.length) {excluded++;continue;}
    const candidates=available.map(([date,mu,sd,truth])=>({date,mu,sd,truth,delta:mu-s.base,score:Math.abs(mu-s.base)-z80*sd}));
    candidates.sort((a,b)=>b.score-a.score || a.date.localeCompare(b.date));
    const pick=candidates[0];
    rows.push({code,meta,s,...pick,before,after:data.images[issue+'/'+code+'/'+pick.date],strong:pick.score>=threshold});
  }
  rows.sort((a,b)=>b.score-a.score || a.code.localeCompare(b.code));
  return {rows,excluded};
}

function exportRounds(rows, {issue,channel,threshold}, marks={}) {
  const lines=[['priority','site','site_name','historical_issue','image_date','index','baseline','forecast_mean','forecast_sd','conservative_shift','threshold','model_flag','visual_review','observed_index','before_image','after_image']];
  rows.forEach((r,i)=>lines.push([i+1,r.code,r.meta.name,issue,r.date,channel,r.s.base.toFixed(5),r.mu.toFixed(5),r.sd.toFixed(5),r.score.toFixed(5),threshold,r.strong?'flagged':'below threshold',marks[[issue,r.code,r.date,channel].join('/')]||'Unreviewed',r.truth.toFixed(5),r.before.original,r.after.original]));
  return lines.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n')+'\r\n';
}
if (typeof module!=='undefined') module.exports={plan,exportRounds,addDays};
