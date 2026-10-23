import sys
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from document_view import document_bytes
ROOT=Path(__file__).resolve().parents[1]

def test_original_downloads_and_rendered_previews():
    manifest=json.loads((ROOT/'documents/manifest.json').read_text())
    for stem in ['Armoede_DRM_Plan','Armoede_Draft_SOPs']:
        path=f'documents/{stem}.docx'
        assert hashlib.sha256(document_bytes(stem,'docx')).hexdigest()==manifest[path]['sha256']
        assert document_bytes(stem,'pdf').startswith(b'%PDF-')

def test_documents_are_protected_by_survey_password():
    with patch.dict('os.environ',{'SURVEY_PASSWORD':'test-access'}):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        assert not at.exception
        assert not at.tabs
        assert not at.get('download_button')
        at.text_input[0].input('test-access')
        next(b for b in at.button if b.label=='Open survey').click().run()
        assert not at.exception
        assert [t.label for t in at.tabs]==['Questionnaire entries','Municipality — District and Local','Stakeholder survey','DRM Plan','Draft SOPs']
        assert len([b for b in at.get('download_button') if b.label=='Download Word document'])==2

def test_previews_preserve_answer_and_can_be_closed():
    with patch('streamlit_folium.st_folium',return_value={}):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        at.checkbox(key='w_consent').check().run()
        next(b for b in at.button if b.label=='Start the questions →').click().run()
        at.text_area(key='w_answer_1').input('Our road floods')
        at.button(key='preview_plan').click().run()
        assert not at.exception
        assert at.session_state['draft']['answers']['1']['text']=='Our road floods'
        assert at.session_state['show_document_plan']
        at.button(key='preview_sops').click().run()
        assert not at.exception
        assert len([e for e in at.expander if e.label.startswith('Document preview —')])==2
        assert at.session_state['show_document_sops']
        at.button(key='close_plan').click().run()
        assert not at.exception
        assert not at.session_state['show_document_plan']
        assert at.text_area(key='w_answer_1').value=='Our road floods'
