CREATE TABLE IF NOT EXISTS push_outbox(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,data TEXT DEFAULT '{}',status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER DEFAULT 0,last_error TEXT,created_at TEXT NOT NULL,sent_at TEXT,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS job_runs(id TEXT PRIMARY KEY,job_name TEXT NOT NULL,status TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,error TEXT,items INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS media_assets(id TEXT PRIMARY KEY,user_id TEXT,object_key TEXT NOT NULL UNIQUE,original_name TEXT,mime_type TEXT,size_bytes INTEGER,sha256 TEXT NOT NULL,storage_backend TEXT NOT NULL DEFAULT 'local',created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL);
CREATE INDEX IF NOT EXISTS idx_push_outbox_status ON push_outbox(status,created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_name ON job_runs(job_name,started_at);
CREATE INDEX IF NOT EXISTS idx_media_assets_user ON media_assets(user_id,created_at);
