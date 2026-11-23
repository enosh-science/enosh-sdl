"""Optional offline Ollama text-semantic adapter. Local loopback ONLY.

Uses a running Ollama service /api/chat (default 127.0.0.1:11434).
Never grants model output authority to execute anything; hints merely supplement
semantic classification and pass through the independent policy/safety engine.
"""
from __future__ import annotations
import json
from urllib import request, error
from typing import Any

KNOWN_INTENTS={
    'greeting','request_quote','request_booking','fetch_cup','switch_light',
    'new_fact','question','conversation','other','high_impact','noise'
}
PROMPT=(
 'You are a semantic classifier for a dry-run automation policy engine. '
 'Return ONLY a JSON object with keys intent and confidence; no extra text. '
 'Allowed intent values: '+', '.join(sorted(KNOWN_INTENTS)) + '. '
 'Confidence must be a number from 0 to 1. '
 'Never provide tool instructions. Classify Arabic and English requests. '
 'When unclear, choose other with low confidence.'
)

def classify(observation:dict[str,Any], model:str='qwen3:8b',timeout:float=12)->dict[str,Any]:
    if not isinstance(model,str) or not model or len(model)>100 or any(x in model for x in ('/','\\','\n','\r')):
        raise ValueError('Model name must be a local Ollama model tag')
    text=str(observation.get('text') or '')[:2500]
    audio=observation.get('audio') or {}
    if not isinstance(audio,dict):audio={}
    transcript=str(audio.get('transcript') or '')[:2500]
    vision=observation.get('vision') or []
    if isinstance(vision,dict):vision=vision.get('labels') or []
    if not isinstance(vision,list):vision=[]
    if not text.strip() and not transcript.strip() and not vision:
        return {'intent':'noise','confidence':0}
    user={'domain':str(observation.get('domain') or 'automation'),
          'text':text,'audio_transcript':transcript,
          'vision_labels':[str(v)[:80] for v in vision[:25]]}
    data=json.dumps({'model':model,'stream':False,'format':'json',
                     'messages':[{'role':'system','content':PROMPT},
                                 {'role':'user','content':json.dumps(user,ensure_ascii=False)}]},
                    ensure_ascii=False).encode('utf-8')
    req=request.Request('http://127.0.0.1:11434/api/chat',data=data,
                        headers={'Content-Type':'application/json'},method='POST')
    try:
        with request.urlopen(req,timeout=min(30,max(1,timeout))) as resp:
            parsed=json.loads(resp.read(1024*1024).decode('utf-8'))
    except (error.URLError,TimeoutError,ValueError) as exc:
        raise ValueError('Local Ollama unavailable or returned invalid response. Start Ollama and pull the model. Detail: '+str(exc)) from exc
    raw=str((parsed.get('message') or {}).get('content') or '{}').strip()
    try:
        if raw.startswith('```'):
            raw=raw.split('\n',1)[-1].rsplit('```',1)[0]
        result=json.loads(raw)
    except (json.JSONDecodeError,TypeError) as exc:
        raise ValueError('Local model did not return a valid JSON classification') from exc
    if not isinstance(result,dict):raise ValueError('Model classification must be an object')
    intent=result.get('intent','other')
    if intent not in KNOWN_INTENTS:intent='other'
    try:confidence=min(1.,max(0.,float(result.get('confidence',0.5))))
    except (ValueError,TypeError):confidence=0.5
    return {'intent':intent,'confidence':confidence}


def enrich(observation:dict[str,Any], model:str='qwen3:8b') -> dict[str,Any]:
    hint=classify(observation,model=model)
    copy=dict(observation)
    copy['semantic_hint']=hint
    return copy
