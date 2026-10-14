import json
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from focus_core import QUESTIONNAIRES,new_entry,validate_entry,entry_csv
from notifications import build_message,deliver_response
from storage import Store
from test_notifications import FakeSMTP

ROOT=Path(__file__).resolve().parents[1]

def test_source_questionnaires_and_complete_email(tmp_path):
    for code,guide in QUESTIONNAIRES.items():
        assert [q['id'] for q in guide['questions']]==[str(i) for i in range(1,22)]
        assert len(guide['scenarios'])==6 and len(guide['closing'])==3
        d=new_entry(code);d['answers']['21']='Final readiness answer';d['scenarios']['6']='Mining incident answer'
        d['closing']['3']='Equipment and training';d['actions']=[{guide['action_columns'][0]:'Review action'}]
        d=validate_entry(d);d['submitted_at']='2026-10-14T20:30:00Z'
        store=Store(sqlite_path=tmp_path/f'{code}.db');store.save(d)
        with patch('notifications.smtplib.SMTP',FakeSMTP):
            assert deliver_response(store,d['response_id'],'dingaanm@gmail.com','testpassword')=='sent'
        body=build_message(d,'dingaanm@gmail.com').get_body(preferencelist=('plain',)).get_content()
        for value in ['Final readiness answer','Mining incident answer','Equipment and training','Review action']:assert value in body
        assert guide['label'].encode() in entry_csv([d])


def test_switch_restore_submit_and_dashboard(tmp_path,monkeypatch):
    monkeypatch.setenv('SQLITE_PATH',str(tmp_path/'entries.db'))
    monkeypatch.setenv('REQUIRE_DURABLE_STORAGE','false');monkeypatch.setenv('ADMIN_PASSWORD','testadmin')
    monkeypatch.delenv('DATABASE_URL',raising=False);monkeypatch.delenv('EMAIL_PASSWORD',raising=False)
    with patch('streamlit_folium.st_folium',return_value={}):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60).run()
        assert not at.exception
        assert at.tabs[0].label=='Questionnaire entries'
        for q in QUESTIONNAIRES['traditional']['questions']:
            assert any(q['prompts']==m.value for m in at.markdown)
        at.text_area(key='focus_traditional_answers_1').input('Council answer').run()
        at.radio(key='focus_choice').set_value('Wardens and General Stakeholders').run()
        for q in QUESTIONNAIRES['wardens']['questions']:
            assert any(q['prompts']==m.value for m in at.markdown)
        at.text_area(key='focus_wardens_answers_1').input('Warden answer').run()
        at.radio(key='focus_choice').set_value('Traditional Council').run()
        assert at.text_area(key='focus_traditional_answers_1').value=='Council answer'
        at.checkbox(key='focus_traditional_consent').check().run()
        at.button(key='focus_submit_traditional').click().run();assert not at.exception
        assert at.session_state['focus_receipt_traditional']['payload']['answers']['1']=='Council answer'
        # Restore callback must replace stale widget state and select the draft's group.
        at.session_state['restore_test']=json.dumps(new_entry('wardens'))
        from focus_view import _restore
        # Invoke restore inside the app's ScriptRunner context through a small harness.
        harness=tmp_path/'restore.py'
        harness.write_text("import sys\nsys.path.insert(0,"+repr(str(ROOT))+")\nimport streamlit as st\nfrom focus_core import new_entry\nfrom focus_view import _restore,render_entries\nfrom storage import Store\nst.session_state['focus_drafts']={c:new_entry(c) for c in ['traditional','wardens']}\nd=new_entry('wardens');d['answers']['1']='Restored warden';_restore(__import__('json').dumps(d))\nrender_entries(Store(sqlite_path="+repr(str(tmp_path/'restore.db'))+"),False,'','')\n")
        restored=AppTest.from_file(str(harness),default_timeout=60).run();assert not restored.exception
        assert restored.radio(key='focus_choice').value=='Wardens and General Stakeholders'
        assert restored.text_area(key='focus_wardens_answers_1').value=='Restored warden'
        at.radio[0].set_value('Facilitator dashboard').run()
        at.text_input[0].input('testadmin')
        next(b for b in at.button if b.label=='Unlock dashboard').click().run()
        next(s for s in at.selectbox if s.label=='Questionnaire to review').set_value('Traditional Council').run()
        assert not at.exception
        assert any('Council answer' in t.value for t in at.text)
