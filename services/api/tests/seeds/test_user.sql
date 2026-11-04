-- Local development account only. Login: test; password: test; role: user.
-- Apply manually to the local database; never loaded by db/init.
INSERT INTO users (user_id, username, password_hash, role)
VALUES ('84f2623c-0709-4717-901f-b74a28a72902', 'test', '$argon2id$v=19$m=65536,t=3,p=4$n+t2ZXzIxaeCYDRCxDqYaA$OjFR9QxVdou84M80ck/R9oJpMnm7VZiMlAAjfMaZdxg', 'user');
