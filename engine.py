from __future__ import annotations

import asyncio, hashlib, hmac, json, os, re, secrets, shutil, subprocess, sys, time, urllib.parse, webbrowser
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable

import requests

APP_NAME='NovaShorts'
APP_VERSION='1.20'
HOME=Path.home()/'.novashorts'
SETTINGS_FILE=HOME/'settings.json'
LOG_FILE=HOME/'logs'/'novashorts.log'
DEFAULT_OUTPUT=Path.home()/'Videos'/'NovaShorts'

PLATFORMS={
 'Douyin':'site:douyin.com/video',
 'Xiaohongshu':'site:xiaohongshu.com/explore',
 'Kuaishou':'site:kuaishou.com/short-video',
 'TikTok':'site:tiktok.com/@ /video/',
 '1688':'site:1688.com',
}

@dataclass
class Settings:
 output_folder:str=str(DEFAULT_OUTPUT)
 gemini_api_key:str=''
 coupang_access_key:str=''
 coupang_secret_key:str=''
 min_similarity:int=55
 auto_skip_low_similarity:bool=True
 use_gemini_query_planning:bool=True
 platform_sources:list[str]|None=None
 youtube_client_secret_file:str=''
 youtube_auto_upload:bool=False
 youtube_upload_interval:int=60
 youtube_title_prompt:str=''
 youtube_description_prompt:str=''
 youtube_hashtag_prompt:str=''
 youtube_comment_enabled:bool=False
 youtube_comment_prompt:str=''
 youtube_privacy:str='private'
 x_account_name:str=''
 lnkbio_client_id:str=''
 lnkbio_client_secret:str=''
 lnkbio_profile_url:str=''
 lnkbio_auto_publish:bool=False
 watermark_enabled:bool=False
 watermark_text:str=''
 watermark_position:str='bottom_right'
 subtitle_overlay:bool=True
 subtitle_position:str='bottom_center'
 subtitle_custom_y:int=80
 tts_voice:str='ko-KR-SunHiNeural'
 tts_rate:str='+0%'
 whisper_model:str='base'
 pipeline_remove_subtitles:bool=True
 pipeline_auto_cut:bool=True
 pipeline_add_korean_subtitles:bool=True
 pipeline_auto_thumbnail:bool=True
 pipeline_target_seconds:int=20
 bridge_token:str=''
 def __post_init__(self):
  if self.platform_sources is None:self.platform_sources=list(PLATFORMS)
  if not self.bridge_token:self.bridge_token=secrets.token_urlsafe(24)

def ensure_dirs():
 HOME.mkdir(parents=True,exist_ok=True);(HOME/'logs').mkdir(parents=True,exist_ok=True);DEFAULT_OUTPUT.mkdir(parents=True,exist_ok=True)

def log(msg:str):
 ensure_dirs(); line=f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
 with LOG_FILE.open('a',encoding='utf-8') as f:f.write(line+'\n')

def load_settings()->Settings:
 ensure_dirs()
 if not SETTINGS_FILE.exists():
  s=Settings();save_settings(s);return s
 try:
  raw=json.loads(SETTINGS_FILE.read_text(encoding='utf-8')); allowed=Settings.__dataclass_fields__.keys()
  return Settings(**{k:v for k,v in raw.items() if k in allowed})
 except Exception as e:log(f'settings load: {e}');return Settings()

def save_settings(s:Settings):
 ensure_dirs();SETTINGS_FILE.write_text(json.dumps(asdict(s),ensure_ascii=False,indent=2),encoding='utf-8')

def app_dir()->Path:
 if getattr(sys,'frozen',False):return Path(sys.executable).parent
 return Path(__file__).resolve().parent

def tool(name:str)->str|None:
 candidates=[]; base=app_dir()
 if name=='ffmpeg':candidates += [base/'ffmpeg.exe',base/'tools'/'ffmpeg.exe']
 if name=='ffprobe':candidates += [base/'ffprobe.exe',base/'tools'/'ffprobe.exe']
 if name=='tesseract':candidates += [base/'tesseract'/'tesseract.exe',Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe')]
 for p in candidates:
  if Path(p).exists():return str(p)
 return shutil.which(name)

def diagnostics()->dict:
 try:
  import yt_dlp; yd=True
 except Exception:yd=False
 try:
  import cv2; cv=True
 except Exception:cv=False
 try:
  import faster_whisper; fw=True
 except Exception:fw=False
 model_dir=app_dir()/'models'/'whisper-base'
 return {'ffmpeg':bool(tool('ffmpeg')),'ffprobe':bool(tool('ffprobe')),'tesseract':bool(tool('tesseract')),'yt_dlp':yd,'opencv':cv,'faster_whisper':fw,'whisper_model':model_dir.exists(),'chrome_bridge':True}

def normalize_title(t:str)->str:
 t=re.sub(r'\[[^\]]+\]|\([^\)]+\)',' ',t);t=re.sub(r'\b(무료배송|로켓배송|당일배송|정품|국내배송)\b',' ',t,flags=re.I)
 return re.sub(r'\s+',' ',t).strip()

def tokens(t:str)->list[str]:return [x for x in re.findall(r'[가-힣A-Za-z0-9一-龥ぁ-んァ-ン]+',t.lower()) if len(x)>1]

def rule_query_plan(title:str)->dict[str,list[str]]:
 base=' '.join(tokens(normalize_title(title))[:7]) or title
 return {'Douyin':[base,base+' 测评',base+' 使用'],'Xiaohongshu':[base,base+' 好物',base+' 测评'],'Kuaishou':[base,base+' 使用',base+' 推荐'],'TikTok':[base,base+' review',base+' demo'],'1688':[base,base+' 视频',base+' 详情']}

def gemini_query_plan(title:str,key:str)->dict[str,list[str]]:
 if not key:return rule_query_plan(title)
 prompt='Return JSON only with keys Douyin, Xiaohongshu, Kuaishou, TikTok, 1688. Each value must contain 3 concise product video search strings. Use Simplified Chinese for Chinese platforms and English for TikTok. Product: '+title
 try:
  r=requests.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',params={'key':key},json={'contents':[{'parts':[{'text':prompt}]}]},timeout=30);r.raise_for_status()
  text=r.json()['candidates'][0]['content']['parts'][0]['text'];text=re.sub(r'^```(?:json)?|```$','',text.strip(),flags=re.M).strip();d=json.loads(text)
  return {p:[str(x) for x in d.get(p,[])][:3] for p in PLATFORMS}
 except Exception as e:log('Gemini fallback: '+str(e));return rule_query_plan(title)

def direct_search_url(p:str,q:str)->str:
 x=urllib.parse.quote(q)
 return {'Douyin':f'https://www.douyin.com/search/{x}?type=video','Xiaohongshu':f'https://www.xiaohongshu.com/search_result?keyword={x}&source=web_search_result_notes','Kuaishou':f'https://www.kuaishou.com/search/video?searchKey={x}','TikTok':f'https://www.tiktok.com/search/video?q={x}','1688':f'https://s.1688.com/selloffer/offer_search.htm?keywords={x}'}[p]

def external_search_url(p:str,q:str)->str:return 'https://www.google.com/search?q='+urllib.parse.quote_plus(PLATFORMS[p]+' '+q)

def relevance(product:str,candidate:str)->int:
 a=set(tokens(product));b=set(tokens(candidate))
 if not a or not b:return 0
 exact=len(a&b)/len(a);partial=sum(1 for x in a if any(x in y or y in x for y in b))/len(a)
 return max(0,min(100,round((exact*.65+partial*.35)*100)))

def coupang_search(keyword:str,access:str,secret:str,limit:int=10)->dict:
 if not access or not secret:raise RuntimeError('쿠팡 Access/Secret Key를 설정하세요.')
 path='/v2/providers/affiliate_open_api/apis/openapi/products/search'
 query=urllib.parse.urlencode({'keyword':keyword,'limit':limit})
 method='GET';dt=time.strftime('%y%m%dT%H%M%SZ',time.gmtime())
 message=dt+method+path+query
 signature=hmac.new(secret.encode(),message.encode(),hashlib.sha256).hexdigest()
 auth=f'CEA algorithm=HmacSHA256, access-key={access}, signed-date={dt}, signature={signature}'
 r=requests.get('https://api-gateway.coupang.com'+path+'?'+query,headers={'Authorization':auth},timeout=20);r.raise_for_status();return r.json()

def download_video(url:str,out_dir:str,progress:Callable[[str],None]|None=None)->Path:
 import yt_dlp
 out=Path(out_dir);out.mkdir(parents=True,exist_ok=True);before=set(out.iterdir())
 def hook(d):
  if progress and d.get('status')=='downloading':progress('다운로드 '+d.get('_percent_str','').strip())
 opts={'outtmpl':str(out/'%(title).120s_%(id)s.%(ext)s'),'noplaylist':True,'merge_output_format':'mp4','quiet':True,'no_warnings':True}
 ff=tool('ffmpeg')
 if ff:opts['ffmpeg_location']=str(Path(ff).parent)
 with yt_dlp.YoutubeDL(opts) as y:y.download([url])
 after=[p for p in out.iterdir() if p not in before and p.suffix.lower() in {'.mp4','.webm','.mkv','.mov'}]
 if not after:after=sorted([p for p in out.iterdir() if p.suffix.lower() in {'.mp4','.webm','.mkv','.mov'}],key=lambda p:p.stat().st_mtime,reverse=True)
 if not after:raise RuntimeError('다운로드 결과 파일이 없습니다.')
 return sorted(after,key=lambda p:p.stat().st_mtime,reverse=True)[0]

def _run_ffmpeg(args:list[str]):
 ff=tool('ffmpeg')
 if not ff:raise RuntimeError('FFmpeg를 찾을 수 없습니다.')
 p=subprocess.run([ff]+args,capture_output=True,text=True,encoding='utf-8',errors='replace')
 if p.returncode:raise RuntimeError(p.stderr[-2500:])

def media_duration(path:str)->float:
 probe=tool('ffprobe')
 if probe:
  p=subprocess.run([probe,'-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',path],capture_output=True,text=True,encoding='utf-8',errors='replace')
  try:return float((p.stdout or '').strip())
  except Exception:pass
 p=subprocess.run([tool('ffmpeg') or 'ffmpeg','-i',path],capture_output=True,text=True,encoding='utf-8',errors='replace')
 m=re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)',p.stderr or '')
 if not m:return 0.0
 h,mn,s=m.groups();return int(h)*3600+int(mn)*60+float(s)

def extract_frames(video:str,out_dir:str,fps=.5)->list[Path]:
 o=Path(out_dir);o.mkdir(parents=True,exist_ok=True);_run_ffmpeg(['-y','-i',video,'-vf',f'fps={fps}',str(o/'frame_%05d.jpg')]);return sorted(o.glob('frame_*.jpg'))

def tesseract_text(img:str,lang='chi_sim+kor+eng')->str:
 exe=tool('tesseract')
 if not exe:raise RuntimeError('Tesseract를 찾을 수 없습니다.')
 env=os.environ.copy(); td=Path(exe).parent/'tessdata'
 if td.exists():env['TESSDATA_PREFIX']=str(td)
 p=subprocess.run([exe,img,'stdout','-l',lang,'--psm','6'],capture_output=True,text=True,encoding='utf-8',errors='replace',env=env)
 if p.returncode:raise RuntimeError(p.stderr[-1200:])
 return p.stdout

def subtitle_scan(video:str,workdir:str,progress=None)->list[dict]:
 frames=extract_frames(video,str(Path(workdir)/'frames'),.5);hits=[]
 for i,f in enumerate(frames):
  try:text=re.sub(r'\s+',' ',tesseract_text(str(f))).strip()
  except Exception as e:log('OCR '+str(e));continue
  if text:hits.append({'frame':str(f),'time':i*2.0,'text':text,'chinese':bool(re.search(r'[一-龥]',text))})
  if progress and i%4==0:progress(f'OCR {i+1}/{len(frames)}')
 return hits

def cleanup_bottom_subtitles(video:str,out:str,y_percent:int=62):
 yp=max(40,min(90,y_percent));y=f'ih*{yp}/100';fc=f'[0:v]split=2[b][c];[c]crop=iw:ih-{y}:0:{y},boxblur=12:2[bl];[b][bl]overlay=0:{y}'
 _run_ffmpeg(['-y','-i',video,'-filter_complex',fc,'-c:a','copy',out]);return out

async def _tts(text,voice,out,rate='+0%'):
 import edge_tts;await edge_tts.Communicate(text,voice,rate=rate).save(out)
def generate_tts(text,voice,out,rate='+0%'):asyncio.run(_tts(text,voice,out,rate));return out

def compose_vertical(video:str,audio:str|None,out:str):
 args=['-y']
 if audio:args += ['-stream_loop','-1','-i',video,'-i',audio,'-map','0:v:0','-map','1:a:0','-shortest']
 else:args += ['-i',video]
 args += ['-vf','scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black','-c:v','libx264','-preset','medium','-crf','20','-c:a','aac','-b:a','192k',out]
 _run_ffmpeg(args);return out

def watermark(video,text,out,pos='bottom_right'):
 xy={'bottom_right':'x=w-tw-40:y=h-th-40','bottom_left':'x=40:y=h-th-40','top_right':'x=w-tw-40:y=40','top_left':'x=40:y=40','center':'x=(w-tw)/2:y=(h-th)/2'}.get(pos,'x=w-tw-40:y=h-th-40')
 safe=text.replace("'","\\'").replace(':','\\:');vf=f"drawtext=text='{safe}':fontcolor=white:fontsize=30:borderw=2:bordercolor=black@0.6:{xy}"
 _run_ffmpeg(['-y','-i',video,'-vf',vf,'-c:a','copy',out]);return out

def youtube_upload(video,secret_file,title,description,tags,privacy='private')->str:
 from google_auth_oauthlib.flow import InstalledAppFlow
 from googleapiclient.discovery import build
 from googleapiclient.http import MediaFileUpload
 scopes=['https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.force-ssl'];creds=InstalledAppFlow.from_client_secrets_file(secret_file,scopes).run_local_server(port=0);yt=build('youtube','v3',credentials=creds)
 body={'snippet':{'title':title,'description':description,'tags':tags,'categoryId':'22'},'status':{'privacyStatus':privacy,'selfDeclaredMadeForKids':False}}
 req=yt.videos().insert(part='snippet,status',body=body,media_body=MediaFileUpload(video,chunksize=-1,resumable=True));resp=None
 while resp is None:_,resp=req.next_chunk()
 return resp['id']

def lnk_bio_add(cid,secret,title,url)->dict:
 t=requests.post('https://lnk.bio/oauth/token',data={'grant_type':'client_credentials','client_id':cid,'client_secret':secret},timeout=20);t.raise_for_status();access=t.json().get('access_token')
 r=requests.post('https://lnk.bio/oauth/v1/lnk/add',headers={'Authorization':f'Bearer {access}'},data={'title':title,'url':url},timeout=20);r.raise_for_status();return r.json()

def open_x(text):webbrowser.open('https://x.com/intent/post?text='+urllib.parse.quote(text))
