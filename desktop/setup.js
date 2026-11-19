'use strict';
const el=id=>document.getElementById(id);
window.chartmateSetup.onStatus(s=>{
  el('heading').textContent=s.heading||'Preparing ChartMate';
  el('message').textContent=s.message||'';el('detail').textContent=s.detail||'';
  if(Number.isFinite(s.percent))el('progress').value=s.percent;else el('progress').removeAttribute('value');
  el('start').hidden=s.phase!=='needs-download';el('retry').hidden=s.phase!=='error';
  el('start').disabled=false;el('retry').disabled=false;
});
el('start').onclick=()=>{el('start').disabled=true;window.chartmateSetup.start();};
el('retry').onclick=()=>{el('retry').disabled=true;window.chartmateSetup.retry();};
el('folder').onclick=()=>window.chartmateSetup.folder();
