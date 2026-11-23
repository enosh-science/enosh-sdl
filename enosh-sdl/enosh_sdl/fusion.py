"""Transparent *proxy* multimodal semantic fusion (v0.3).

Text and audio transcripts use lightweight keyword matches for offline demonstration.
Vision is a list of tags produced elsewhere; sensors are numeric readings.
Not an ASR engine, visual model, language model, or proof of 'understanding'.

v0.3 change: cues are matched on *tokens* (with a small, explicit set of Arabic
proclitics/enclitics) instead of raw substrings. This removes false positives such
as 'خطر' inside 'أخطر' or 'hi' inside 'which', while keeping 'الكوباية', 'اشرحلي',
'ابعتلي' etc. Gates for deletion and external sending are deliberately conservative:
a false positive yields human review, never an autonomous action.
"""
from __future__ import annotations
import re
from typing import Any

AR_DIACRITICS = re.compile('[ً-ٰٟ]')
TOKEN_RE = re.compile(r'[^\W_]+|[؟?]', re.UNICODE)

def normalize(text: str) -> str:
    text = AR_DIACRITICS.sub('', text.lower()).replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي')
    return re.sub(r'\s+', ' ', text).strip()

def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(normalize(text))

# Explicit affix inventory (kept small and auditable; no stemming library).
AR_PREFIXES = ('', 'و', 'ف', 'ب', 'ل', 'ك', 'ال', 'وال', 'فال', 'بال', 'كال', 'لل', 'ولل')
AR_SUFFIXES = ('', 'ه', 'ة', 'ات', 'ها', 'هم', 'هن', 'ك', 'كم', 'ي', 'لي', 'له', 'لها', 'لنا', 'نا', 'وا', 'ين', 'ون', 'ش')

def _token_match(token: str, cue: str) -> bool:
    if token == cue:
        return True
    if not re.search('[؀-ۿ]', cue):      # Latin cue: exact token only
        return False
    for p in AR_PREFIXES:
        if not token.startswith(p):
            continue
        rest = token[len(p):]
        for s in AR_SUFFIXES:
            if rest == cue + s:
                return True
    return False

CUES = {
    'greeting': ('مرحبا','اهلا','صباح الخير','ازيك','hello','hi','hey'),
    'price': ('سعر','تكلفه','تكلفة','بكام','عرض سعر','price','quote','quotation','cost'),
    'booking': ('احجز','حجز','معاينه','معاينة','ميعاد','موعد','book','booking','appointment'),
    'cup': ('كوب','كوبايه','كوباية','cup','mug'),
    'water': ('مياه','ميه','مايه','مبلول','water','liquid','full'),
    'bring': ('هات','جيب','احضر','bring','fetch','pick up'),
    'light': ('نور','اضاءه','اضاءة','lights','light on','switch on'),
    'question': ('؟','?','اشرح','ليه','ازاي','why','how','what'),
    'new_fact': ('معلومه جديده','معلومة جديدة','اكتشاف','نتيجه جديده','نتيجة جديدة','new finding','new fact'),
    'danger': ('خطر','حريق','دخان','طوارئ','اصطدام','danger','fire','smoke','collision','emergency'),
    # Conservative: any deletion verb triggers review (false positives cost a review, not an action).
    'delete': ('احذف','حذف','امسح','مسح','delete','erase','wipe','remove'),
    # Conservative: any outbound-send/publish verb triggers review.
    'send': ('ابعت','ابعث','ارسل','انشر','send','email','e-mail','publish','post','forward','share'),
    'money': ('حول فلوس','تحويل اموال','تحويل فلوس','حوالة','حواله','دفع','ادفع','transfer money','payment','bank transfer','wire','pay'),
}

_CUE_PARTS: dict[str, list[str]] = {}

def _parts(cue: str) -> list[str]:
    if cue not in _CUE_PARTS:
        _CUE_PARTS[cue] = tokenize(cue) or [normalize(cue)]
    return _CUE_PARTS[cue]

def _has(tokens: list[str], variants: tuple[str, ...]) -> bool:
    for cue in variants:
        parts = _parts(cue)
        n = len(parts)
        for i in range(len(tokens) - n + 1):
            if all(_token_match(tokens[i+j], parts[j]) for j in range(n)):
                return True
    return False

def fuse(observation: dict[str, Any]) -> dict[str, Any]:
    text = str(observation.get('text', '') or '')[:4000]
    audio = observation.get('audio') or {}
    if not isinstance(audio, dict): audio = {}
    transcript = str(audio.get('transcript', '') or '')[:4000]
    combined = normalize(' '.join((text, transcript)))
    tokens = tokenize(combined)
    tags = observation.get('vision') or []
    if isinstance(tags, dict): tags = tags.get('labels') or []
    tags = [normalize(str(t)) for t in tags if isinstance(t, str)][:40] if isinstance(tags, list) else []
    sensors = observation.get('sensors') or {}
    if not isinstance(sensors, dict): sensors = {}
    context = observation.get('context') or {}
    if not isinstance(context, dict): context = {}
    domain = str(observation.get('domain') or 'automation').lower()
    if domain not in ('automation','presenter','robot'): domain='automation'
    cues = {key: _has(tokens, values) for key,values in CUES.items()}
    tagset=set(tags)
    if any(t in tagset for t in ('cup','mug','كوباية','كوب')): cues['cup']=True
    if any(t in tagset for t in ('water','liquid','مياه')): cues['water']=True
    if any(t in tagset for t in ('fire','smoke','حريق','دخان')): cues['danger']=True

    channel_conf=[]
    if text.strip(): channel_conf.append(float(observation.get('text_confidence',0.94)))
    if transcript.strip(): channel_conf.append(float(audio.get('confidence',0.80)))
    if tags: channel_conf.append(float(observation.get('vision_confidence',0.78)))
    if sensors: channel_conf.append(float(observation.get('sensor_confidence',0.92)))
    confidence = min(1.0, max(0.0, sum(channel_conf)/len(channel_conf) if channel_conf else 0.0))
    explicit = observation.get('confidence')
    if explicit is not None: confidence = max(0.,min(1., float(explicit)))
    hazard = bool(sensors.get('emergency_stop',False)) or bool(sensors.get('fire_alarm',False))
    obstacle = sensors.get('obstacle_distance_m',None)
    if domain=='robot' and isinstance(obstacle,(int,float)) and not isinstance(obstacle,bool) and obstacle<0.28:
        hazard=True
    if cues['danger']: hazard=True

    intent='other'
    if cues['delete'] or cues['money']: intent='high_impact'
    elif cues['bring'] and cues['cup']: intent='fetch_cup'
    elif cues['price']: intent='request_quote'
    elif cues['booking']: intent='request_booking'
    elif cues['light']: intent='switch_light'
    elif cues['new_fact']: intent='new_fact'
    elif cues['question']: intent='question'
    elif cues['greeting']: intent='greeting'
    if domain=='presenter' and intent=='other' and (combined or tags): intent='conversation'
    if not combined and not tags and not sensors: intent='noise'
    # Optional adapter output is untrusted; do not allow it to erase hard
    # safety/impact cues, nor invent a command when no evidence exists.
    hint=observation.get('semantic_hint') or {}
    allowed={'greeting','request_quote','request_booking','fetch_cup','switch_light',
             'new_fact','question','conversation','other','high_impact','noise'}
    if isinstance(hint,dict) and intent!='high_impact' and intent!='noise' and not hazard:
        label=hint.get('intent')
        if label in allowed and label!='noise':
            intent=label
            try:
                hint_conf=float(hint.get('confidence',.5))
                confidence=min(confidence,max(0.,min(1.,hint_conf)))
            except (TypeError,ValueError): pass
    modality_count = sum((bool(text.strip()),bool(transcript.strip()),bool(tags),bool(sensors)))
    return {'domain':domain,'intent':intent,'confidence':round(confidence,4),
            'hazard':hazard,'cues':cues,'vision_tags':tags,
            'outbound_request':cues['send'],
            'modality_count':modality_count,'context':context,
            'text_excerpt':combined[:160],
            'evidence':{'text':bool(text.strip()),'audio_transcript':bool(transcript.strip()),
                        'vision_labels':tags,'sensor_keys':sorted(sensors)}}
