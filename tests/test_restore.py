import io,json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from survey_core import new_draft,add_location
from streamlit.testing.v1 import AppTest

APP=str(Path(__file__).resolve().parents[1]/'app.py')


def draft_with_answers():
    d=new_draft();d['consent']=True;d['participant']['area']='Road One'
    d['answers']['1']['text']='Saved flooding experience'
    d['answers']['1']['change']='Repair drainage'
    d['answers']['8']['text']='A proposed assembly point'
    add_location(d,8,-23.96,28.99,'Saved shelter proposal')
    d['ratings']['D2.1']='Workable with changes';d['priorities'][0]='Drainage first'
    return d


def test_restore_opens_saved_question_and_preserves_all_fields():
    saved=draft_with_answers();saved['resume_stage']=8
    with patch('streamlit.file_uploader',return_value=io.BytesIO(json.dumps(saved).encode())),patch('streamlit_folium.st_folium',return_value={}):
        at=AppTest.from_file(APP,default_timeout=20).run()
        next(b for b in at.button if b.label=='Restore draft').click().run()
        assert not at.exception
        assert at.session_state['stage']==8
        assert at.text_area(key='w_answer_8').value=='A proposed assembly point'
        assert len(at.session_state['draft']['answers']['8']['locations'])==1
        assert at.session_state['draft']['participant']['area']=='Road One'
        assert at.session_state['draft']['ratings']['D2.1']=='Workable with changes'
        assert at.session_state['draft']['priorities'][0]=='Drainage first'
        assert any('Draft restored: 2 questions' in x.value for x in at.success)
        next(b for b in at.button if b.label=='← Previous').click().run()
        assert at.session_state['draft']['answers']['8']['text']=='A proposed assembly point'


def test_old_draft_opens_first_saved_answer_and_replaces_current_widgets():
    saved=draft_with_answers()
    with patch('streamlit.file_uploader',return_value=io.BytesIO(json.dumps(saved).encode())),patch('streamlit_folium.st_folium',return_value={}):
        at=AppTest.from_file(APP,default_timeout=20).run()
        at.checkbox(key='w_consent').check().run()
        next(b for b in at.button if b.label=='Start the questions →').click().run()
        at.text_area(key='w_answer_1').input('Unsaved different answer').run()
        next(b for b in at.button if b.label=='← Previous').click().run()
        next(b for b in at.button if b.label=='Restore draft').click().run()
        assert not at.exception
        assert at.session_state['stage']==1
        assert at.text_area(key='w_answer_1').value=='Saved flooding experience'
        assert at.text_area(key='w_change_1').value=='Repair drainage'


def test_malformed_draft_preserves_current_data_and_reports_error():
    with patch('streamlit.file_uploader',return_value=io.BytesIO(b'not json')):
        at=AppTest.from_file(APP,default_timeout=20).run()
        old_id=at.session_state['draft']['response_id']
        next(b for b in at.button if b.label=='Restore draft').click().run()
        assert not at.exception
        assert at.session_state['draft']['response_id']==old_id
        assert any('Could not restore draft' in e.value for e in at.error)


def test_prepare_captures_pending_answer_and_download_snapshot():
    with patch('streamlit_folium.st_folium',return_value={}):
        at=AppTest.from_file(APP,default_timeout=20).run()
        at.checkbox(key='w_consent').check().run()
        next(b for b in at.button if b.label=='Start the questions →').click().run()
        # Input is intentionally not followed by its own run before Prepare is clicked.
        at.text_area(key='w_answer_1').input('The newest typed answer')
        next(b for b in at.button if b.label=='Prepare draft download').click().run()
        assert not at.exception
        exported=json.loads(at.session_state['prepared_draft'])
        assert exported['answers']['1']['text']=='The newest typed answer'
        assert exported['resume_stage']==1
        at.text_area(key='w_answer_1').input('A later edit').run()
        assert any('made changes' in c.value for c in at.caption)


def test_empty_draft_gives_explicit_warning():
    saved=new_draft()
    with patch('streamlit.file_uploader',return_value=io.BytesIO(json.dumps(saved).encode())):
        at=AppTest.from_file(APP,default_timeout=20).run()
        next(b for b in at.button if b.label=='Restore draft').click().run()
        assert not at.exception
        assert any('no saved question answers' in w.value for w in at.warning)
