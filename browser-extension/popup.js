const token=document.getElementById('token'),status=document.getElementById('status');
chrome.storage.local.get(['bridgeToken'],x=>{if(x.bridgeToken)token.value=x.bridgeToken;});
document.getElementById('save').onclick=async()=>{const v=token.value.trim();await chrome.storage.local.set({bridgeToken:v});try{const r=await fetch('http://127.0.0.1:38471/v1/tasks',{headers:{Authorization:'Bearer '+v}});status.textContent=r.ok?'연결됨':'토큰 확인 필요';status.style.color=r.ok?'#3fb950':'#f85149';}catch(e){status.textContent='NovaShorts가 실행 중인지 확인';status.style.color='#f85149';}};
