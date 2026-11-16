# NeedBridge

Connecting unused resources with verified community needs. **Give. Connect. Smile.**

## Current development state

The original React/Vite website and its GSAP storytelling animation remain in place. The
original CSV/SQLite API is still available during migration. A new relational API is now
available under `/api/v2`; the frontend has not yet been switched to it.

### PostgreSQL setup

1. Create a PostgreSQL database.
2. Set `DATABASE_URL` in your environment (for local development, a PostgreSQL URL such as
   `postgresql+psycopg://user:password@localhost:5432/needbridge`).
3. Install `requirements-deploy.txt`.
4. Run `alembic upgrade head`.
5. Run `python -m backend.init_postgres` to seed resource categories and optionally create
   the first admin when `ADMIN_EMAIL`, `ADMIN_PASSWORD` and optionally `ADMIN_NAME` are set.
6. Start the application with `uvicorn backend.api:app --reload`.

Do not use the default development session secret in production. Set a long random
`NEEDBRIDGE_SECRET` and set `NEEDBRIDGE_HTTPS=1` behind HTTPS.

### Relational API v2

- `POST /api/v2/auth/signup` and `/login`; `GET /api/v2/auth/me`; `POST /api/v2/auth/logout`
- `GET /api/v2/dashboard` (role-scoped donor, institution and admin metrics)
- `GET /api/v2/categories`
- `GET/POST /api/v2/donations`
- `POST /api/v2/donations/{donation_id}/photos`
- `GET/POST /api/v2/requirements`
- `GET /api/v2/matches`
- `GET/POST /api/v2/offers`; `POST /api/v2/offers/{offer_id}/respond`
- `POST /api/v2/handovers/{handover_id}/schedule`, `/confirm` and `/cancel`
- `GET /api/v2/notifications`
- `POST /api/v2/notifications/{notification_id}/read`; `POST /api/v2/notifications/read-all`
- `POST /api/v2/organisations/{organisation_id}/verification-documents`
- `GET /api/v2/admin/organisations`; `POST /api/v2/admin/organisations/{organisation_id}`
- `POST /api/v2/admin/verification-documents/{document_id}`
- `GET /api/v2/files/{file_id}`

Institution accounts begin unverified. An administrator must review and approve at least one
uploaded verification document before marking an institution verified. Verified institutions
can publish requirements. The matching engine is transparent, rule-based, location-aware and
suggestive only; people still decide whether to offer, accept and complete a handover.

Offer acceptance reserves the agreed quantity in a database transaction. The donation and
requirement quantities are only marked fulfilled after both donor and recipient confirm the
same received quantity. A disagreement is marked as disputed rather than silently counted.

## Storage

File bytes are kept outside PostgreSQL. `backend/storage.py` provides one provider-neutral
interface:

- `local` (default): development files under `data/uploads/`.
- `s3`: S3-compatible private object storage (for example, Cloudflare R2).

Set `NEEDBRIDGE_STORAGE_BACKEND=s3`, `S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`,
`S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` to enable object storage. Keep bucket public
access disabled. Database rows store opaque object keys, never temporary signed URLs. Production
startup rejects ephemeral local uploads: configure S3-compatible storage, or explicitly mount a
persistent disk and set `NEEDBRIDGE_PERSISTENT_UPLOADS=1`.

Donation photos can be attached to a donation from the listing form. Donation photos: maximum 5 MB, JPEG/PNG/WebP. Verification documents: maximum 10 MB,
PDF/JPEG/PNG, private by default. Files are checked by their magic bytes rather than trusting
the browser-provided MIME type. Original filenames are not used as storage keys.

## Tests

Run from the project root with `python -m pytest -q`. The suite currently has 30 passing tests, including end-to-end offer reservation, two-party
confirmation, cancellation, private-file access, role-scoped dashboard metrics and private
notification read-state management. Tests use
SQLite for isolation; production configuration remains PostgreSQL. A full Vite production bundle
still needs to be run after frontend dependencies install (`npm ci && npm run build`).

## Listing management (Build 06)

Signed-in donors and institution members can manage only their own listings:

- `GET /api/v2/my-listings` returns the current user's donation listings or their institution's requirements, including reserved, completed and remaining quantities.
- `PATCH /api/v2/listings/{kind}/{listing_id}` updates title, description, area and total quantity (`kind` is `donation` or `requirement`). Quantity cannot be reduced below already reserved plus completed units.
- `POST /api/v2/listings/{kind}/{listing_id}/status` accepts `pause`, `resume`, `withdraw` (donations) or `close` (requirements).

Listing ownership is checked server-side. A listing with a pending or accepted offer cannot be edited, paused, withdrawn or closed until that offer is resolved. A listing with reserved units cannot be withdrawn or closed. Every successful change is written to the audit log. The React `ListingManager` is shown to signed-in donors and institution members; no generated images or changes to the existing storytelling assets are included.


## Build 07 — community trust and safety

- Signed-in donors and institution members can privately report public requirements for misleading information, inappropriate content, duplicates, safety concerns, suspicious activity, or other concerns. A reporter cannot report their own listing or institution, and duplicate open reports are rejected.
- Administrators have a report queue and can mark reports in review, resolve them, or dismiss them with an internal review note. The reporter receives a status notification; the reported party is not shown the reporter's identity.
- Listing owners can inspect a private activity timeline containing their listing's audit events.
- Apply the new database migration `4c91a0d7b2e1` after the previous migration before deploying Build 07.

## Build 08 additions

- Authenticated donor and institution profile read/update endpoints (`GET/PATCH /api/v2/profile`). Institution owners/managers can update institution details; ordinary members can update their personal profile only.
- Accepted-offer contact coordination (`GET /api/v2/offers/{offer_id}/contacts`). Contact details are withheld until acceptance and only returned to the donor or member of the recipient institution participating in that offer.
- Admin account list and account activation/suspension endpoints (`GET /api/v2/admin/accounts`, `POST /api/v2/admin/accounts/{user_id}/status`). Admins cannot suspend admin accounts or their own account. Suspending an institution member also suspends the associated organisation's verification status.
- The `/api/v2/auth/me` endpoint clears inactive sessions so suspended accounts are signed out on their next session check.
- Frontend profile editor, accepted-offer contact reveal, and admin account controls.

Build 08 verification: run `python -m pytest -q` and `python -m compileall -q backend tests`. The frontend production build must also be run with dependencies installed (`cd frontend && npm ci && npm run build`).
