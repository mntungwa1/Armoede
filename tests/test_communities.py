import json
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from focus_core import QUESTIONNAIRES, new_entry, validate_entry, build_entry_message
from storage import Store

ROOT = Path(__file__).resolve().parents[1]

def test_gapila_content_and_roundtrip():
    for code in ('gapila_traditional', 'gapila_wardens'):
        guide = QUESTIONNAIRES[code]
        assert 'Armoede' not in json.dumps(guide)
        for section in dict.fromkeys(q['section'] for q in guide['questions']):
            assert len([q for q in guide['questions'] if q['section'] == section and q['id'].startswith('BF')]) == 2
        draft = new_entry(code)
        draft['answers']['BF1.1'] = 'Farm coordinator'
        restored = validate_entry(json.loads(json.dumps(draft)))
        assert restored['answers']['BF1.1'] == 'Farm coordinator'
        message = build_entry_message(restored, 'sender@example.com', 'recipient@example.com')
        assert message['Subject'].startswith('Ga-Pila ')

def test_drafts_and_submissions_keep_community(tmp_path, monkeypatch):
    db = tmp_path / 'communities.db'
    monkeypatch.setenv('SQLITE_PATH', str(db))
    monkeypatch.setenv('REQUIRE_DURABLE_STORAGE', 'false')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('EMAIL_PASSWORD', raising=False)
    with patch('streamlit_folium.st_folium', return_value={}):
        at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=60).run()
        assert not at.exception
        at.text_area(key='focus_traditional_answers_1').input('Armoede council').run()
        at.text_area(key='focus_gapila_traditional_answers_1').input('Ga-Pila council').run()
        at.text_area(key='focus_gapila_traditional_answers_BF1.1').input('Farm coordinator').run()
        assert at.text_area(key='focus_traditional_answers_1').value == 'Armoede council'
        at.checkbox(key='focus_gapila_traditional_consent').check().run()
        at.button(key='focus_submit_gapila_traditional').click().run()
        assert not at.exception
        saved = Store(sqlite_path=db).all()
        assert len(saved) == 1
        assert saved[0]['questionnaire_type'] == 'gapila_traditional'
        assert saved[0]['answers']['1'] == 'Ga-Pila council'
        assert saved[0]['answers']['BF1.1'] == 'Farm coordinator'
        assert at.text_area(key='focus_traditional_answers_1').value == 'Armoede council'
