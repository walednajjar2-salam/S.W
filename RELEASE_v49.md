# Release v49 — Rollout and Post-Release Roadmap

## Scope Delivered

- Stronger contract-property-client linkage with active-contract guardrails
- Invoice autofill from contract + payment cycle scheduling logic on approval
- Leaflet + OpenStreetMap dashboard map centered on Nizwa
- Property coordinates support (`latitude` / `longitude`)
- Organization workspace zone moved to the bottom section
- Permission audit API endpoint for admin validation
- Backup/storage telemetry and integrity signal in health and backup status APIs

## Direct Production Rollout

### Wave 1 (Core finance flow)
1. `POST /api/backup/run`
2. Deploy v49 code
3. Smoke test:
   - Create client
   - Create contract (draft)
   - Approve contract
   - Create invoice from contract
   - Collect payment

### Wave 2 (UI + storage hardening)
1. Verify map markers and property coordinates
2. Verify workspace org chart moved to bottom
3. Validate `GET /api/backup/status` includes `storage` + `backup_integrity`
4. Confirm `GET /api/permissions/audit` for admin role matrix

## Rollback

1. Restore previous stable commit
2. `POST /api/backup/verify` then restore from latest SQLite backup if needed
3. Re-run smoke test (login, contract flow, backup download)

## Post-v49 Roadmap

- Controlled migration path from SQLite to PostgreSQL with dual-write/verification
- Smart receivables engine (aging + reminders + WhatsApp/SMS integration)
- Object storage for contract files/photos (S3-compatible)
- Role-specific KPI boards + proactive alerts
- Security hardening: MFA + device trust + stricter password rotation
