const API='http://127.0.0.1:38471';

async function token(){const x=await chrome.storage.local.get(['bridgeToken']);return x.bridgeToken||'';}
async function api(path,options={}){
  const t=await token();
  const headers=Object.assign({'Authorization':'Bearer '+t,'Content-Type':'application/json'},options.headers||{});
  return fetch(API+path,Object.assign({},options,{headers})).then(r=>r.json());
}
function platformRegex(platform){
  if(platform==='Douyin')return /douyin\.com\/video\//i;
  if(platform==='Xiaohongshu')return /xiaohongshu\.com\/(explore|discovery\/item)\//i;
  if(platform==='Kuaishou')return /kuaishou\.com\/(short-video|f)\//i;
  if(platform==='TikTok')return /tiktok\.com\/@[^/]+\/video\//i;
  return /1688\.com\/offer\//i;
}
async function collect(task){
  const tab=await chrome.tabs.create({url:task.url,active:false});
  await new Promise(r=>setTimeout(r,6500));
  let results=[];
  try{
    const injected=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>Array.from(document.querySelectorAll('a[href]')).map(a=>({url:a.href,title:(a.innerText||a.getAttribute('title')||'').trim()})).filter(x=>x.url)});
    const all=(injected[0]&&injected[0].result)||[];const rx=platformRegex(task.platform);const seen=new Set();
    results=all.filter(x=>rx.test(x.url)).filter(x=>{if(seen.has(x.url))return false;seen.add(x.url);return true;}).slice(0,50).map(x=>({...x,platform:task.platform,keyword:task.keyword}));
  }catch(e){results=[{url:task.url,title:'수집 오류: '+String(e),platform:task.platform,keyword:task.keyword,error:true}];}
  try{await chrome.tabs.remove(tab.id);}catch(e){}
  await api('/v1/results',{method:'POST',body:JSON.stringify({task,items:results})});
}
async function poll(){
  try{
    const t=await token();if(!t)return;
    const r=await api('/v1/tasks');if(r&&r.task&&r.task.type==='collect_links')await collect(r.task);
  }catch(e){}
}
setInterval(poll,1500);chrome.runtime.onInstalled.addListener(()=>poll());
