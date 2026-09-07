const status=document.getElementById('status');
async function connect(){
  status.textContent='연결 확인 중…';status.className='muted';
  try{
    let x=await chrome.storage.local.get(['bridgeToken']);let t=x.bridgeToken||'';
    if(!t){const p=await fetch('http://127.0.0.1:38471/v1/pair');if(p.ok){const d=await p.json();t=d.bridgeToken||'';if(t)await chrome.storage.local.set({bridgeToken:t,pairedAt:Date.now(),bridgeVersion:d.version||''});}}
    if(!t)throw new Error('pair failed');
    const r=await fetch('http://127.0.0.1:38471/v1/tasks',{headers:{Authorization:'Bearer '+t}});
    status.textContent=r.ok?'연결됨 · 자동 페어링 완료':'연결 정보 갱신 필요';status.className=r.ok?'ok':'bad';
    if(!r.ok)await chrome.storage.local.remove(['bridgeToken']);
  }catch(e){status.textContent='NovaShorts를 먼저 실행하세요.';status.className='bad';}
}
document.getElementById('connect').onclick=connect;connect();
