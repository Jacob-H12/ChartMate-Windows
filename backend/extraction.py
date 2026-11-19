"""Conservative, offline label-based extraction. No diagnosis or inferred values."""
import re
FIELDS = [
('Identity','name','Name',r'patient name|name'),('Identity','parity','Parity',r'parity'),('Identity','labour_onset','Labour onset',r'labou?r onset'),('Identity','active_diagnosis','Active labour diagnosis (date)',r'active labou?r diagnosis'),('Identity','rupture','Ruptured membranes (date/time)',r'ruptured membranes|membrane rupture|rupture of membranes'),('Identity','risk','Risk factors',r'risk factors?'),
('Supportive care','companion','Companion',r'companion'),('Supportive care','pain','Pain relief',r'pain relief|analgesia'),('Supportive care','oral','Oral fluid',r'oral fluids?'),('Supportive care','posture','Posture',r'posture|maternal position'),
('Baby','fhr','Baseline FHR (bpm)',r'baseline (?:fhr|fetal heart rate|foetal heart rate)|fetal heart rate|foetal heart rate|fhr(?!\s+deceleration)'),('Baby','deceleration','FHR deceleration',r'fhr decelerations?|decelerations?'),('Baby','amniotic','Amniotic fluid',r'amniotic fluid'),('Baby','position','Fetal position',r'fetal position|foetal position'),('Baby','caput','Caput',r'caput'),('Baby','moulding','Moulding',r'moulding|molding'),
('Woman','pulse','Pulse (bpm)',r'maternal pulse|pulse|maternal heart rate'),('Woman','systolic','Systolic BP (mmHg)',r'systolic(?: blood pressure| bp)?'),('Woman','diastolic','Diastolic BP (mmHg)',r'diastolic(?: blood pressure| bp)?'),('Woman','temperature','Temperature (°C; verify units)',r'temperature'),('Woman','urine','Urine',r'urine'),
('Labour progress','contractions','Contractions per 10 min',r'contractions per (?:10|ten) minutes?|contraction frequency'),('Labour progress','duration','Duration of contractions (s)',r'duration of contractions?|contraction duration'),('Labour progress','cervix','Cervix (cm; X)',r'cervical dilatation|cervical dilation|cervix'),('Labour progress','descent','Descent (fifths palpable; O)',r'fetal descent|descent'),('Labour progress','pushing','Pushing begins (P)',r'pushing begins|pushing started'),
('Medication','oxytocin','Oxytocin (U/L, drops/min)',r'oxytocin'),('Medication','medicine','Medicine',r'medicines?|medications?'),('Medication','iv','IV fluids',r'iv fluids?|intravenous fluids?'),
('Shared decision-making','assessment','Assessment',r'assessment'),('Shared decision-making','plan','Plan',r'plan'),('Shared decision-making','initials','Initials',r'initials')]

TIME_PREFIX = re.compile(r"^(?:(?:it is|it[’']s|the time is|time is|time|at)\s*[:=]?\s*)?(?P<h>\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)(?::(?P<m>\d{2}))?\s*(?P<ampm>AM|PM)?(?=$|[\s,.:;])",re.I)
HOURS = dict(zip('one two three four five six seven eight nine ten eleven twelve'.split(),range(1,13)))

def time_prefix(clause):
    m=TIME_PREFIX.match(clause)
    if not m or not (m['ampm'] or m['m']):return clause,None,False
    h=HOURS.get(m['h'].lower()) if not m['h'].isdigit() else int(m['h'])
    minute=int(m['m'] or 0);period=m['ampm']
    if minute>59 or (period and not 1<=h<=12) or (not period and not 0<=h<=23):
        return clause,None,True
    if period:h=h%12+(12 if period.upper()=='PM' else 0)
    return clause[m.end():].lstrip(' ,.:;-'),f'{h:02d}:{minute:02d}',False


def extract(text):
    # Split at sentences / semicolons / lines, not decimals. Never resolve corrections silently.
    clean=re.sub(r'\[BLANK_AUDIO\]', '', text, flags=re.I)
    clean=re.sub(r'\b([ap])\.\s*m\.(?=\W|$)',lambda m:m[1].upper()+'M',clean,flags=re.I)
    clauses=re.split(r'[;\n]+|(?<=[.!?])\s+(?=[A-Za-z])',clean)
    candidates={};unmatched=[];warnings=[];times=[];time_sources=[];invalid_time=False
    if clean!=text:warnings.append("Audio markers were ignored and/or AM/PM spelling was normalized; the transcript was preserved.")
    patterns=[(key,re.compile(r'(?<!\w)(?:'+aliases+r')(?!\w)',re.I)) for _,key,_,aliases in FIELDS]
    for clause in clauses:
        clause=clause.strip()
        if not clause:continue
        if re.search(r'\b(?:correction|correct that|actually|instead|not sure|uncertain|maybe|possibly)\b',clause,re.I):
            unmatched.append(clause);warnings.append('Correction or uncertainty requires manual entry.');continue
        source=clause
        clause,observed_time,bad_time=time_prefix(clause)
        if bad_time:
            invalid_time=True;unmatched.append(source);warnings.append('Invalid observation time. Enter the time and values manually.');continue
        if observed_time:times.append(observed_time);time_sources.append(source)
        if not clause:continue
        clause=re.sub(r'^the\s+','',clause,flags=re.I)
        # A combined BP expression must be explicitly numeric; keep each original source.
        bp=re.fullmatch(r'(?:maternal )?(?:blood pressure|bp)\s*(?:is|:|=)?\s*(\d{2,3})\s*(?:/|over)\s*(\d{2,3})(?:\s*(?:mm\s*hg|millimet(?:er|re)s? of mercury))?[.]?',clause,re.I)
        if bp:
            for key,val in zip(('systolic','diastolic'),bp.groups()):candidates.setdefault(key,[]).append({'value':val,'source':source})
            continue
        matches=sorted([(m.start(),m.end(),key) for key,p in patterns for m in p.finditer(clause)])
        # Do not let narrative assessment/plan/medicine be split by clinical keywords.
        first=next((m for m in matches if m[0]==0),None)
        if first and first[2] in ('assessment','plan','medicine','risk'):matches=[first]
        if not matches:unmatched.append(source);continue
        if clause[:matches[0][0]].strip():
            unmatched.append(source);warnings.append('A field with preceding context was left for manual review.');continue
        for i,(a,b,key) in enumerate(matches):
            end=matches[i+1][0] if i+1<len(matches) else len(clause)
            val=clause[b:end].strip(' ,:;=.')
            val=re.sub(r'^(?:is|are|was|of)\s+','',val,flags=re.I).strip()
            val=re.sub(r'[, ]+and$','',val,flags=re.I).strip()
            if not val:unmatched.append(clause);continue
            candidates.setdefault(key,[]).append({'value':val,'source':source})
    result={}
    for key,items in candidates.items():
        vals=list(dict.fromkeys(x['value'] for x in items))
        if len(vals)>1:
            warnings.append('Multiple values for '+key+': choose the correct observation manually.')
            result[key]={'value':'','source':' | '.join(x['source'] for x in items),'conflict':True}
        else:result[key]={'value':vals[0],'source':' | '.join(dict.fromkeys(x['source'] for x in items)),'conflict':False}
    unique_times=list(dict.fromkeys(times))
    multiple=len(unique_times)>1
    if multiple:
        result={};unmatched=[c.strip() for c in clauses if c.strip()]
        warnings.append('Multiple observation times detected. Split the transcript into one time point per extraction; no values were assigned to avoid mixing observations.')
    observation_time=unique_times[0] if len(unique_times)==1 and not invalid_time else ''
    return {'fields':result,'unmatched':list(dict.fromkeys(unmatched)),'warnings':list(dict.fromkeys(warnings)),
            'observation_time':observation_time,'time_sources':time_sources,'time_conflict':multiple or invalid_time}

# Reference text copied from the user-supplied WHO form; not evaluated by this app.
ALERTS = {'companion':'N','pain':'N','oral':'N','posture':'SP','fhr':'<110, ≥160','deceleration':'L','amniotic':'M+++, B','position':'P, T','caput':'+++','moulding':'+++','pulse':'<60, ≥120','systolic':'<80, ≥140','diastolic':'≥90','temperature':'<35.0, ≥37.5','urine':'P++, A++','contractions':'≤2, >5','duration':'<20, >60','cervix':'No progress: 5 cm ≥6 h; 6 cm ≥5 h; 7 cm ≥3 h; 8 cm ≥2.5 h; 9 cm ≥2 h'}
