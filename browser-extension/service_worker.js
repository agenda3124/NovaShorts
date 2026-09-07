const API='http://127.0.0.1:38471';
let activeJobs=0;
const MAX_ACTIVE=2;

async function ensureToken(){
  const x=await chrome.storage.local.get(['bridgeToken']);
  if(x.bridgeToken)return x.bridgeToken;
  try{
    const r=await fetch(API+'/v1/pair');
    if(!r.ok)return '';
    const d=await r.json();
    const t=d.bridgeToken||'';
    if(t)await chrome.storage.local.set({bridgeToken:t,pairedAt:Date.now(),bridgeVersion:d.version||''});
    return t;
  }catch(e){return '';}
}
async function api(path,options={}){
  const t=await ensureToken();
  const headers=Object.assign({'Authorization':'Bearer '+t,'Content-Type':'application/json'},options.headers||{});
  return fetch(API+path,Object.assign({},options,{headers})).then(r=>r.json());
}
function sleep(ms){return new Promise(r=>setTimeout(r,ms));}
function platformRegex(platform){
  if(platform==='TikTok')return /tiktok\.com\/@[^/]+\/video\//i;
  if(platform==='YouTube')return /(youtube\.com\/(watch\?v=|shorts\/)|youtu\.be\/)/i;
  if(platform==='Instagram')return /instagram\.com\/(reel|reels|p)\//i;
  if(platform==='Douyin')return /douyin\.com\/video\//i;
  if(platform==='Xiaohongshu')return /xiaohongshu\.com\/(explore|discovery\/item)\//i;
  if(platform==='Kuaishou')return /kuaishou\.com\/(short-video|f)\//i;
  return /1688\.com\/offer\//i;
}
function unwrapUrl(raw){
  try{
    const u=new URL(raw);
    if(/google\./i.test(u.hostname)&&u.pathname==='/url')return u.searchParams.get('q')||u.searchParams.get('url')||raw;
  }catch(e){}
  return raw||'';
}
async function openTab(url){return chrome.tabs.create({url,active:false});}
async function closeTab(tab){try{if(tab&&tab.id)await chrome.tabs.remove(tab.id);}catch(e){}}

async function waitAndCollect(tabId,maxMs=14000){
  const start=Date.now();let last=-1,stable=0;
  while(Date.now()-start<maxMs){
    try{
      const x=await chrome.scripting.executeScript({target:{tabId},func:()=>({ready:document.readyState,count:document.querySelectorAll('a[href]').length})});
      const s=(x[0]&&x[0].result)||{};const n=Number(s.count||0);
      if((s.ready==='interactive'||s.ready==='complete')&&n>=12){stable=(n===last)?stable+1:0;if(stable>=2)break;}
      last=n;
    }catch(e){}
    await sleep(650);
  }
  const injected=await chrome.scripting.executeScript({target:{tabId},func:async()=>{
    const pause=ms=>new Promise(r=>setTimeout(r,ms));let last=-1,stable=0;
    for(let i=0;i<7;i++){
      window.scrollTo(0,Math.min(document.body.scrollHeight,(i+1)*Math.max(innerHeight,900)));
      await pause(700);
      const n=document.querySelectorAll('a[href]').length;
      stable=(n===last)?stable+1:0;last=n;
      if(stable>=2&&i>=3)break;
    }
    window.scrollTo(0,0);await pause(250);
    const body=((document.body&&document.body.innerText)||'').slice(0,5000);
    const anchors=Array.from(document.querySelectorAll('a[href]')).map(a=>{
      const img=a.querySelector('img')||a.closest('div')?.querySelector('img');
      const box=a.closest('article,li,div');
      const title=(a.innerText||a.getAttribute('title')||(img&&img.alt)||(box&&box.innerText)||'').replace(/\s+/g,' ').trim();
      return {url:a.href||'',title:title.slice(0,260),thumbnail:img?(img.currentSrc||img.src||img.getAttribute('data-src')||img.getAttribute('data-original')||''):''};
    }).filter(x=>x.url);
    return {anchors,body,title:document.title||'',url:location.href||''};
  }});
  return (injected[0]&&injected[0].result)||{anchors:[],body:'',title:'',url:''};
}
function classifyEmpty(page){
  const t=((page.title||'')+' '+(page.body||'')).toLowerCase();
  if(/access denied|forbidden|request blocked|too many requests|403/.test(t))return {status:'blocked',note:'접근 차단/검증 페이지'};
  if(/login|log in|sign in|로그인|登录|登入|扫码|请登录|captcha|verify|verification|验证|robot|人机验证/.test(t))return {status:'login_required',note:'로그인 또는 추가 인증 필요 가능성'};
  return {status:'empty',note:'검색 결과 링크를 찾지 못함'};
}

async function collect(task){
  let tab;
  try{
    tab=await openTab(task.url);
    const page=await waitAndCollect(tab.id,task.wait_ms||14000);
    const rx=platformRegex(task.platform);const seen=new Set();const results=[];
    for(const x of (page.anchors||[])){
      const u=unwrapUrl(x.url);
      if(!u||!rx.test(u)||seen.has(u))continue;
      seen.add(u);results.push({...x,url:u,platform:task.platform,keyword:task.keyword});
      if(results.length>=80)break;
    }
    const empty=results.length?{status:'ok',note:`${results.length}개 영상 링크`}:classifyEmpty(page);
    await api('/v1/results',{method:'POST',body:JSON.stringify({task,items:results,status:empty.status,note:empty.note,pageTitle:page.title||''})});
  }catch(e){
    await api('/v1/results',{method:'POST',body:JSON.stringify({task,items:[],status:'error',note:String(e),error:String(e)})});
  }finally{await closeTab(tab);}
}

async function analyzeProduct(task){
  let tab;
  try{
    tab=await openTab(task.url);await sleep(task.wait_ms||4500);
    const injected=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>{
      const meta=(key)=>document.querySelector(`meta[property="${key}"]`)?.content||document.querySelector(`meta[name="${key}"]`)?.content||'';
      const clean=v=>String(v||'').replace(/\s+/g,' ').trim();
      const walk=o=>{if(!o)return null;if(Array.isArray(o)){for(const v of o){const r=walk(v);if(r)return r;}return null;}if(typeof o==='object'){const t=o['@type'];const arr=Array.isArray(t)?t:[t];if(arr.some(x=>String(x||'').toLowerCase()==='product'))return o;for(const v of Object.values(o)){const r=walk(v);if(r)return r;}}return null;};
      let product=null;for(const s of document.querySelectorAll('script[type="application/ld+json"]')){try{const r=walk(JSON.parse(s.textContent||'{}'));if(r){product=r;break;}}catch(e){}}
      const brand=product&&product.brand?(typeof product.brand==='object'?(product.brand.name||''):product.brand):'';
      const image=product&&product.image?(Array.isArray(product.image)?product.image[0]:product.image):'';
      const visibleTitle=document.querySelector('h1')?.innerText||document.querySelector('[class*="product-title"]')?.innerText||'';
      return {url:location.href,pageTitle:document.title||'',title:clean((product&&product.name)||meta('og:title')||visibleTitle||document.title||''),ogTitle:meta('og:title'),image:clean(image||meta('og:image')||meta('twitter:image')),ogImage:meta('og:image'),brand:clean(brand),model:clean((product&&(product.model||product.mpn))||''),sku:clean((product&&product.sku)||''),description:clean((product&&product.description)||meta('og:description')||'')};
    }});
    const profile=(injected[0]&&injected[0].result)||{};
    await api('/v1/results',{method:'POST',body:JSON.stringify({task,profile})});
  }catch(e){await api('/v1/results',{method:'POST',body:JSON.stringify({task,error:String(e),profile:{}})});}finally{await closeTab(tab);}
}

async function extractMedia(task){
  let tab;
  try{
    tab=await openTab(task.url);await sleep(task.wait_ms||6000);
    const injected=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>{
      const out=[];const add=u=>{try{if(u){const x=new URL(u,location.href).href;if(/^https?:/i.test(x))out.push(x);}}catch(e){}};
      document.querySelectorAll('video').forEach(v=>{add(v.currentSrc);add(v.src);});document.querySelectorAll('video source,source[type*="video"]').forEach(s=>add(s.src||s.getAttribute('src')));['og:video','og:video:url','og:video:secure_url'].forEach(k=>add(document.querySelector(`meta[property="${k}"]`)?.content));try{performance.getEntriesByType('resource').forEach(e=>{if(/\.(mp4|m3u8|webm)(\?|$)/i.test(e.name)||/video/i.test(e.initiatorType||''))add(e.name);});}catch(e){}
      return {title:document.title||'',url:location.href,media:[...new Set(out)].slice(0,40)};
    }});
    const media=(injected[0]&&injected[0].result)||{};await api('/v1/results',{method:'POST',body:JSON.stringify({task,media})});
  }catch(e){await api('/v1/results',{method:'POST',body:JSON.stringify({task,error:String(e),media:{media:[]}})});}finally{await closeTab(tab);}
}

async function dispatch(task){if(!task)return;if(task.type==='collect_links')return collect(task);if(task.type==='analyze_product_page')return analyzeProduct(task);if(task.type==='extract_media')return extractMedia(task);await api('/v1/results',{method:'POST',body:JSON.stringify({task,error:'unknown task type'})});}
async function poll(){try{const t=await ensureToken();if(!t||activeJobs>=MAX_ACTIVE)return;const r=await api('/v1/tasks');if(r&&r.task){activeJobs++;dispatch(r.task).catch(()=>{}).finally(()=>{activeJobs=Math.max(0,activeJobs-1);});}}catch(e){}}
setInterval(poll,700);
chrome.runtime.onInstalled.addListener(()=>{ensureToken().then(()=>poll());});
chrome.runtime.onStartup.addListener(()=>{ensureToken().then(()=>poll());});
