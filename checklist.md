# Barber CRM Build Checklist

## Project setup status
- [x] Django project scaffolding
- [x] Core apps/modules structure
- [x] Base layout + custom CSS system (no Tailwind)
- [x] Arabic/English i18n (RTL + LTR support)
- [x] Role-based auth (Owner/Admin, Receptionist, Barber)

## Confirmed decisions (from interview)
- Progressive delivery: build in iterations (no strict all-at-once scope)
- Single branch/location for now
- Roles: Owner/Admin + Receptionist + Barber
- Barbers can view other barbers' clients/visits
- Client identity fields are editable by default for roles; owner can toggle/restrict permissions
- Phone number is unique; no duplicates
- AFTER photo is optional when completing visit
- Multiple photos per visit allowed + quick retake UX
- Overlapping appointments are allowed intentionally
- Reminders/promos: export and external sending (WhatsApp/SMS tools)
- UI stack: Django server-rendered templates + custom CSS only
- Walk-ins can be minimal (name + phone)
- Keep appointment statuses simple
- Completed visits remain editable with edit-tracking/audit
- Satisfaction rating should be included
- No separate consent timestamps needed
- No heavy legal/compliance requirements
- Audit logging is required
- Core KPI reporting is required
- Revenue tracking deferred
- Defaults: Egypt timezone + EGP currency
- Local media storage first; S3 later
- Bilingual UI (Arabic/English) from day one, default Arabic
- No data import required initially

## Backlog (not built yet)

### Phase 0 — Foundations
- [x] Define architecture and app boundaries
- [x] Define domain model (clients, visits, appointments, photos, services, audit logs)
- [x] Define permissions matrix per role
- [x] Define i18n strategy (translations + RTL/LTR styling)

### Phase 1 — Core operations
- [x] Client profiles (minimal + full profile)
- [x] Client list/search (name/phone)
- [x] Appointment management (supports overlaps)
- [x] Walk-in queue (manual assignment)
- [x] Service catalog + default durations
- [x] Visit workflow with last-visit summary
- [x] Camera capture inside visit flow (before/after optional)
- [x] Multi-photo per visit + retake UX
- [x] Complete visit flow + satisfaction rating
- [x] Owner/receptionist/barber dashboards (basic)
- [x] Audit trail for edits (who/when/what)

### Phase 2 — Growth
- [ ] Future phase definitions

## Session update log
- 2026-02-08: Initial discovery interview completed; checklist initialized.
- 2026-02-08: Final discovery clarifications captured (permissions toggles, phase-1 services, Arabic default).
- 2026-02-08: M1 scaffold completed (Django setup, custom user/roles, base UI, i18n, foundational models, logo integration).
- 2026-02-08: M2 core operations shipped (clients, services, appointments/walk-ins UI, permission toggles usage, audit logging signals, dashboard links/stats).
- 2026-02-08: M3 visit workflow shipped (visit start/list/workflow pages, optional AFTER completion rule, camera capture+retake, multi-photo upload, appointment-to-visit linking).
- 2026-02-08: Hotfix shipped for AR/EN switching (correct locale-aware redirects and recovery from non-prefixed URLs after switching to English).
