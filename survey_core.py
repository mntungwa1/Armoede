"""Validation and portable exports for the Armoede engagement survey."""
import csv
import io
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / 'data/questions.json').read_text(encoding='utf-8'))
BOUNDARY = json.loads((ROOT / 'data/armoede_boundary.geojson').read_text(encoding='utf-8'))
RING = BOUNDARY['features'][0]['geometry']['coordinates'][0]
RATINGS = ['Not enough information to judge', 'Workable now', 'Workable with changes', 'Not workable under current conditions']
SOPS = {'D2.1': 'Governance and coordination', 'D2.2': 'Prevention, preparedness and warnings', 'D2.3': 'Emergency response and safe support', 'D2.4': 'Relief, recovery and Build Back Better'}

def inside_boundary(lat, lon):
    """Ray casting including edges; coordinates always lat, lon at this interface."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(lat) or not math.isfinite(lon):
        return False
    inside = False
    for (x1,y1),(x2,y2) in zip(RING, RING[1:]):
        cross = (lon-x1)*(y2-y1)-(lat-y1)*(x2-x1)
        if abs(cross) < 1e-10 and min(x1,x2)-1e-10 <= lon <= max(x1,x2)+1e-10 and min(y1,y2)-1e-10 <= lat <= max(y1,y2)+1e-10:
            return True
        if (y1 > lat) != (y2 > lat) and lon < (x2-x1)*(lat-y1)/(y2-y1)+x1:
            inside = not inside
    return inside

def new_draft():
    return {'schema_version': 1, 'survey_version': 'Armoede focus group guide 2026-10-13',
            'response_id': str(uuid.uuid4()), 'created_at': datetime.now(timezone.utc).isoformat(),
            'participant': {'role': 'Community member', 'mode': 'Individual participant', 'session_code': '', 'area': '', 'language': ''},
            'consent': False, 'answers': {str(q['id']): {'text': '', 'change': '', 'locations': []} for q in QUESTIONS},
            'ratings': {code: RATINGS[0] for code in SOPS}, 'priorities': ['', '', ''], 'closing': '', 'feedback_channel': ''}

def add_location(draft, qid, lat, lon, label='', category='Risk or concern'):
    if not inside_boundary(lat, lon):
        raise ValueError('Choose a point inside the supplied Armoede boundary.')
    locations = draft['answers'][str(qid)]['locations']
    if len(locations) >= 20:
        raise ValueError('Up to 20 locations can be attached to each question.')
    lat, lon = round(float(lat),6), round(float(lon),6)
    if any(abs(p['lat']-lat)<1e-6 and abs(p['lon']-lon)<1e-6 for p in locations):
        raise ValueError('This location is already attached to this question.')
    point = {'id': str(uuid.uuid4()), 'lat':lat, 'lon':lon, 'label': str(label).strip()[:300] or f'Location {len(locations)+1}', 'category':category}
    locations.append(point)
    return point

def validate_draft(raw):
    """Allow only this schema when restoring a downloaded draft."""
    if not isinstance(raw,dict) or raw.get('schema_version') != 1:
        raise ValueError('This is not a supported Armoede survey draft.')
    result = new_draft()
    try:
        result['response_id'] = str(uuid.UUID(raw['response_id']))
        result['created_at'] = str(raw['created_at'])[:100]
        for field in result['participant']:
            result['participant'][field] = str(raw.get('participant',{}).get(field,result['participant'][field]))[:300]
        result['consent'] = raw.get('consent') is True
        for q in QUESTIONS:
            a=raw.get('answers',{}).get(str(q['id']),{})
            result['answers'][str(q['id'])]['text']=str(a.get('text',''))[:15000]
            result['answers'][str(q['id'])]['change']=str(a.get('change',''))[:15000]
            for loc in a.get('locations',[]):
                add_location(result,q['id'],loc['lat'],loc['lon'],loc.get('label',''),loc.get('category','Risk or concern'))
        for code in SOPS:
            rating=raw.get('ratings',{}).get(code,RATINGS[0])
            if rating not in RATINGS:raise ValueError('Invalid SOP rating.')
            result['ratings'][code]=rating
        priorities=raw.get('priorities',['','',''])
        result['priorities']=[str(x)[:15000] for x in (priorities+['','',''])[:3]]
        result['closing']=str(raw.get('closing',''))[:15000]
        result['feedback_channel']=str(raw.get('feedback_channel',''))[:300]
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('The draft contains invalid fields.') from exc
    return result

def submission_errors(draft):
    errors=[]
    if not draft.get('consent'):errors.append('Confirm consent before submitting.')
    if not any(a['text'].strip() or a['change'].strip() for a in draft['answers'].values()):
        errors.append('Add a written answer or suggested change to at least one question.')
    for a in draft['answers'].values():
        if any(not inside_boundary(p['lat'],p['lon']) for p in a['locations']):
            errors.append('A selected location falls outside the Armoede boundary.')
    return errors

def answer_rows(records):
    rows=[]
    for record in records:
        for q in QUESTIONS:
            a=record['answers'][str(q['id'])]
            rows.append({'response_id':record['response_id'],'submitted_at':record.get('submitted_at',''),
                         **record['participant'],'question_id':q['id'],'question':q['question'],
                         'sop_reference':q['sop_reference'],'answer':a['text'],'suggested_change':a['change'],
                         'locations_count':len(a['locations']), 'locations_json':json.dumps(a['locations'],ensure_ascii=False),
                         **{f'rating_{k}':v for k,v in record['ratings'].items()},
                         **{f'priority_{i+1}':v for i,v in enumerate(record['priorities'])},
                         'closing':record['closing'],'feedback_channel':record['feedback_channel']})
    return rows

def csv_bytes(records):
    rows=answer_rows(records)
    if not rows:return b''
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader()
    # Protect spreadsheets against formula injection in participant text.
    for row in rows:
        writer.writerow({k:("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
    return out.getvalue().encode('utf-8-sig')

def geojson_export(records):
    features=[]
    for record in records:
        for q in QUESTIONS:
            a=record['answers'][str(q['id'])]
            for loc in a['locations']:
                features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[loc['lon'],loc['lat']]},
                                 'properties':{'response_id':record['response_id'],'question_id':q['id'],'question':q['question'],
                                               'answer':a['text'],'suggested_change':a['change'],'sop_reference':q['sop_reference'],
                                               'label':loc['label'],'category':loc['category'],'verification_status':'Participant identified; requires verification'}})
    return {'type':'FeatureCollection','features':features}
