import csv
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest
from focus_core import new_entry,validate_entry,entry_csv,build_entry_message
from storage import Store

ROOT=Path(__file__).resolve().parents[1]


def test_municipality_choices_keep_independent_answers_and_legacy_entries(tmp_path,monkeypatch):
    monkeypatch.setenv('SQLITE_PATH',str(tmp_path/'municipal.db'))
    monkeypatch.setenv('REQUIRE_DURABLE_STORAGE','false')
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.delenv('EMAIL_PASSWORD',raising=False)
    with patch('streamlit_folium.st_folium',return_value={}):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        assert not at.exception
        assert at.radio(key='municipality_choice').options==['District Municipality','Local Municipality']
        at.text_area(key='focus_traditional_answers_1').input('Council input').run()
        at.text_area(key='focus_district_answers_1').input('District supports Armoede assessments').run()
        at.radio(key='municipality_choice').set_value('Local Municipality').run()
        at.text_area(key='focus_local_answers_1').input('Local drainage maintenance').run()
        at.radio(key='municipality_choice').set_value('District Municipality').run()
        assert at.text_area(key='focus_district_answers_1').value=='District supports Armoede assessments'
        assert at.text_area(key='focus_traditional_answers_1').value=='Council input'
        at.radio(key='municipality_choice').set_value('Local Municipality').run()
        assert at.text_area(key='focus_local_answers_1').value=='Local drainage maintenance'
        assert not at.exception


@pytest.mark.parametrize('code,label',[('district','District Municipality'),('local','Local Municipality')])
def test_municipal_submission_exports_and_dashboard(tmp_path,monkeypatch,code,label):
    db=tmp_path/f'{code}.db'
    monkeypatch.setenv('SQLITE_PATH',str(db));monkeypatch.setenv('REQUIRE_DURABLE_STORAGE','false')
    monkeypatch.setenv('ADMIN_PASSWORD','testadmin')
    monkeypatch.delenv('DATABASE_URL',raising=False);monkeypatch.delenv('EMAIL_PASSWORD',raising=False)
    with patch('streamlit_folium.st_folium',return_value={}):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        at.radio(key='municipality_choice').set_value(label).run()
        at.text_area(key=f'focus_{code}_answers_21').input('Joint Armoede exercise and review').run()
        at.checkbox(key=f'focus_{code}_consent').check().run()
        at.button(key=f'focus_submit_{code}').click().run()
        assert any('Enter the municipality' in e.value for e in at.error)
        at.text_area(key=f'focus_{code}_metadata_Municipality or disaster management centre').input('Test municipal institution').run()
        at.text_area(key=f'focus_{code}_metadata_Department or function').input('Disaster management').run()
        at.text_area(key=f'focus_{code}_scenarios_6').input('Refer Armoede pollution concern').run()
        at.button(key=f'focus_submit_{code}').click().run()
        assert not at.exception
        saved=Store(sqlite_path=db).all()
        assert len(saved)==1 and saved[0]['questionnaire_type']==code
        assert saved[0]['participant']['role']==label
        row=next(r for r in csv.DictReader(io.StringIO(entry_csv(saved).decode('utf-8-sig'))) if r['answer']=='Joint Armoede exercise and review')
        assert row['Municipality or disaster management centre']=='Test municipal institution'
        assert row['Department or function']=='Disaster management'
        body=build_entry_message(saved[0],'sender@example.com','recipient@example.com').get_body(preferencelist=('plain',)).get_content()
        assert 'Refer Armoede pollution concern' in body
        assert 'Test municipal institution' in body
        at.radio[0].set_value('Facilitator dashboard').run()
        at.text_input[0].input('testadmin')
        next(b for b in at.button if b.label=='Unlock dashboard').click().run()
        next(s for s in at.selectbox if s.label=='Questionnaire to review').set_value(label).run()
        assert not at.exception
        assert any('Joint Armoede exercise and review' in t.value for t in at.text)


@pytest.mark.parametrize('code,label',[('district','District Municipality'),('local','Local Municipality')])
def test_restore_municipal_draft_selects_matching_choice_and_preserves_other_group(tmp_path,code,label):
    d=new_entry(code);d['answers']['1']='Restored municipal answer'
    d['metadata']['Municipality or disaster management centre']='Restored institution'
    script=tmp_path/'restore_municipal.py'
    script.write_text('import sys,json\nsys.path.insert(0,'+repr(str(ROOT))+')\n'
        'import streamlit as st\nfrom focus_core import new_entry\nfrom focus_view import _restore,render_entries\nfrom storage import Store\n'
        'st.session_state["focus_drafts"]={c:new_entry(c) for c in ["traditional","wardens","district","local"]}\n'
        'st.session_state["focus_drafts"]["traditional"]["answers"]["1"]="Retained council answer"\n'
        '_restore('+repr(json.dumps(d))+',["district","local"],"municipality_restore_notice")\n'
        'render_entries(Store(sqlite_path='+repr(str(tmp_path/'restore.db'))+'),False,"","",questionnaire_code="municipality")\n')
    at=AppTest.from_file(str(script),default_timeout=30).run()
    assert not at.exception
    assert at.radio(key='municipality_choice').value==label
    assert at.text_area(key=f'focus_{code}_answers_1').value=='Restored municipal answer'
    assert at.session_state['focus_drafts']['traditional']['answers']['1']=='Retained council answer'
    assert at.text_area(key=f'focus_{code}_metadata_Municipality or disaster management centre').value=='Restored institution'
    assert validate_entry(d)['metadata']['Municipality or disaster management centre']=='Restored institution'
