"""Questionnaire records and exports, separate from the legacy map survey."""
import csv
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from email.message import EmailMessage

QUESTIONNAIRES = json.loads((Path(__file__).parent/'data/entry_questionnaires.json').read_text())
def community(code):
    return 'Ga-Pila' if code.startswith('gapila_') else 'Armoede'

for original, guide in list(QUESTIONNAIRES.items()):
    text=json.dumps(guide,ensure_ascii=False).replace('Armoede / Ga-Sekhaolelo','Ga-Pila (Sterkwater)').replace('Ga-Sekhaolelo','Ga-Pila (Sterkwater)').replace('Armoede','Ga-Pila')
    adapted=json.loads(text)
    adapted['label']='Ga-Pila · '+adapted['label']
    if original in ('traditional','wardens'):
        additions={
          1: [('Who is authorised to activate and coordinate disaster arrangements at Bellevue Farm, and how should they report to the Ga-Pila structures?', 'Confirm farm management, trustees, Traditional Council and volunteer responsibilities.'),('How should Bellevue Farm incidents and decisions be recorded and escalated?', 'Identify reporting channels, alternates and records required.')],
          2: [('Which hazards and vulnerable assets at Bellevue Farm need priority prevention and early-warning measures?', 'Consider water, drought, veld fire, livestock, workers and production assets.'),('How should Bellevue Farm receive, verify and act on warnings and maintain preparedness?', 'Confirm warning sources, inspections, training, resources and responsibilities.')],
          3: [('What should trigger emergency activation at Bellevue Farm, and who should take the first safe actions?', 'Consider fire, injury, flooding, water-system failure and biosecurity incidents.'),('How should responders reach Bellevue Farm and coordinate evacuation, assistance and communication?', 'Confirm access routes, assembly points, specialist support and village–farm liaison.')],
          4: [('How should recovery and restoration of Bellevue Farm operations be prioritised after a disaster?', 'Consider water supply, access, livestock, infrastructure and production continuity.'),('How should Bellevue Farm damage, recovery needs and resilience improvements be assessed and tracked?', 'Identify records, responsible persons, funding referrals and safer rebuilding measures.')],
          5: [('How should Bellevue Farm readiness and SOP implementation be monitored and tested?', 'Identify drills, indicators, records, responsibilities and review frequency.'),('How should Bellevue Farm lessons and corrective actions inform the Ga-Pila SOP review?', 'Confirm feedback, approval, tracking and communication arrangements.')]
        }
        sections=list(dict.fromkeys(q['section'] for q in adapted['questions']))
        for number,section in enumerate(sections,1):
            for idx,(question,prompts) in enumerate(additions.get(number,[]),1):
                adapted['questions'].append({'id':f'BF{number}.{idx}','section':section,'question':question,'prompts':prompts})
    QUESTIONNAIRES['gapila_'+original]=adapted

META = ['Date and venue', 'Facilitator', 'Participants and roles', 'Session code', 'Stakeholder group']

def metadata_fields(code):
    return META + QUESTIONNAIRES[code].get('metadata_fields', [])

def new_entry(code):
    guide=QUESTIONNAIRES[code]
    return {'schema_version':1,'record_type':'focus_questionnaire','questionnaire_type':code,
            'response_id':str(uuid.uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),
            'metadata':{k:'' for k in metadata_fields(code)},'consent':False,
            'answers':{q['id']:'' for q in guide['questions']},
            'scenarios':{q['id']:'' for q in guide['scenarios']},
            'closing':{str(i):'' for i in range(1,4)},'actions':[]}

def validate_entry(raw):
    if not isinstance(raw,dict) or raw.get('record_type')!='focus_questionnaire' or raw.get('schema_version')!=1:
        raise ValueError('Choose a saved questionnaire-entry draft.')
    code=raw.get('questionnaire_type')
    if code not in QUESTIONNAIRES:raise ValueError('Unknown questionnaire type.')
    d=new_entry(code);d['response_id']=str(uuid.UUID(raw['response_id']))
    d['created_at']=str(raw.get('created_at',''))[:100];d['consent']=raw.get('consent') is True
    for group in ['metadata','answers','scenarios','closing']:
        if not isinstance(raw.get(group,{}),dict):raise ValueError('Invalid questionnaire fields.')
        for k in d[group]:d[group][k]=str(raw.get(group,{}).get(k,''))[:15000 if group!='metadata' else 500]
    if not isinstance(raw.get('actions',[]),list):raise ValueError('Invalid action table.')
    for row in raw.get('actions',[])[:50]:
        if not isinstance(row,dict):raise ValueError('Invalid action row.')
        clean={k:str(row.get(k,''))[:3000] for k in QUESTIONNAIRES[code]['action_columns']}
        if any(v.strip() for v in clean.values()):d['actions'].append(clean)
    d['participant']={'role':QUESTIONNAIRES[code]['label'],'mode':'Facilitated focus group','session_code':d['metadata']['Session code']}
    return d

def has_input(d):
    return any(str(v).strip() for group in ['answers','scenarios','closing'] for v in d[group].values()) or bool(d['actions'])

def entry_rows(records):
    rows=[]
    for d in records:
        guide=QUESTIONNAIRES[d['questionnaire_type']]
        base={'response_id':d['response_id'],'submitted_at':d.get('submitted_at',''),'questionnaire':guide['label'],**d['metadata']}
        for q in guide['questions']:
            rows.append({**base,'section':q['section'],'question':q['question'],'prompts':q['prompts'],'answer':d['answers'][q['id']]})
        for q in guide['scenarios']:
            rows.append({**base,'section':'Hazard scenario','question':q['question'],'prompts':q['prompts'],'answer':d['scenarios'][q['id']]})
        for i,q in enumerate(guide['closing'],1):rows.append({**base,'section':'Closing','question':q,'prompts':'','answer':d['closing'][str(i)]})
        for i,row in enumerate(d['actions'],1):rows.append({**base,'section':'Action recording','question':f'Action {i}','prompts':'','answer':json.dumps(row,ensure_ascii=False)})
    return rows

def entry_csv(records):
    rows=entry_rows(records)
    metadata=list(dict.fromkeys(META+[k for d in records for k in metadata_fields(d['questionnaire_type'])]))
    fields=['response_id','submitted_at','questionnaire',*metadata,'section','question','prompts','answer']
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader()
    for row in rows:
        writer.writerow({k:("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
    return output.getvalue().encode('utf-8-sig')

def build_entry_message(d,sender,recipient):
    guide=QUESTIONNAIRES[d['questionnaire_type']];msg=EmailMessage()
    msg['From']=sender;msg['To']=recipient
    msg['Subject']=f"{community(d['questionnaire_type'])} {guide['label']} response {d['response_id'][:8]}"
    msg['Message-ID']=f"<armoede-{d['response_id']}@gmail.com>"
    lines=[guide['label'],f"Response reference: {d['response_id']}",f"Submitted UTC: {d.get('submitted_at','')}"]
    lines += [f'{k}: {v}' for k,v in d['metadata'].items()]
    for row in entry_rows([d]):lines += ['',row['section'],row['question'],row['prompts'],row['answer'] or 'No answer recorded']
    msg.set_content('\n'.join(lines))
    msg.add_attachment(entry_csv([d]),maintype='text',subtype='csv',filename=community(d['questionnaire_type'])+'_questionnaire_answers.csv')
    msg.add_attachment(json.dumps(d,ensure_ascii=False,indent=2).encode(),maintype='application',subtype='json',filename=community(d['questionnaire_type'])+'_questionnaire_response.json')
    return msg
