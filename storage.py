"""SQLite for local workshops; PostgreSQL for hosted collection."""
import json
import sqlite3
from pathlib import Path

class Store:
    def __init__(self,database_url='',sqlite_path='responses/armoede.sqlite3'):
        self.url=database_url
        self.path=Path(sqlite_path)
    @property
    def durable(self):return bool(self.url)
    def _connection(self):
        if self.url:
            import psycopg
            return psycopg.connect(self.url,connect_timeout=10)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        conn=sqlite3.connect(self.path,timeout=20)
        conn.execute('PRAGMA busy_timeout=20000')
        return conn
    def _init(self,conn):
        conn.execute('CREATE TABLE IF NOT EXISTS armoede_survey_responses (response_id TEXT PRIMARY KEY, submitted_at TEXT NOT NULL, payload TEXT NOT NULL)')
        conn.execute("CREATE TABLE IF NOT EXISTS armoede_email_notifications (response_id TEXT PRIMARY KEY, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '')")
        if self.url:
            # The server connects as table owner; public API roles receive no row access.
            conn.execute('ALTER TABLE armoede_survey_responses ENABLE ROW LEVEL SECURITY')
            conn.execute('ALTER TABLE armoede_email_notifications ENABLE ROW LEVEL SECURITY')
    def save(self,payload):
        conn=self._connection()
        try:
            self._init(conn)
            placeholder='%s' if self.url else '?'
            # Duplicate clicks and restored submissions do not insert or overwrite records.
            cur=conn.execute(f'INSERT INTO armoede_survey_responses (response_id,submitted_at,payload) VALUES ({placeholder},{placeholder},{placeholder}) ON CONFLICT (response_id) DO NOTHING',
                             (payload['response_id'],payload['submitted_at'],json.dumps(payload,ensure_ascii=False)))
            conn.commit()
            return cur.rowcount==1
        finally:conn.close()
    def all(self):
        conn=self._connection()
        try:
            self._init(conn);rows=conn.execute('SELECT payload FROM armoede_survey_responses ORDER BY submitted_at DESC').fetchall();conn.commit()
            return [json.loads(row[0]) for row in rows]
        finally:conn.close()

    def get(self,response_id):
        conn=self._connection()
        try:
            self._init(conn);placeholder='%s' if self.url else '?'
            row=conn.execute(f'SELECT payload FROM armoede_survey_responses WHERE response_id={placeholder}',(response_id,)).fetchone();conn.commit()
            return json.loads(row[0]) if row else None
        finally:conn.close()

    def queue_email(self,response_id):
        conn=self._connection()
        try:
            self._init(conn);placeholder='%s' if self.url else '?'
            conn.execute(f"INSERT INTO armoede_email_notifications (response_id,status,attempts,updated_at) VALUES ({placeholder},'pending',0,{placeholder}) ON CONFLICT (response_id) DO NOTHING",(response_id,self._now()))
            conn.commit()
        finally:conn.close()

    @staticmethod
    def _now():
        from datetime import datetime,timezone
        return datetime.now(timezone.utc).isoformat()

    def claim_email(self,response_id,allow_uncertain=False):
        conn=self._connection()
        try:
            self._init(conn);placeholder='%s' if self.url else '?'
            eligible="'pending','failed','uncertain','sending'" if allow_uncertain else "'pending','failed'"
            cur=conn.execute(f"UPDATE armoede_email_notifications SET status='sending',attempts=attempts+1,updated_at={placeholder},detail='' WHERE response_id={placeholder} AND status IN ({eligible})",(self._now(),response_id))
            conn.commit();return cur.rowcount==1
        finally:conn.close()

    def finish_email(self,response_id,status,detail=''):
        if status not in ('sent','failed','uncertain'):raise ValueError('Invalid email status')
        conn=self._connection()
        try:
            self._init(conn);placeholder='%s' if self.url else '?'
            conn.execute(f'UPDATE armoede_email_notifications SET status={placeholder},detail={placeholder},updated_at={placeholder} WHERE response_id={placeholder}',(status,detail[:300],self._now(),response_id));conn.commit()
        finally:conn.close()

    def email_statuses(self):
        conn=self._connection()
        try:
            self._init(conn);rows=conn.execute('SELECT response_id,status,attempts,updated_at,detail FROM armoede_email_notifications ORDER BY updated_at DESC').fetchall();conn.commit()
            return {r[0]:{'status':r[1],'attempts':r[2],'updated_at':r[3],'detail':r[4]} for r in rows}
        finally:conn.close()
