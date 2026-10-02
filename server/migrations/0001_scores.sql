CREATE TABLE players (
  scope TEXT NOT NULL,
  token_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (scope, token_hash)
);
CREATE TABLE runs (
  scope TEXT NOT NULL,
  id TEXT NOT NULL,
  player_hash TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('strict','original')),
  version TEXT NOT NULL,
  score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 1000000),
  accuracy REAL CHECK (accuracy BETWEEN 0 AND 100),
  wpm REAL CHECK (wpm BETWEEN 0 AND 1000),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (scope, id),
  FOREIGN KEY (scope, player_hash) REFERENCES players(scope, token_hash)
);
CREATE INDEX runs_board ON runs(scope, mode, version, score DESC);
CREATE INDEX runs_player ON runs(scope, player_hash, mode, version);
CREATE INDEX runs_recent ON runs(scope, player_hash, created_at);
