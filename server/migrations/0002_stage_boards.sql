-- Per-stage leaderboards and the weapon used. Additive: existing rows are full runs with the pistol.
ALTER TABLE runs ADD COLUMN stage TEXT NOT NULL DEFAULT 'all';
ALTER TABLE runs ADD COLUMN weapon TEXT NOT NULL DEFAULT 'pistol';
CREATE INDEX runs_board_stage ON runs(scope, mode, version, stage, score DESC);
CREATE INDEX runs_player_stage ON runs(scope, player_hash, mode, version, stage);
