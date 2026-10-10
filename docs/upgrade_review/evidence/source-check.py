import requests,json,time,hashlib,re,concurrent.futures
from html.parser import HTMLParser
class Links(HTMLParser):
 def __init__(self): super().__init__(); self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':
   href=dict(attrs).get('href','')
   if any(x in href.lower() for x in ['.pdf','1968','1974','1978','1983','download','copyright','terms','stat_','szam','05300']):self.links.append(href)
urls=['https://epa.oszk.hu/05300/05300','https://www.kshkonyvtar.hu/article/4/290/szamitastechnikai-statisztikai-evkoenyv','https://web.kshkonyvtar.hu/article/89/1239/szamitastechnika-1969-1986','https://www.elibrary.imf.org/display/book/9781451963830/back-1.xml','https://www.ksh.hu/copyright_eng','https://statisztika.mnb.hu/sw/static/file/magyarorsza-g-pe-nzu-gyi-sza-mla-i-1970-1989-en.PDF']
def check(u):
 t=time.perf_counter()
 try:
  if u.lower().endswith('.pdf'):
   r=requests.head(u,timeout=25,allow_redirects=True);return dict(url=u,final_url=r.url,status=r.status_code,content_type=r.headers.get('Content-Type'),seconds=time.perf_counter()-t,method='HEAD',body_not_read=True)
  r=requests.get(u,timeout=25);s=r.text;p=Links();p.feed(s);title=re.search(r'<title[^>]*>(.*?)</title>',s,re.S|re.I)
  return dict(url=u,final_url=r.url,status=r.status_code,content_type=r.headers.get('Content-Type'),seconds=time.perf_counter()-t,title=title.group(1).strip() if title else None,body_sha256=hashlib.sha256(r.content).hexdigest(),links=p.links[:55])
 except Exception as e:return dict(url=u,error=str(e),seconds=time.perf_counter()-t)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(check,urls))
open('/private/tmp/hsm-source-check.json','w').write(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
