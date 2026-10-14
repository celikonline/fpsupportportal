"""Exercise the running local API over HTTP with synthetic data; never prints credentials."""
import io
import json
import os
import time
import uuid
import http.cookiejar
import urllib.request
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parent.parent
config=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
base=os.environ.get('FP_SUPPORT_API_BASE', 'http://127.0.0.1:8000/api/v1/').rstrip('/') + '/'

class Client:
    def __init__(self,user):
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf=self.call('session')['csrfToken']
        result=self.call('auth/login',{'username':user,'password':config['DEMO_PASSWORD']})
        self.csrf=result['csrfToken']
    def call(self,path,body=None,headers=None,raw=False):
        headers={'X-CSRFToken':getattr(self,'csrf',''),'Content-Type':'application/json',**(headers or {})}
        request=urllib.request.Request(base+path,data=(json.dumps(body).encode() if isinstance(body,dict) else body),headers=headers)
        with self.opener.open(request,timeout=20) as result:
            value=result.read()
            return value if raw else json.loads(value)

customer=Client('customer');agent=Client('agent')
tenant=customer.call('me/tenants')[0]
project=customer.call(f"tenants/{tenant['id']}/projects")[0]
scope=f"tenants/{tenant['id']}/projects/{project['id']}"
draft=customer.call(scope+'/drafts',{})['id']
image=io.BytesIO();Image.new('RGB',(24,24),'#362dae').save(image,'PNG')
boundary='fp-'+uuid.uuid4().hex
body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="clipboard.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+image.getvalue()+f'\r\n--{boundary}--\r\n'.encode())
attachment=customer.call(scope+'/drafts/'+draft+'/uploads',body,{'Content-Type':'multipart/form-data; boundary='+boundary})
for _ in range(60):
    files=customer.call(scope+'/drafts/'+draft+'/uploads')
    if files[0]['state']=='clean': break
    if files[0]['state']=='rejected': raise SystemExit('FAIL: synthetic PNG rejected')
    time.sleep(1)
else: raise SystemExit('FAIL: scanner did not complete within 60 seconds')
ticket=customer.call(scope+'/tickets',{'title':'Sentetik HTTP akış testi','description':'Gerçek kullanıcı verisi içermez.','draftId':draft}, {'Idempotency-Key':str(uuid.uuid4())})
assert ticket['attachments'][0]['state']=='clean'
agent.call(scope+'/tickets/'+ticket['id']+'/comments',{'body':'PRIVATE-SMOKE-NOTE','visibility':'internal'},{'Idempotency-Key':str(uuid.uuid4())})
visible=customer.call(scope+'/tickets/'+ticket['id'])
assert 'PRIVATE-SMOKE-NOTE' not in json.dumps(visible)
download=customer.call(scope+'/attachments/'+attachment['id'],raw=True)
assert download.startswith(b'\x89PNG')
agent.call(scope+'/tickets/'+ticket['id']+'/comments',{'body':'Sentetik test yanıtı.','visibility':'public'},{'Idempotency-Key':str(uuid.uuid4())})
visible=customer.call(scope+'/tickets/'+ticket['id'])
assert len(visible['comments'])==1
print('PASS: session + CSRF, tenant/project selection, PNG upload, real scan, ticket creation, internal-note isolation, download and public reply.')
