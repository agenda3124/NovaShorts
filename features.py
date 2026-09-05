from __future__ import annotations
import re, shutil, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from engine import tool, log


def _ff(args:list[str], check=True):
    ff = tool('ffmpeg')
    if not ff:
        raise RuntimeError('FFmpeg를 찾을 수 없습니다.')
    p = subprocess.run([ff] + args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and p.returncode:
        raise RuntimeError(p.stderr[-2500:] or 'FFmpeg 오류')
    return p


def video_duration(path:str)->float:
    p = _ff(['-i', path], check=False)
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', p.stderr)
    if not m:
        return 0.0
    h, mnt, sec = m.groups()
    return int(h)*3600 + int(mnt)*60 + float(sec)


def extract_thumbnail(video:str, output:str, at_seconds:float=1.0)->str:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    _ff(['-y','-ss',str(max(0, at_seconds)),'-i',video,'-frames:v','1','-vf','scale=1080:-2',str(out)])
    return str(out)


def _font(size:int):
    candidates = [
        r'C:\Windows\Fonts\malgunbd.ttf',
        r'C:\Windows\Fonts\malgun.ttf',
        r'C:\Windows\Fonts\arialbd.ttf',
    ]
    for p in candidates:
        if Path(p).exists():
            try:return ImageFont.truetype(p, size=size)
            except:pass
    return ImageFont.load_default()


def make_thumbnail(video:str, text:str, output:str, at_seconds:float=1.0)->str:
    out = Path(output)
    tmp = out.with_suffix('.frame.jpg')
    extract_thumbnail(video, str(tmp), at_seconds)
    im = Image.open(tmp).convert('RGB')
    if im.height < 1350:
        ratio = 1350 / im.height
        im = im.resize((int(im.width*ratio),1350))
    canvas = Image.new('RGB',(1080,1920),(15,18,28))
    ratio = max(1080/im.width, 1920/im.height)
    scaled = im.resize((int(im.width*ratio),int(im.height*ratio)))
    x=(scaled.width-1080)//2; y=(scaled.height-1920)//2
    canvas.paste(scaled.crop((x,y,x+1080,y+1920)),(0,0))
    draw=ImageDraw.Draw(canvas)
    lines=[]
    raw=(text or '').strip()
    if raw:
        chunk=12
        lines=[raw[i:i+chunk] for i in range(0,len(raw),chunk)][:3]
    font=_font(74)
    if lines:
        y0=1320
        for line in lines:
            box=draw.textbbox((0,0),line,font=font,stroke_width=4)
            tw=box[2]-box[0]; th=box[3]-box[1]
            tx=(1080-tw)//2
            draw.rounded_rectangle((tx-26,y0-18,tx+tw+26,y0+th+22),radius=18,fill=(0,0,0,150))
            draw.text((tx,y0),line,font=font,fill='white',stroke_width=4,stroke_fill='black')
            y0 += th+34
    out.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(out,quality=94)
    try:tmp.unlink()
    except:pass
    return str(out)


def auto_cut_vertical(video:str, output:str, target_seconds:float=18.0, clip_seconds:float=2.6, progress=None)->str:
    total=video_duration(video)
    if total <= 0:
        raise RuntimeError('영상 길이를 확인할 수 없습니다.')
    target=max(4.0,min(float(target_seconds),min(total,60.0)))
    clip=max(1.2,min(float(clip_seconds),5.0))
    n=max(1,min(8,round(target/clip)))
    usable=max(0.0,total-clip)
    starts=[0.0] if n==1 else [usable*i/(n-1) for i in range(n)]
    out=Path(output); out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='novashorts_cut_') as td:
        td=Path(td); clips=[]
        vf='scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black'
        for i,s in enumerate(starts):
            c=td/f'clip_{i:02d}.mp4'
            args=['-y','-ss',f'{s:.3f}','-t',f'{clip:.3f}','-i',video,'-vf',vf,'-c:v','libx264','-preset','veryfast','-crf','22','-c:a','aac','-b:a','160k',str(c)]
            p=_ff(args,check=False)
            if p.returncode:
                # fallback for silent/no-audio sources
                _ff(['-y','-ss',f'{s:.3f}','-t',f'{clip:.3f}','-i',video,'-vf',vf,'-an','-c:v','libx264','-preset','veryfast','-crf','22',str(c)])
            clips.append(c)
            if progress:progress(f'자동 컷 {i+1}/{n}')
        lst=td/'concat.txt'
        lst.write_text('\n'.join([f"file '{str(c).replace("'","''")}'" for c in clips]),encoding='utf-8')
        p=_ff(['-y','-f','concat','-safe','0','-i',str(lst),'-c','copy',str(out)],check=False)
        if p.returncode:
            _ff(['-y','-f','concat','-safe','0','-i',str(lst),'-c:v','libx264','-c:a','aac',str(out)])
    return str(out)
