CREATE TABLE accounts (
 id VARCHAR(36) PRIMARY KEY,
 email VARCHAR(255) NOT NULL UNIQUE,
 display_name VARCHAR(80) NOT NULL,
 password_hash VARCHAR(100) NOT NULL,
 created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE TABLE analysis_records (
 id VARCHAR(36) PRIMARY KEY,
 owner_id VARCHAR(36) NOT NULL REFERENCES accounts(id),
 kind VARCHAR(20) NOT NULL,
 payload TEXT NOT NULL,
 created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX analysis_owner_created ON analysis_records(owner_id, created_at);
