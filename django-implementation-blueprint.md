# Django Implementation Blueprint (Barber CRM)

## 1) Product boundaries (v1 direction)
- Single branch/location deployment
- Django server-rendered app (no Tailwind, custom CSS)
- Arabic/English UI from day one (default: Arabic)
- Local media storage first, S3-compatible storage later
- Progressive rollout with strict checklist-based delivery

## 2) Recommended tech architecture
- Backend: Django + Django ORM + Django auth
- Database: PostgreSQL (recommended) or SQLite for initial prototyping only
- Frontend: Django templates + vanilla JS + custom CSS
- Camera: in-flow capture UX for visit photos
- Background jobs: Celery + Redis (or Django-Q as lighter alternative) for reminders/precompute tasks

## 3) Django app/module structure
- `core`: settings, base templates, language switching, shared utilities
- `accounts`: users, roles, permission toggles, profile settings
- `clients`: client profile, preferences, notes, consent flags
- `services`: service catalog and default durations
- `appointments`: appointments + walk-ins + statuses
- `visits`: visit lifecycle, haircut summary, detailed notes, ratings, photos
- `auditlog`: centralized audit records for tracked changes

## 4) Domain model (initial)

### Users & roles
- `User`: standard auth + display name + active flag + preferred language
- `Role`: owner_admin, receptionist, barber
- `PermissionToggle`: owner-managed per-user/per-role toggles (e.g., edit client identity)

### Clients
- `Client`
  - `full_name` (required)
  - `phone` (required, unique)
  - `email` (optional)
  - `date_of_birth` (optional)
  - `gender` (optional)
  - `preferred_drink` (optional)
  - `general_notes` (optional)
  - `marketing_opt_in` (boolean)
  - `photo_marketing_opt_in` (boolean)
  - timestamps + `created_by`/`updated_by`

### Services
- `Service`
  - `name_ar`, `name_en`
  - `default_duration_minutes`
  - `is_active`

### Appointments
- `Appointment`
  - `client`
  - `barber` (nullable for unassigned walk-ins)
  - `service`
  - `start_at`, `end_at`
  - `status` (scheduled/confirmed/completed/cancelled/no_show)
  - `is_walk_in` (boolean)
  - `notes`
  - timestamps + actor fields
- Overlap prevention is intentionally disabled by business rule

### Visits
- `Visit`
  - `client`
  - `barber`
  - `appointment` (nullable)
  - `started_at`, `completed_at` (nullable)
  - `short_summary` (last haircut summary)
  - `detailed_notes`
  - `comments`
  - `satisfaction_rating` (nullable, e.g., 1–5)
  - `status` (in_progress/completed)
  - timestamps + actor fields
- `VisitPhoto`
  - `visit`
  - `image`
  - `stage` (before/after/other)
  - `captured_at`
  - `captured_by`
  - `sort_order`

### Audit trail
- `AuditLog`
  - `content_type`, `object_id`
  - `action` (create/update/delete)
  - `changed_fields` (JSON)
  - `actor`
  - `created_at`
- Track all edits for clients, appointments, visits, visit photos

## 5) Permission policy (toggle-first)
- Baseline access:
  - Owner/Admin: full access
  - Receptionist: operational access to clients/appointments/visits
  - Barber: operational access + cross-client visibility
- Owner can toggle key permissions per role/user (start with):
  - Edit client identity fields
  - Delete visits/photos
  - Edit completed visits
  - Export campaign lists

## 6) Operational notes
- Visit completion does not require AFTER photo

## 7) UI flow (phase 1)
- Login → Today dashboard (role-specific)
- Appointments/walk-ins list
- Start visit
- In-visit screen:
  - client header + last visit summary
  - before photo card (capture/retake/save)
  - after photo card (capture/retake/save/skip)
  - summary + detailed notes + rating
  - save progress / complete visit
- Client page:
  - profile
  - latest summary highlight
  - timeline of visits + photos

## 8) Milestones (execution order)
- M1: Project scaffold + auth/roles + i18n/RTL + base UI system
- M2: Clients + services + appointments/walk-ins
- M3: Visits + in-screen camera flow + multi-photo + ratings
- M4: Operational polish + audit integration

## 9) Definition of done for each milestone
- Features implemented
- Permissions enforced and toggleable
- Audit events captured
- Arabic/English labels complete for touched screens
- Checklist updated in `checklist.md`
