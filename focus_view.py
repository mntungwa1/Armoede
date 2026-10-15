"""First-tab questionnaire entry and facilitator review."""
import copy
import json
from datetime import datetime, timezone
import streamlit as st
from focus_core import QUESTIONNAIRES,META,new_entry,validate_entry,has_input,entry_csv,entry_rows
from notifications import deliver_response


def _keep(code,group,field,key):
    st.session_state['focus_drafts'][code][group][field]=st.session_state[key]

def _text(code,group,field,label,help_text=None):
    d=st.session_state['focus_drafts'][code];key=f'focus_{code}_{group}_{field}'
    if key not in st.session_state:st.session_state[key]=d[group][field]
    st.text_area(label,key=key,height=100,max_chars=500 if group=='metadata' else 15000,
                 help=help_text,on_change=_keep,args=(code,group,field,key))
    d[group][field]=st.session_state[key]


def _restore(data):
    try:
        if len(data)>2_000_000:raise ValueError('Draft is too large.')
        d=validate_entry(json.loads(data));code=d['questionnaire_type']
        st.session_state['focus_drafts'][code]=d
        st.session_state['focus_choice']=QUESTIONNAIRES[code]['label']
        for k in list(st.session_state):
            if k.startswith(f'focus_{code}_'):del st.session_state[k]
        st.session_state.pop('focus_receipt_'+code,None)
        st.session_state['focus_restore_notice']='Questionnaire draft restored. Review the entries below.'
    except (ValueError,TypeError,KeyError,UnicodeDecodeError):
        st.session_state['focus_restore_notice']='Could not restore this file. Choose a valid questionnaire-entry draft JSON.'


def render_entries(store,require_durable,email_sender,email_password):
    st.subheader('Questionnaire entries')
    st.write('Choose the group you are recording. Each choice keeps its own answers while you work.')
    if 'focus_drafts' not in st.session_state:st.session_state['focus_drafts']={c:new_entry(c) for c in QUESTIONNAIRES}
    with st.expander('Continue from a saved questionnaire draft'):
        upload=st.file_uploader('Choose questionnaire draft JSON',type=['json'],key='focus_upload')
        st.button('Restore questionnaire draft',key='focus_restore',disabled=upload is None,on_click=_restore,args=(upload.getvalue() if upload else b'',))
        if st.session_state.get('focus_restore_notice'):st.info(st.session_state['focus_restore_notice'])
    label=st.radio('Questionnaire',['Traditional Council','Wardens and General Stakeholders'],horizontal=True,key='focus_choice')
    code=next(c for c,g in QUESTIONNAIRES.items() if g['label']==label);guide=QUESTIONNAIRES[code]
    d=st.session_state['focus_drafts'][code]
    receipt=st.session_state.get('focus_receipt_'+code)
    if receipt:
        st.success('This questionnaire is recorded. Reference: '+receipt['response_id'])
        status=receipt['email_status'];st.info('Email status: '+status)
        if status=='sent':st.success('Gmail accepted your questionnaire for delivery to dingaanm@gmail.com. Check Inbox and Spam.')
        elif status!='not_configured':
            detail=store.email_statuses().get(receipt['response_id'],{}).get('detail')
            if detail:st.warning(detail)
        else:st.warning('Email is not configured. Add EMAIL_ADDRESS and EMAIL_PASSWORD in Streamlit Secrets to enable submission emails.')
        if status in ['failed','pending'] and email_password:
            if st.button('Retry questionnaire email',key='focus_retry_'+code):
                receipt['email_status']=deliver_response(store,receipt['response_id'],email_sender,email_password);st.rerun()
        st.download_button('Download submitted questionnaire',json.dumps(receipt['payload'],ensure_ascii=False,indent=2),file_name=f'Armoede_{code}_submitted.json',mime='application/json',key='focus_submitted_'+code,on_click='ignore')
        if st.button('Start another questionnaire',key='focus_new_'+code):
            st.session_state['focus_drafts'][code]=new_entry(code);st.session_state.pop('focus_receipt_'+code,None)
            for k in list(st.session_state):
                if k.startswith(f'focus_{code}_'):del st.session_state[k]
            st.rerun()
        return
    st.caption('Ga-Sekhaolelo · 21 main questions · six hazard scenarios · closing and action records')
    if code=='wardens':st.info('General stakeholders may answer from their own role and experience. If a question refers to Warden training you have not received, say so or leave it unanswered.')
    with st.expander('Purpose and facilitation guidance'):
        st.write(guide['purpose']);st.write(guide['opening']);st.write(guide['approach'])
    st.caption('Record group-level views. Do not enter private contact details, household names or sensitive personal information. Use your separate attendance register for participant identities.')
    for field in META:_text(code,'metadata',field,field+' (optional)')
    for section in dict.fromkeys(q['section'] for q in guide['questions']):
        with st.expander(section,expanded=section==guide['questions'][0]['section']):
            for q in guide['questions']:
                if q['section']!=section:continue
                with st.container(border=True):
                    main_column,prompt_column=st.columns(2,gap='large')
                    with main_column:
                        st.markdown('**Main question**')
                        st.write(f"{q['id']}. {q['question']}")
                    with prompt_column:
                        st.markdown('**Follow-up questions / prompts**')
                        st.write(q['prompts'])
                    _text(code,'answers',q['id'],'Answer '+q['id']+' — include the follow-up questions')
    with st.expander('Priority hazard scenarios'):
        st.write(guide['scenario_instruction'])
        for q in guide['scenarios']:
            scenario_column,prompt_column=st.columns(2,gap='large')
            with scenario_column:
                st.markdown('**Priority hazard scenario**');st.write(q['question'])
            with prompt_column:
                st.markdown('**Input to capture**');st.write(q['prompts'])
            _text(code,'scenarios',q['id'],'Scenario response '+q['id'])
    with st.expander('Closing questions'):
        for i,q in enumerate(guide['closing'],1):_text(code,'closing',str(i),q)
    with st.expander('Facilitator action-recording table'):
        st.caption('Capture agreed actions, triggers, responsibilities, contacts, records and matters still needing confirmation. Scroll across the table on a phone.')
        import pandas as pd
        frame=pd.DataFrame(d['actions'],columns=guide['action_columns'])
        edited=st.data_editor(frame,num_rows='dynamic',hide_index=True,key=f'focus_{code}_table',use_container_width=True)
        d['actions']=[{k:('' if pd.isna(v) else str(v)[:3000]) for k,v in row.items()} for row in edited.to_dict('records') if any(not pd.isna(v) and str(v).strip() for v in row.values())][:50]
    consent_key=f'focus_{code}_consent'
    if consent_key not in st.session_state:st.session_state[consent_key]=d['consent']
    d['consent']=st.checkbox('I agree that these entries may be recorded, emailed to dingaanm@gmail.com and reviewed by the Armoede engagement team for SOP development.',key=consent_key)
    st.download_button('Download questionnaire draft',json.dumps(d,ensure_ascii=False,indent=2),file_name=f'Armoede_{code}_draft.json',mime='application/json',key='focus_draft_'+code,on_click='ignore')
    st.download_button('Download questionnaire answers CSV',entry_csv([d]),file_name=f'Armoede_{code}_answers.csv',mime='text/csv',key='focus_csv_'+code,on_click='ignore')
    ready=store.durable or not require_durable or bool(email_sender and email_password)
    if not ready:st.info('Submission will be enabled when the organiser configures database storage or email collection. You can download your draft now.')
    if st.button('Submit questionnaire entries',type='primary',key='focus_submit_'+code,disabled=not ready):
        if not d['consent']:st.error('Confirm consent before submitting.')
        elif not has_input(d):st.error('Record at least one answer, scenario, closing response or action before submitting.')
        else:
            payload=validate_entry(copy.deepcopy(d));payload['submitted_at']=datetime.now(timezone.utc).isoformat()
            try:
                inserted=store.save(payload);original=payload if inserted else store.get(payload['response_id'])
                status=deliver_response(store,payload['response_id'],email_sender,email_password) if email_sender and email_password else 'not_configured'
                st.session_state['focus_receipt_'+code]={'response_id':payload['response_id'],'payload':original,'email_status':status};st.rerun()
            except Exception:st.error('Could not save the questionnaire. Your entries remain here. Download a draft and try again.')
    st.caption('On Streamlit Cloud, local copies may be temporary unless a response database is configured. Email status “sent” means Gmail accepted the message.')


def render_entry_dashboard(records):
    st.download_button('Export questionnaire answers CSV',entry_csv(records),file_name='Armoede_questionnaire_answers.csv',mime='text/csv',key='focus_admin_csv')
    st.download_button('Export questionnaire backup JSON',json.dumps(records,ensure_ascii=False,indent=2),file_name='Armoede_questionnaire_backup.json',mime='application/json',key='focus_admin_json')
    for r in records:
        with st.expander(f"{r['metadata'].get('Session code') or 'Session not specified'} · {r['response_id'][:8]}"):
            st.write(r['metadata']);st.caption(r.get('submitted_at',''))
            for row in entry_rows([r]):
                st.markdown('**'+row['question']+'**');st.text(row['answer'] or 'No answer recorded')
