import json,bisect,sys
from PIL import Image
r=sys.argv[1]; out=sys.argv[2]; times=[float(x) for x in sys.argv[3:]]
fr=[json.loads(l) for l in open(f'{r}/frames.jsonl')]
ts=[f['ts'] for f in fr]
t0=json.loads(open(f'{r}/events.jsonl').readline())['t']
imgs=[]
for t in times:
    j=max(0,bisect.bisect_right(ts,t0+t)-1)
    imgs.append(Image.open(f"{r}/{fr[j]['file']}").convert('RGB').resize((1000,562)))
cols=2; rows=(len(imgs)+1)//2
s=Image.new('RGB',(1000*cols,562*rows),'white')
for k,im in enumerate(imgs): s.paste(im,((k%cols)*1000,(k//cols)*562))
s.save(out,quality=82)
