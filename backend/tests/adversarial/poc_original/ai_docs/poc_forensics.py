import os, sys, io
os.environ["JWT_SECRET"]="x"*40
B=r"C:\Users\aizag\Desktop\ai hackathon\team-repo\backend"
sys.path.insert(0,B)
import numpy as np
from PIL import Image, ImageFilter
from app.documents import forensics, imaging, indicators
raw=open(B+r"\sample_docs\death_certificate_aslam_edited.png","rb").read()
base=imaging.load(raw).image
def rep(label,img):
    r=forensics.analyse(img,{})[0]
    print(f"{label:55s} found={r.copy_move.found!s:5} ncc={r.copy_move.score} cands={r.copy_move.stamp_candidates} screenshot={r.looks_like_screenshot} ela_p99={r.ela_p99}")
    return r
r0=rep("original edited PNG (baseline)",base)
reg=r0.copy_move.regions
def jpeg(img,q):
    b=io.BytesIO(); img.save(b,"JPEG",quality=q); return Image.open(io.BytesIO(b.getvalue())).convert("RGB")
for q in (85,60,40,25): rep(f"JPEG q{q}",jpeg(base,q))
# attacker tweaks only the pasted stamp (second region)
x0,y0,x1,y1=reg[1]
def tweak_second(angle=0,scale=1.0,shift=(0,0)):
    img=base.copy()
    pad=12
    box=(max(0,x0-pad),max(0,y0-pad),x1+pad,y1+pad)
    crop=img.crop(box)
    bg=img.crop((box[0],box[1],box[2],box[3]))
    w,h=crop.size
    c=crop.rotate(angle,resample=Image.BICUBIC,fillcolor=(255,255,255))
    if scale!=1.0:
        c=c.resize((int(w*scale),int(h*scale)),Image.BICUBIC)
    img.paste(c,(box[0]+shift[0],box[1]+shift[1]))
    return img
for a in (1,2,3,5,10): rep(f"pasted stamp rotated {a} deg",tweak_second(angle=a))
for s in (0.9,1.1,1.25,0.7): rep(f"pasted stamp scaled x{s}",tweak_second(scale=s))
rep("pasted stamp rotated 3 + whole JPEG q70",jpeg(tweak_second(angle=3),70))
# hue shift of the pasted stamp
arr=np.asarray(base).astype(np.int16)
im=base.copy().convert("HSV"); a=np.asarray(im).copy()
a[y0:y1,x0:x1,0]=(a[y0:y1,x0:x1,0].astype(int)+20)%256
rep("pasted stamp hue shifted (different ink colour bin)",Image.fromarray(a,"HSV").convert("RGB"))
# re-photograph simulation
def rephoto(img):
    w,h=img.size
    im=img.filter(ImageFilter.GaussianBlur(1.1))
    n=np.asarray(im).astype(np.float32)+np.random.RandomState(1).normal(0,6,(h,w,3))
    return Image.fromarray(np.clip(n,0,255).astype(np.uint8)).rotate(1.5,fillcolor=(235,235,235))
rep("re-photograph sim (blur+noise+rot)",rephoto(base))
# missing exif never penalised / edit software tag only info
r=indicators.from_forensics(forensics.ForensicReport(r0.copy_move,r0.ela_mean,r0.ela_p99,{"software":"Adobe Photoshop"},False))
print("EXIF Photoshop tag severity:",[ (i.code,i.severity) for i in r if i.code=="EDIT_SOFTWARE_TAG"])
