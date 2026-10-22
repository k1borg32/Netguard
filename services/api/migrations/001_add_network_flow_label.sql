-- For databases already using the network_flows schema. Safe to apply again.
ALTER TABLE network_flows ADD COLUMN IF NOT EXISTS label TEXT;
