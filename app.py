"""Armoede stakeholder survey with question linked map locations."""
import copy
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from streamlit_folium import st_folium
from survey_core import (QUESTIONS,SOPS,RATINGS,new_draft,validate_draft,inside_boundary,
                         add_location,submission_errors,csv_bytes,geojson_export,answer_rows)
from storage import Store
from map_view import survey_map

st.set_page_config(page_title='Armoede Community SOP Survey',page_icon='📍',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>
.block-container {max-width:1150px;padding-top:1.8rem;padding-bottom:2rem;}
h1 {font-size:2rem !important;letter-spacing:-.025em;}
.stButton button {min-height:48px;} textarea, input {font-size:16px !important;}
@media(max-width:768px){.block-container{padding:1rem .8rem;} h1{font-size:1.65rem !important;}
[data-testid="stHorizontalBlock"]{flex-direction:column !important;gap:.5rem;}
[data-testid="stColumn"]{width:100% !important;flex:1 1 100% !important;min-width:0 !important;}}
</style>''',unsafe_allow_html=True)

def setting(key,default=''):
    if key in os.environ:return os.environ[key]
    try:return st.secrets.get(key,default)
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError):return default

def is_true(value):return str(value).lower() in ('true','1','yes')
store=Store(str(setting('DATABASE_URL')),str(setting('SQLITE_PATH',str(Path(__file__).parent/'responses/armoede.sqlite3'))))
require_durable=is_true(setting('REQUIRE_DURABLE_STORAGE',True))
if 'draft' not in st.session_state:st.session_state.draft=new_draft()
if 'stage' not in st.session_state:st.session_state.stage=0
if 'pending' not in st.session_state:st.session_state.pending={}
if 'map_epoch' not in st.session_state:st.session_state.map_epoch={}


def password_gate(kind):
    expected_hash=str(setting(kind.upper()+'_PASSWORD_SHA256'))
    expected_plain=str(setting(kind.upper()+'_PASSWORD'))
    if not expected_hash and not expected_plain:
        if kind=='survey':return True
        st.info('The facilitator dashboard is locked until an administrator password is configured.');return False
    authkey=f'{kind}_authenticated'
    if st.session_state.get(authkey):return True
    now=time.time();lock_until=st.session_state.get(f'{kind}_locked_until',0)
    if now<lock_until:
        st.warning('Too many login attempts. Try again in a few minutes.');return False
    with st.form(f'{kind}_login'):
        entered=st.text_input('Facilitator password' if kind=='admin' else 'Survey access password',type='password')
        login=st.form_submit_button('Unlock dashboard' if kind=='admin' else 'Open survey',use_container_width=True)
    if login:
        ok=hmac.compare_digest(hashlib.sha256(entered.encode()).hexdigest(),expected_hash) if expected_hash else hmac.compare_digest(entered,expected_plain)
        if ok:
            st.session_state[authkey]=True;st.session_state[f'{kind}_attempts']=0;st.rerun()
        count=st.session_state.get(f'{kind}_attempts',0)+1;st.session_state[f'{kind}_attempts']=count
        if count>=5:
            st.session_state[f'{kind}_locked_until']=now+300;st.session_state[f'{kind}_attempts']=0
        st.error('The password is incorrect.')
    return False


def persist_answer(qid,field,key):st.session_state.draft['answers'][str(qid)][field]=st.session_state[key]
def persist_participant(field,key):st.session_state.draft['participant'][field]=st.session_state[key]
def persist_field(field,key):st.session_state.draft[field]=st.session_state[key]
def persist_rating(code,key):st.session_state.draft['ratings'][code]=st.session_state[key]
def persist_priority(index,key):st.session_state.draft['priorities'][index]=st.session_state[key]
def move(stage):st.session_state.stage=stage

def fresh_response():
    st.session_state.draft=new_draft();st.session_state.stage=0;st.session_state.pending={};st.session_state.map_epoch={}
    st.session_state.pop('submitted_receipt',None)
    for key in list(st.session_state):
        if key.startswith('w_'):del st.session_state[key]

def draft_download():
    st.download_button('Download my draft',json.dumps(st.session_state.draft,ensure_ascii=False,indent=2),
                       file_name='Armoede_survey_draft.json',mime='application/json',key=f'draft_dl_{st.session_state.stage}',use_container_width=True)
    st.caption('Your answers stay in this session while the page remains open. Download a draft before closing or refreshing, then restore it on the welcome screen.')


def input_value(key,value):
    if key not in st.session_state:st.session_state[key]=value


def attach(qid,lat,lon,label,category):
    try:
        add_location(st.session_state.draft,qid,lat,lon,label,category)
        st.session_state.pending.pop(str(qid),None)
        st.session_state.map_epoch[str(qid)]=st.session_state.map_epoch.get(str(qid),0)+1
        st.rerun()
    except ValueError as exc:st.error(str(exc))


def welcome():
    st.subheader('Tell us what would work in Armoede')
    st.write('Help improve the disaster procedures for Armoede / Ga-Sekhaolelo. Share your experiences, describe what needs to change, and mark relevant places inside the community boundary.')
    st.info('There are 12 questions. Answer those you can; locations are optional. For a focus group, a facilitator can enter the group’s views. This survey does not request emergency assistance.')
    st.caption('Do not enter household names, identification numbers, personal health details or private contact numbers. Pins identify places or concerns, not named vulnerable households. Candidate safe places still require verification.')
    with st.expander('Continue from a saved draft'):
        uploaded=st.file_uploader('Choose your Armoede survey draft JSON',type=['json'],key='draft_upload')
        if st.button('Restore draft',disabled=uploaded is None,use_container_width=True):
            try:
                if len(uploaded.getvalue())>2_000_000:raise ValueError('The draft file is too large.')
                restored=validate_draft(json.loads(uploaded.getvalue()))
                fresh_response();st.session_state.draft=restored;st.success('Draft restored.');st.rerun()
            except (ValueError,UnicodeDecodeError) as exc:st.error('Could not restore draft: '+str(exc))
    participant=st.session_state.draft['participant']
    roles=['Community member','Disaster management warden','Traditional leader','Local municipality','District disaster management','NGO or community organisation','Faith based organisation','Youth representative','Other stakeholder','Mixed focus group']
    modes=['Individual participant','Facilitated focus group']
    for field,label,options in [('mode','How are you answering?',modes),('role','Your stakeholder group',roles)]:
        key='w_'+field;input_value(key,participant[field] if participant[field] in options else options[0])
        st.selectbox(label,options,key=key,on_change=persist_participant,args=(field,key))
    for field,label in [('session_code','Session code or group reference if supplied'),('area','Street or area within Armoede optional'),('language','Preferred discussion language optional')]:
        key='w_'+field;input_value(key,participant[field]);st.text_input(label,key=key,on_change=persist_participant,args=(field,key))
    input_value('w_consent',st.session_state.draft['consent'])
    st.checkbox('I agree that my answers and selected locations may be recorded and reviewed by the Armoede engagement team to improve the SOPs.',key='w_consent',on_change=persist_field,args=('consent','w_consent'))
    st.button('Start the questions →',type='primary',disabled=not st.session_state.draft['consent'],on_click=move,args=(1,),use_container_width=True)


def question_page(qid):
    q=QUESTIONS[qid-1];answer=st.session_state.draft['answers'][str(qid)]
    st.progress(qid/12,text=f'Question {qid} of 12')
    st.subheader(q['question'])
    if qid in (7,8,9):
        with st.expander('Storm scenario for Questions 7 to 9',expanded=qid==7):
            st.write('Imagine a storm like the reported 13 November 2025 incident affecting Road One and New Stands. Roofing sheets and branches create danger, routes flood and learners are returning from school. Mobile communications are unreliable, some wardens are away and another is affected at home. What would happen today?')
            st.caption('Discuss safe alternatives. The draft SOP prohibits entering floodwater or unstable structures and reserves specialist tasks for competent responders.')
    with st.expander('Prompts to help your discussion'):
        st.write(q['probes'])
    left,right=st.columns([1,1],gap='large')
    with left:
        key=f'w_answer_{qid}';input_value(key,answer['text'])
        st.text_area('Your answer',height=200,key=key,placeholder='Describe what happens here, what works, and what is difficult…',max_chars=15000,on_change=persist_answer,args=(qid,'text',key))
        key=f'w_change_{qid}';input_value(key,answer['change'])
        st.text_area('What should change in the SOP or local arrangements? Optional',height=120,key=key,max_chars=15000,on_change=persist_answer,args=(qid,'change',key))
        st.caption('Linked procedure: '+q['sop_reference'])
    with right:
        st.markdown('**Mark a place for this answer**')
        st.caption('Tap or click inside the green boundary, describe the place, then attach it. You may add several places or leave the map blank.')
        pending=st.session_state.pending.get(str(qid));epoch=st.session_state.map_epoch.get(str(qid),0)
        m=survey_map(answer['locations'],pending)
        result=st_folium(m,height=360,use_container_width=True,key=f'location_map_{qid}_{epoch}',returned_objects=['last_clicked'])
        click=(result or {}).get('last_clicked')
        if click:
            st.session_state.pending[str(qid)]=click;pending=click
        if pending:
            valid=inside_boundary(pending['lat'],pending['lng'])
            if valid:st.caption(f"Selected: {pending['lat']:.6f}, {pending['lng']:.6f}")
            else:st.warning('That point is outside the Armoede boundary. Select a point inside the green outline.')
            label=st.text_input('Place name or short description',key=f'w_place_label_{qid}',max_chars=300)
            category=st.selectbox('Type of place',['Risk or concern','Blocked or unsafe access','Proposed assembly or shelter place','Resource or support point','Affected area','Other'],key=f'w_place_type_{qid}')
            if st.button('Attach selected place to this answer',disabled=not valid,use_container_width=True):attach(qid,pending['lat'],pending['lng'],label,category)
        with st.expander('Map not loading? Enter coordinates instead'):
            st.caption('Enter decimal degrees for a place inside Armoede. Locations are optional if you cannot identify coordinates. The map background needs an internet connection.')
            with st.form(f'manual_{qid}',clear_on_submit=True):
                lat=st.number_input('Latitude',value=-23.960000,format='%.6f',min_value=-90.,max_value=90.)
                lon=st.number_input('Longitude',value=28.990000,format='%.6f',min_value=-180.,max_value=180.)
                manual_label=st.text_input('Place description',max_chars=300)
                manual_add=st.form_submit_button('Attach coordinates',use_container_width=True)
            if manual_add:attach(qid,lat,lon,manual_label,'Other')
        for loc in list(answer['locations']):
            st.caption(f"📍 {loc['label']} · {loc['category']} · {loc['lat']:.6f}, {loc['lon']:.6f}")
            if st.button('Remove this place',key=f'remove_{loc["id"]}',use_container_width=True):
                answer['locations'][:]=[p for p in answer['locations'] if p['id']!=loc['id']]
                st.session_state.map_epoch[str(qid)]=epoch+1;st.session_state.pending.pop(str(qid),None);st.rerun()
    previous,next_=st.columns(2)
    previous.button('← Previous',on_click=move,args=(qid-1,),use_container_width=True)
    next_.button('Review my answers →' if qid==12 else 'Next question →',type='primary',on_click=move,args=(qid+1,),use_container_width=True)


def review():
    d=st.session_state.draft
    st.subheader('Review and identify the changes that matter most')
    answered=sum(bool(a['text'].strip() or a['change'].strip()) for a in d['answers'].values())
    pins=sum(len(a['locations']) for a in d['answers'].values())
    st.write(f'{answered} of 12 questions have written input · {pins} places attached. Unanswered questions are allowed.')
    for code,label in SOPS.items():
        key=f'w_rating_{code}';input_value(key,d['ratings'][code]);st.selectbox(f'{code} · {label}',RATINGS,key=key,on_change=persist_rating,args=(code,key))
    for i in range(3):
        key=f'w_priority_{i}';input_value(key,d['priorities'][i]);st.text_area(f'Priority change {i+1}',key=key,height=80,max_chars=15000,on_change=persist_priority,args=(i,key))
    for field,label in [('closing','Any concern or differing view not yet captured?'),('feedback_channel','How should the group receive feedback? Describe a channel, without private contact details.')]:
        key=f'w_{field}';input_value(key,d[field]);st.text_area(label,key=key,height=80,max_chars=300 if field=='feedback_channel' else 15000,on_change=persist_field,args=(field,key))
    with st.expander('Read all answers before submitting'):
        for q in QUESTIONS:
            a=d['answers'][str(q['id'])];st.markdown(f"**{q['id']}. {q['question']}**")
            st.text(a['text'] or 'No written answer');st.text('Suggested change: '+(a['change'] or 'None recorded'))
            for point in a['locations']:st.text(f"{point['label']} ({point['lat']:.6f}, {point['lon']:.6f})")
    st.download_button('Download my answers CSV',csv_bytes([d]),file_name='Armoede_my_answers.csv',mime='text/csv',use_container_width=True)
    st.download_button('Download my locations GeoJSON',json.dumps(geojson_export([d]),ensure_ascii=False,indent=2),file_name='Armoede_my_locations.geojson',mime='application/geo+json',use_container_width=True)
    can_submit=store.durable or not require_durable
    if not can_submit:
        st.info('Online collection is not yet configured. You can complete the survey and download your answers and draft. The organiser must configure a response database before server submission is enabled.')
    if st.button('Submit my response',type='primary',disabled=not can_submit,use_container_width=True):
        errors=submission_errors(d)
        if errors:
            for error in errors:st.error(error)
        else:
            payload=copy.deepcopy(d);payload['submitted_at']=datetime.now(timezone.utc).isoformat()
            try:
                inserted=store.save(payload)
                st.session_state.submitted_receipt={'response_id':payload['response_id'],'submitted_at':payload['submitted_at'],'inserted':inserted,'payload':payload if inserted else None}
                st.rerun()
            except Exception:
                st.error('The response could not be saved. Your answers are still here. Download a backup and try again or contact the facilitator.')
    st.button('← Return to Question 12',on_click=move,args=(12,),use_container_width=True)


def dashboard():
    if not password_gate('admin'):return
    if st.button('Lock dashboard',use_container_width=True):
        st.session_state.admin_authenticated=False;st.rerun()
    st.subheader('Facilitator dashboard')
    try:records=store.all()
    except Exception:
        st.error('Could not connect to the response database. Check the configured connection.');return
    st.caption('Submitted responses only. Participant drafts and personal session state are not visible here.')
    if not records:st.info('No submitted responses yet.');return
    roles=sorted({r['participant']['role'] for r in records})
    selected=st.multiselect('Filter stakeholder groups',roles)
    sessions=sorted({r['participant']['session_code'] for r in records if r['participant']['session_code']})
    selected_session=st.selectbox('Filter session',['All sessions']+sessions)
    filtered=[r for r in records if (not selected or r['participant']['role'] in selected) and (selected_session=='All sessions' or r['participant']['session_code']==selected_session)]
    st.metric('Responses in this selection',len(filtered))
    st.download_button('Export answers CSV',csv_bytes(filtered),file_name='Armoede_answers.csv',mime='text/csv',disabled=not filtered,use_container_width=True)
    st.download_button('Export mapped locations GeoJSON',json.dumps(geojson_export(filtered),ensure_ascii=False,indent=2),file_name='Armoede_locations.geojson',mime='application/geo+json',use_container_width=True)
    st.download_button('Export full response backup JSON',json.dumps(filtered,ensure_ascii=False,indent=2),file_name='Armoede_responses_backup.json',mime='application/json',use_container_width=True)
    qid=st.selectbox('Question to review',list(range(1,13)),format_func=lambda n:f"{n}. {QUESTIONS[n-1]['question']}")
    points=[]
    for r in filtered:
        for loc in r['answers'][str(qid)]['locations']:points.append(loc)
    st_folium(survey_map(points),use_container_width=True,height=430,key=f'admin_map_{qid}',returned_objects=[])
    st.caption('All pins are participant identified places requiring verification. Do not infer that a proposed shelter or route is safe.')
    rows=[r for r in answer_rows(filtered) if r['question_id']==qid]
    if rows:
        st.dataframe([{k:r[k] for k in ['response_id','role','session_code','answer','suggested_change','locations_count']} for r in rows],use_container_width=True,hide_index=True)
    st.markdown('**SOP fit ratings**')
    for code,label in SOPS.items():
        counts={rating:sum(r['ratings'][code]==rating for r in filtered) for rating in RATINGS}
        st.write(f'{code} · {label}');st.dataframe([{'Rating':k,'Responses':v} for k,v in counts.items()],hide_index=True,use_container_width=True)
    st.markdown('**Priority changes and remaining concerns**')
    for r in filtered:
        with st.expander(f"{r['participant']['role']} · {r['response_id'][:8]}"):
            for i,priority in enumerate(r['priorities']):st.text(f'{i+1}. {priority or "No priority recorded"}')
            st.text(r['closing'] or 'No additional concern')


st.caption('ARMOEDE COMMUNITY DEVELOPMENT TRUST · COMMUNITY ENGAGEMENT')
st.title('Armoede Community SOP Survey')
st.write('Your experience. Your places. Better disaster procedures.')
page=st.radio('Choose area',['Survey','Facilitator dashboard'],horizontal=True,label_visibility='collapsed')
if page=='Facilitator dashboard':dashboard()
elif password_gate('survey'):
    if not store.durable and not require_durable:
        st.warning('Local workshop storage is enabled. Responses are stored on this computer. Back up exports; this mode is not durable on Streamlit Cloud.')
    if 'submitted_receipt' in st.session_state:
        receipt=st.session_state.submitted_receipt
        st.success('Thank you. Your response was saved.' if receipt['inserted'] else 'This response was already submitted. No duplicate was created; the original submission was retained.')
        st.code(receipt['response_id'],language=None)
        st.caption('Keep this response reference for follow up. If this response was already submitted, edited draft answers have not replaced the original submission.')
        st.download_button('Download my submitted response JSON' if receipt['inserted'] else 'Download this session’s draft JSON',json.dumps(receipt['payload'] or st.session_state.draft,ensure_ascii=False,indent=2),file_name='Armoede_submitted_response.json' if receipt['inserted'] else 'Armoede_survey_draft.json',mime='application/json',use_container_width=True)
        st.button('Start a separate response',on_click=fresh_response,use_container_width=True)
    else:
        if not st.session_state.draft['consent']:st.session_state.stage=0
        stage=st.session_state.stage
        if stage==0:welcome()
        elif stage<=12:question_page(stage)
        else:review()
        st.divider();draft_download()
st.divider();st.caption('Developed by Dingaan Mahlangu · NCUMA Risk Management Consultancy. Based on the Armoede focus group guide and supplied Ga-Sekhaolelo boundary. This consultation supports SOP refinement and does not approve operational locations or replace emergency services.')
