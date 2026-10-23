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
CASES=[('provincial','Provincial Government (DM)',{'Province':'Test province','Provincial centre or department':'Test provincial centre'}),('ndmc','National Disaster Management Centre',{'NDMC unit or function':'Test national coordination unit'})]


@pytest.mark.parametrize('code,label,institution',CASES)
def test_government_tab_submission_and_dashboard(tmp_path,monkeypatch,code,label,institution):
    db=tmp_path/f'{code}.db'
    monkeypatch.setenv('SQLITE_PATH',str(db));monkeypatch.setenv('REQUIRE_DURABLE_STORAGE','false')
    monkeypatch.setenv('ADMIN_PASSWORD','testadmin')
    monkeypatch.delenv('DATABASE_URL',raising=False);monkeypatch.delenv('EMAIL_PASSWORD',raising=False)
    with patch('streamlit_folium.st_folium',return_value={}):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=40).run()
        assert not at.exception
        assert label in [t.label for t in at.tabs]
        at.text_area(key='focus_traditional_answers_1').input('Retained council input').run()
        at.text_area(key=f'focus_{code}_answers_21').input('Armoede joint review and follow-up').run()
        at.text_area(key=f'focus_{code}_scenarios_6').input('Coordinate specialist environmental referral').run()
        at.checkbox(key=f'focus_{code}_consent').check().run()
        at.button(key=f'focus_submit_{code}').click().run()
        assert any('required institution details' in e.value for e in at.error)
        for field,value in institution.items():
            at.text_area(key=f'focus_{code}_metadata_{field}').input(value).run()
        assert at.text_area(key='focus_traditional_answers_1').value=='Retained council input'
        at.button(key=f'focus_submit_{code}').click().run()
        assert not at.exception
        records=Store(sqlite_path=db).all()
        assert len(records)==1 and records[0]['questionnaire_type']==code
        assert records[0]['participant']['role']==label
        assert 'focus_receipt_'+('ndmc' if code=='provincial' else 'provincial') not in at.session_state
        row=next(r for r in csv.DictReader(io.StringIO(entry_csv(records).decode('utf-8-sig'))) if r['answer']=='Armoede joint review and follow-up')
        for field,value in institution.items():assert row[field]==value
        body=build_entry_message(records[0],'sender@example.com','recipient@example.com').get_body(preferencelist=('plain',)).get_content()
        assert 'Coordinate specialist environmental referral' in body
        assert next(iter(institution.values())) in body
        at.radio[0].set_value('Facilitator dashboard').run()
        at.text_input[0].input('testadmin')
        next(b for b in at.button if b.label=='Unlock dashboard').click().run()
        next(s for s in at.selectbox if s.label=='Questionnaire to review').set_value(label).run()
        assert not at.exception
        assert any('Armoede joint review and follow-up' in t.value for t in at.text)


@pytest.mark.parametrize('code,label,institution',CASES)
def test_government_restore_is_scoped_to_its_tab(tmp_path,code,label,institution):
    d=new_entry(code);d['answers']['1']='Restored support for Armoede';d['metadata'].update(institution)
    assert validate_entry(d)['metadata']==d['metadata']
    source=tmp_path/'restore.py'
    source.write_text('import sys,json\nsys.path.insert(0,'+repr(str(ROOT))+')\n'
        'import streamlit as st\nfrom focus_core import QUESTIONNAIRES,new_entry\nfrom focus_view import _restore,render_entries\nfrom storage import Store\n'
        'if "focus_drafts" not in st.session_state:\n'
        ' st.session_state["focus_drafts"]={c:new_entry(c) for c in QUESTIONNAIRES}\n'
        ' st.session_state["focus_drafts"]["wardens"]["answers"]["1"]="Retained warden input"\n'
        f' st.session_state["focus_{code}_answers_1"]="Stale widget answer"\n'
        '_restore('+repr(json.dumps(d))+',['+repr(code)+'],'+repr(code+'_restore_notice')+')\n'
        'render_entries(Store(sqlite_path='+repr(str(tmp_path/'restore.db'))+'),False,"","",questionnaire_code='+repr(code)+')\n')
    at=AppTest.from_file(str(source),default_timeout=30).run()
    assert not at.exception
    assert at.text_area(key=f'focus_{code}_answers_1').value=='Restored support for Armoede'
    assert at.session_state['focus_drafts']['wardens']['answers']['1']=='Retained warden input'
    for field,value in institution.items():assert at.text_area(key=f'focus_{code}_metadata_{field}').value==value
