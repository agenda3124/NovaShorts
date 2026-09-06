const API='http://127.0.0.1:38471';
let activeJobs=0;
const MAX_ACTIVE=4;

async function token(){const x=await chrome.storage.local.get(['bridgeToken']);return x.bridgeToken||'';}
async function api(path,options={}){
  const t=await token();
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
async function openTab(url,waitMs=5200){
  const tab=await chrome.tabs.create({url,active:false});
  await sleep(waitMs);
  return tab;
}
async function closeTab(tab){try{if(tab&&tab.id)await chrome.tabs.remove(tab.id);}catch(e){}}

async function collect(task){
  let tab;
  try{
    tab=await openTab(task.url,task.wait_ms||5200);
    const injected=await chrome.scripting.executeScript({target:{tabId:tab.id},func:async()=>{
      const pause=ms=>new Promise(r=>setTimeout(r,ms));
      for(let i=0;i<3;i++){
        window.scrollTo(0,Math.min(document.body.scrollHeight,(i+1)*Math.max(innerHeight,900)));
        await pause(650);
      }
      window.scrollTo(0,0);
      return Array.from(document.querySelectorAll('a[href]')).map(a=>{
        const img=a.querySelector('img');
        const thumb=img ? (img.currentSrc||img.src||img.getAttribute('data-src')||img.getAttribute('data-original')||'') : '';
        const title=(a.innerText||a.getAttribute('title')||(img&&img.alt)||'').trim();
        return {url:a.href,title,thumbnail:thumb};
      }).filter(x=>x.url);
    }});
    const all=(injected[0]&&injected[0].result)||[];
    const rx=platformRegex(task.platform);const seen=new Set();
    const results=all.filter(x=>rx.test(x.url)).filter(x=>{if(seen.has(x.url))return false;seen.add(x.url);return true;}).slice(0,60).map(x=>({...x,platform:task.platform,keyword:task.keyword}));
    await api('/v1/results',{method:'POST',body:JSON.stringify({task,items:results})});
  }catch(e){
    await api('/v1/results',{method:'POST',body:JSON.stringify({task,items:[{url:task.url,title:'수집 오류: '+String(e),thumbnail:'',platform:task.platform,keyword:task.keyword,error:true}]})});
  }finally{await closeTab(tab);}
}

async function analyzeProduct(task){
  let tab;
  try{
    tab=await openTab(task.url,task.wait_ms||4500);
    const injected=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>{
      const meta=(key)=>document.querySelector(`meta[property="${key}"]`)?.content||document.querySelector(`meta[name="${key}"]`)?.content||'';
      const clean=v=>String(v||'').replace(/\s+/g,' ').trim();
      const walk=o=>{
        if(!o)return null;
        if(Array.isArray(o)){for(const v of o){const r=walk(v);if(r)return r;}return null;}
        if(typeof o==='object'){
          const t=o['@type'];const arr=Array.isArray(t)?t:[t];
          if(arr.some(x=>String(x||'').toLowerCase()==='product'))return o;
          for(const v of Object.values(o)){const r=walk(v);if(r)return r;}
        }
        return null;
      };
      let product=null;
      for(const s of document.querySelectorAll('script[type="application/ld+json"]')){
        try{const r=walk(JSON.parse(s.textContent||'{}'));if(r){product=r;break;}}catch(e){}
      }
      const brand=product&&product.brand?(typeof product.brand==='object'?(product.brand.name||''):product.brand):'';
      const image=product&&product.image?(Array.isArray(product.image)?product.image[0]:product.image):'';
      return {
        url:location.href,
        pageTitle:document.title||'',
        title:clean((product&&product.name)||meta('og:title')||document.title||''),
        ogTitle:meta('og:title'),
        image:clean(image||meta('og:image')||meta('twitter:image')),
        ogImage:meta('og:image'),
        brand:clean(brand),
        model:clean((product&&(product.model||product.mpn))||''),
        sku:clean((product&&product.sku)||''),
        description:clean((product&&product.description)||meta('og:description')||'')
      };
    }});
    const profile=(injected[0]&&injected[0].result)||{};
    await api('/v1/results',{method:'POST',body:JSON.stringify({task,profile})});
  }catch(e){
    await api('/v1/results',{method:'POST',body:JSON.stringify({task,error:String(e),profile:{}})});
  }finally{await closeTab(tab);}
}

async function extractMedia(task){
  let tab;
  try{
    tab=await openTab(task.url,task.wait_ms||5200);
    const injected=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>{
      const out=[];const add=u=>{try{if(u){const x=new URL(u,location.href).href;if(/^https?:/i.test(x))out.push(x);}}catch(e){}};
      document.querySelectorAll('video').forEach(v=>{add(v.currentSrc);add(v.src);if(v.poster)add(v.poster);});
      document.querySelectorAll('video source,source[type*="video"]').forEach(s=>add(s.src||s.getAttribute('src')));
      ['og:video','og:video:url','og:video:secure_url'].forEach(k=>add(document.querySelector(`meta[property="${k}"]`)?.content));
      try{performance.getEntriesByType('resource').forEach(e=>{if(/\.(mp4|m3u8|webm)(\?|$)/i.test(e.name)||/video/i.test(e.initiatorType||''))add(e.name);});}catch(e){}
      const seen=new Set();return {title:document.title||'',url:location.href,media:out.filter(x=>!seen.has(x)&&seen.add(x)).slice(0,30)};
    }});
    const media=(injected[0]&&injected[0].result)||{};
    await api('/v1/results',{method:'POST',body:JSON.stringify({task,media})});
  }catch(e){
    await api('/v1/results',{method:'POST',body:JSON.stringify({task,error:String(e),media:{media:[]}})});
  }finally{await closeTab(tab);}
}

async function dispatch(task){
  if(!task)return;
  if(task.type==='collect_links')return collect(task);
  if(task.type==='analyze_product_page')return analyzeProduct(task);
  if(task.type==='extract_media')return extractMedia(task);
  await api('/v1/results',{method:'POST',body:JSON.stringify({task,error:'unknown task type'})});
}

async function poll(){
  try{
    const t=await token();if(!t||activeJobs>=MAX_ACTIVE)return;
    const r=await api('/v1/tasks');
    if(r&&r.task){
      activeJobs++;
      dispatch(r.task).catch(()=>{}).finally(()=>{activeJobs=Math.max(0,activeJobs-1);});
    }
  }catch(e){}
}
setInterval(poll,700);
chrome.runtime.onInstalled.addListener(()=>poll());
