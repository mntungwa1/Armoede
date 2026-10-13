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
