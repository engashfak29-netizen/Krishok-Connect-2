-- Production hardening: native video attachments for social posts.
ALTER TABLE posts ADD COLUMN videos TEXT DEFAULT '[]';
