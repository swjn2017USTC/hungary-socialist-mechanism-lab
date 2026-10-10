import requests,json,concurrent.futures
from html.parser import HTMLParser
from urllib.parse import urljoin
class A(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,t,a):
  if t=='a':
   h=dict(a).get('href','')
   if '.pdf' in h.lower() or h.lower().endswith('/pdf'):self.links.append(h)
base='https://epa.oszk.hu'
urls=[base+f'/html/vgi/kardexlap.phtml?aktev={y}&id=5300' for y in [1960,1965,1968,1970,1973,1975,1978,1980,1985]]
rows=[]
for u in urls:
 try:
  r=requests.get(u,timeout=20);p=A();p.feed(r.text);rows.append({'url':u,'status':r.status_code,'pdf_links':[urljoin(u,l) for l in p.links]})
 except Exception as e:rows.append({'url':u,'error':str(e)})
ks=json.load(open('/private/tmp/hsm-source-check.json'))[1]['links']; selected=[urljoin('https://www.kshkonyvtar.hu',l) for i,l in enumerate(ks) if i in [2,5,7,10]]
def head(u):
 try:
  r=requests.head(u,allow_redirects=True,timeout=20);return {'url':u,'status':r.status_code,'content_type':r.headers.get('Content-Type'),'content_length':r.headers.get('Content-Length')}
 except Exception as e:return {'url':u,'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p: heads=list(p.map(head,selected))
out={'epa_years':rows,'ksh_computing_pdf_headers':heads};open('/private/tmp/hsm-source-follow.json','w').write(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
