import concurrent.futures, hashlib, json, pathlib, re
from urllib.parse import urljoin
import requests
urls = ['https://epa.oszk.hu/05300/05300/00012/pdf','https://epa.oszk.hu/05300/05300/00030/pdf','https://linopy.readthedocs.io/en/latest/prerequisites.html','https://linopy.readthedocs.io/en/latest/using-solvers.html','https://highs.dev/','https://pyomo.readthedocs.io/en/stable/getting_started/solvers.html','https://docs.astral.sh/uv/reference/cli/','https://pymrio.readthedocs.io/en/latest/intro.html','https://mesa.readthedocs.io/stable/index.html','https://docs.econ-ark.org/docs/guides/installation.html','https://salib.readthedocs.io/en/stable/user_guide/getting-started.html','https://pyabc.readthedocs.io/en/latest/installation.html','https://docs.pypsa.org/latest/home/installation/','https://www.v-dem.net/data/the-v-dem-dataset/']
def probe(url):
 try:
  r=requests.get(url,timeout=20)
  links=[urljoin(r.url,a) for a in re.findall(r'href=[\"\']([^\"\']+)',r.text) if '.pdf' in a.lower()]
  out={'url':url,'final_url':r.url,'status':r.status_code,'body_sha256':hashlib.sha256(r.content).hexdigest(),'pdf_links':links[:20]}
  if 'epa.oszk' in url and links:
   h=requests.head(links[0],allow_redirects=True,timeout=20)
   out['first_pdf_head']={'url':links[0],'status':h.status_code,'content_type':h.headers.get('Content-Type'),'length':h.headers.get('Content-Length')}
  if 'v-dem.net' in url:
   out['version_strings']=re.findall(r'.{0,30}(?:v16|Version 16|version 16).{0,60}',r.text)[:5]
  return out
 except Exception as e:return {'url':url,'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: results=list(ex.map(probe,urls))
pathlib.Path('/private/tmp/hsm-final-source-probe.json').write_text(json.dumps(results,indent=2))
for d in results: print(d)
