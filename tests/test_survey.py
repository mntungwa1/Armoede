import json
from pathlib import Path
import sys
import pytest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from survey_core import new_draft,add_location,inside_boundary,validate_draft,csv_bytes,geojson_export,submission_errors,QUESTIONS,RING
from storage import Store


def test_boundary_rejects_outside_and_accepts_edge():
    assert inside_boundary(-23.96,28.99)
    assert not inside_boundary(-29.0,31.0)
    assert not inside_boundary(float('nan'),28.99)
    lon,lat=RING[0];assert inside_boundary(lat,lon)


def test_linked_locations_and_draft_roundtrip():
    draft=new_draft();draft['answers']['1']['text']='Flooding on access road'
    add_location(draft,1,-23.96,28.99,'Road concern')
    assert not draft['answers']['2']['locations']
    with pytest.raises(ValueError):add_location(draft,1,-23.96,28.99)
    with pytest.raises(ValueError):add_location(draft,1,-29,31)
    restored=validate_draft(json.loads(json.dumps(draft)))
    assert restored['response_id']==draft['response_id']
    assert restored['answers']['1']['text']==draft['answers']['1']['text']
    assert restored['answers']['1']['locations'][0]['lat']==-23.96
    geo=geojson_export([restored]);assert geo['features'][0]['geometry']['coordinates']==[28.99,-23.96]
    assert geo['features'][0]['properties']['question_id']==1


def test_storage_duplicate_does_not_overwrite(tmp_path):
    draft=new_draft();draft['submitted_at']='2026-10-13T16:00:00Z';draft['answers']['1']['text']='Original'
    store=Store(sqlite_path=tmp_path/'responses.db')
    assert store.save(draft)
    draft['answers']['1']['text']='Changed';assert not store.save(draft)
    assert len(store.all())==1;assert store.all()[0]['answers']['1']['text']=='Original'


def test_consent_validation_and_spreadsheet_export():
    draft=new_draft();assert len(submission_errors(draft))==2
    draft['consent']=True;draft['answers']['3']['change']='=SUM(1,2)'
    assert not submission_errors(draft)
    assert "'=SUM(1,2)" in csv_bytes([draft]).decode('utf-8-sig')
    assert len(QUESTIONS)==12


def test_widget_navigation_retains_answers_and_places(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('SQLITE_PATH',str(tmp_path/'ui.db'))
    monkeypatch.setenv('REQUIRE_DURABLE_STORAGE','false')
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20)
    with patch('streamlit_folium.st_folium',return_value={}):
        at.run();assert not at.exception
        at.checkbox(key='w_consent').check().run()
        next(b for b in at.button if b.label=='Start the questions →').click().run()
        assert not at.exception
        at.text_area(key='w_answer_1').input('Water reaches the road').run()
        next(b for b in at.button if b.label=='Next question →').click().run()
        at.text_area(key='w_answer_2').input('A recent storm').run()
        next(b for b in at.button if b.label=='← Previous').click().run()
        assert at.text_area(key='w_answer_1').value=='Water reaches the road'
        assert at.session_state['draft']['answers']['2']['text']=='A recent storm'
    with patch('streamlit_folium.st_folium',return_value={'last_clicked':{'lat':-23.96,'lng':28.99}}):
        at.run();assert not at.exception
        at.text_input(key='w_place_label_1').input('Road One concern').run()
        next(b for b in at.button if b.label=='Attach selected place to this answer').click().run()
        assert not at.exception
        assert len(at.session_state['draft']['answers']['1']['locations'])==1
    with patch('streamlit_folium.st_folium',return_value={}):
        at.session_state['stage']=13;at.run();assert not at.exception
        next(b for b in at.button if b.label=='Submit my response').click().run()
        assert not at.exception
        assert len(Store(sqlite_path=tmp_path/'ui.db').all())==1
        assert any('submitted' in s.value for s in at.success)


def test_dashboard_locked_and_cloud_submission_disabled(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('REQUIRE_DURABLE_STORAGE','true')
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.delenv('ADMIN_PASSWORD',raising=False)
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
    assert not at.exception
    at.radio[0].set_value('Facilitator dashboard').run()
    assert not at.exception
    assert any('locked' in i.value for i in at.info)
    at.radio[0].set_value('Survey').run()
    at.checkbox(key='w_consent').check().run();at.session_state['stage']=13
    at.run();assert not at.exception
    assert next(b for b in at.button if b.label=='Submit my response').disabled


def test_all_questions_and_authenticated_dashboard(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('REQUIRE_DURABLE_STORAGE','false')
    monkeypatch.setenv('SQLITE_PATH',str(tmp_path/'dash.db'))
    monkeypatch.setenv('ADMIN_PASSWORD','test-only-password')
    draft=new_draft();draft['consent']=True;draft['submitted_at']='2026-10-13T16:00:00Z';draft['answers']['4']['text']='Follow up is needed'
    Store(sqlite_path=tmp_path/'dash.db').save(draft)
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20)
    with patch('streamlit_folium.st_folium',return_value={}):
        at.run();at.checkbox(key='w_consent').check().run()
        next(b for b in at.button if b.label=='Start the questions →').click().run()
        for i in range(1,13):
            assert not at.exception
            assert at.text_area(key=f'w_answer_{i}') is not None
            next(b for b in at.button if b.label in ['Next question →','Review my answers →']).click().run()
        assert not at.exception
        at.radio[0].set_value('Facilitator dashboard').run()
        at.text_input[0].input('wrong-password')
        next(b for b in at.button if b.label=='Unlock dashboard').click().run()
        assert at.error
        at.text_input[0].input('test-only-password')
        next(b for b in at.button if b.label=='Unlock dashboard').click().run()
        assert not at.exception
        assert any(m.value=='1' for m in at.metric)
        assert len(at.dataframe)>=5
        next(b for b in at.button if b.label=='Lock dashboard').click().run()
        assert not at.exception
        assert any(b.label=='Unlock dashboard' for b in at.button)


def test_postgres_initialization_enables_rls_before_rows_are_used():
    class RecordedConnection:
        def __init__(self):self.statements=[]
        def execute(self,statement):self.statements.append(statement)
    conn=RecordedConnection()
    Store(database_url='postgresql://example')._init(conn)
    assert conn.statements[-2:]==['ALTER TABLE armoede_survey_responses ENABLE ROW LEVEL SECURITY','ALTER TABLE armoede_email_notifications ENABLE ROW LEVEL SECURITY']
