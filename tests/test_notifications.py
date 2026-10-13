from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage import Store
from survey_core import new_draft,add_location
from notifications import build_message,deliver_response,RECIPIENT


def payload():
    d=new_draft();d['consent']=True;d['submitted_at']='2026-10-13T17:20:00Z'
    for n,a in d['answers'].items():a['text']='Answer '+n;a['change']='Change '+n
    add_location(d,8,-23.96,28.99,'Assembly proposal')
    d['priorities']=['Drainage','Warnings','Backup wardens'];return d


def test_email_has_all_answers_locations_and_exports():
    d=payload();msg=build_message(d,'dingaanm@gmail.com')
    assert msg['To']==RECIPIENT
    body=msg.get_body(preferencelist=('plain',)).get_content()
    for n in range(1,13):assert f'QUESTION {n}:' in body and f'Answer {n}' in body and f'Change {n}' in body
    assert 'Assembly proposal' in body and '-23.960000' in body and '28.990000' in body
    attachments=list(msg.iter_attachments());assert len(attachments)==2
    assert attachments[0].get_filename().endswith('_answers.csv')
    assert attachments[1].get_filename().endswith('_locations.geojson')


class FakeSMTP:
    messages=[]
    def __init__(self,host,port,timeout):assert host=='smtp.gmail.com' and port==587
    def ehlo(self):pass
    def starttls(self,context):assert context.check_hostname
    def login(self,sender,password):assert password=='testpassword'
    def send_message(self,msg,from_addr,to_addrs):
        assert to_addrs==['dingaanm@gmail.com'];self.messages.append(msg);return {}
    def close(self):pass


def test_notification_sent_once_and_original_payload_retained(tmp_path):
    d=payload();store=Store(sqlite_path=tmp_path/'outbox.db');store.save(d);FakeSMTP.messages=[]
    with patch('notifications.smtplib.SMTP',FakeSMTP):
        assert deliver_response(store,d['response_id'],'dingaanm@gmail.com','test password')=='sent'
        assert deliver_response(store,d['response_id'],'dingaanm@gmail.com','test password')=='sent'
    assert len(FakeSMTP.messages)==1
    assert store.email_statuses()[d['response_id']]['attempts']==1


def test_pre_send_failure_can_retry_and_send_timeout_is_not_auto_retried(tmp_path):
    d=payload();store=Store(sqlite_path=tmp_path/'outbox.db');store.save(d)
    with patch('notifications.smtplib.SMTP',side_effect=OSError('test error containing a sensitive string')):
        assert deliver_response(store,d['response_id'],'dingaanm@gmail.com','testpassword')=='failed'
    assert 'sensitive string' not in store.email_statuses()[d['response_id']]['detail']
    class UncertainSMTP(FakeSMTP):
        def send_message(self,*args,**kwargs):raise TimeoutError('unknown delivery')
    with patch('notifications.smtplib.SMTP',UncertainSMTP):
        assert deliver_response(store,d['response_id'],'dingaanm@gmail.com','testpassword')=='uncertain'
        assert deliver_response(store,d['response_id'],'dingaanm@gmail.com','testpassword')=='uncertain'
    assert store.email_statuses()[d['response_id']]['attempts']==2
    with patch('notifications.smtplib.SMTP',FakeSMTP):
        assert deliver_response(store,d['response_id'],'dingaanm@gmail.com','testpassword',allow_uncertain=True)=='sent'


def test_claim_is_exclusive(tmp_path):
    d=payload();store=Store(sqlite_path=tmp_path/'outbox.db');store.save(d);store.queue_email(d['response_id'])
    assert store.claim_email(d['response_id'])
    assert not store.claim_email(d['response_id'])


def test_email_only_cloud_submission_and_receipt(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('REQUIRE_DURABLE_STORAGE','true');monkeypatch.setenv('SQLITE_PATH',str(tmp_path/'ui.db'))
    monkeypatch.setenv('EMAIL_ADDRESS','dingaanm@gmail.com');monkeypatch.setenv('EMAIL_PASSWORD','testpassword')
    monkeypatch.delenv('DATABASE_URL',raising=False)
    app=str(Path(__file__).resolve().parents[1]/'app.py')
    with patch('streamlit_folium.st_folium',return_value={}),patch('notifications.smtplib.SMTP',FakeSMTP):
        at=AppTest.from_file(app,default_timeout=20).run();assert not at.exception
        at.session_state['draft']=payload();at.session_state['stage']=13;at.run()
        b=next(b for b in at.button if b.label=='Submit my response');assert not b.disabled
        b.click().run();assert not at.exception
        assert at.session_state['submitted_receipt']['email_status']=='sent'
        assert any('Gmail accepted' in x.value for x in at.success)
