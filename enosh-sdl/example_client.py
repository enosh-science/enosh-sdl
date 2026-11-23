"""Run after starting server to demonstrate a third-party agent integration."""
from urllib.request import Request,urlopen
import json
payload={'observation':{'domain':'automation','text':'محتاج عرض سعر للعزل الصوتي',
                        'context':{'external_send':False}},
         'energy_weight':0.18}
data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
req=Request('http://127.0.0.1:8765/api/decide',data=data,
            headers={'Content-Type':'application/json; charset=utf-8'})
with urlopen(req,timeout=6) as resp:
    result=json.load(resp)
print(json.dumps(result,ensure_ascii=False,indent=2))
print('WARNING: This only returns a decision proposal; no tools executed.')
