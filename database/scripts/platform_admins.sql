-- =============================================================================
-- Platform Admin Management Queries
-- =============================================================================
-- Run with:  psql $DATABASE_URL -f database/scripts/platform_admins.sql
--
-- To generate a bcrypt hash for a new password (cost 12):
--   python3 -c "from passlib.context import CryptContext; \
--               print(CryptContext(schemes=['bcrypt']).hash('YourPassword'))"
-- =============================================================================


-- ── List all platform admins ──────────────────────────────────────────────────
-- SELECT id, email, display_name, is_active, created_at
-- FROM platform_admins
-- ORDER BY created_at;


-- ── Insert a new platform admin ───────────────────────────────────────────────
-- Replace :email, :hashed_password, :display_name with real values.
-- The hashed_password must be a bcrypt hash (see generation command above).
--
-- INSERT INTO platform_admins (id, email, hashed_password, display_name, is_active)
-- VALUES (
--     gen_random_uuid(),
--     'newadmin@example.com',
--     '$2b$12$REPLACE_WITH_BCRYPT_HASH',
--     'New Admin',
--     TRUE
-- )
-- ON CONFLICT (email) DO NOTHING;


-- ── Deactivate an admin (soft disable — they cannot log in) ───────────────────
-- UPDATE platform_admins
-- SET is_active = FALSE, updated_at = NOW()
-- WHERE email = 'admin@example.com';


-- ── Reactivate an admin ───────────────────────────────────────────────────────
-- UPDATE platform_admins
-- SET is_active = TRUE, updated_at = NOW()
-- WHERE email = 'admin@example.com';


-- ── Update password ───────────────────────────────────────────────────────────
-- UPDATE platform_admins
-- SET hashed_password = '$2b$12$REPLACE_WITH_NEW_BCRYPT_HASH',
--     updated_at = NOW()
-- WHERE email = 'admin@example.com';


-- ── Delete an admin permanently ───────────────────────────────────────────────
-- DELETE FROM platform_admins WHERE email = 'admin@example.com';
