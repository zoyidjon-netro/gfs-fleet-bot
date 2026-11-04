# GFS Speaker — implementation prompt

Implement the frontend specification in `mini-app-spec.md` in the existing `web/index.html` application. Preserve its vanilla HTML/CSS/JavaScript architecture and real API integrations. Inspect the current implementation first. Finish and visually verify the frontend rather than only proposing a design.

## Visual references

Use the four user-provided images as visual direction:

1. Overview dashboard: navy summary card, spacious white metric cards, strong number hierarchy, thin line icons, calm borders and compact recent-activity rows.
2. Vehicle directory: searchable group cards, rounded status chips, clear detail view, readable Unit identity and floating-feeling bottom navigation. Do not introduce vehicle inventories or maintenance controls absent from GFS requirements.
3. Scheduled list: group real broadcasts by Today, Tomorrow and Later; show clear date/time subtitles and contextual actions. Do not present delivery state as an editable task checkbox.
4. Message form: clean labeled fields, large message editor, inline button builder, scheduling controls and a review step. Use a mobile-safe native date/time picker; avoid recreating unrelated SMS controls.

Do not copy the reference images' revenue, order, conversion, vehicle-maintenance or financial data into this operational app. All displayed operational counts must derive from real API responses. For unavailable data show an explicit unavailable state.

## Design tokens

Use Inter, primary #2563EB, navy #102C53, background #F8FAFC, surface #FFFFFF, text #0F172A, muted #64748B and border #E2E8F0. Use 8px spacing increments, 14–18px card radii, 12px input/button radii, and touch targets of at least 44px. Support light/dark Telegram themes, safe areas, reduced motion and widths from 320px upward. Use consistent SVG line icons instead of miscellaneous Unicode symbols.

## Functional scope

Bottom navigation: Dashboard, Broadcasts, Groups, Audits, More. Provide contextual back navigation for editor and details.

Broadcast workflow: Compose → Inline buttons → Recipient scope → Schedule → Review. Preserve media upload, HTML/MarkdownV2, ordinary/premium stickers where Telegram supports them, real private preview, one-time/weekly schedules, edit/cancel and delivery logs. Provide truthful attachment and formatting previews, character counts, button reorder, search/status/date filters and confirmations explaining recipient scope.

Current backend always broadcasts to all eligible registered groups. Do not offer individual recipient selection as working unless that capability already exists. Clearly state the actual scope in recipient/review steps.

Eligibility: exclude a present group ONLY when its title contains INACTIVE (case insensitive) AND it has no avatar. Monday SHOP, INACTIVE or AVAILIBLE must never exclude a Telegram group. Unit conflicts must remain eligible under the same matrix.

Groups: show name, avatar/placeholder, chat ID, mapped Unit, mapping status and eligibility explanation. Provide search and mapping/eligibility filters. Use real Monday sync data for Unit candidates. Confirm manual assignments only after successful existing PUT request.

COI submission remains through the bot. Do not fabricate audit history or warnings because the current API does not expose them. Administrator creation remains the existing bot command; no admin deletion UI. Hide or explain unavailable admin-directory, notification and language capabilities instead of adding fake working buttons.

## API contract — preserve exactly

- GET /api/state → groups, jobs, timezone
- POST /api/sync → trucks, refresh_failures
- PUT /api/groups/{chat_id} with {unit}
- POST /api/media?kind=... multipart file → file_id
- POST /api/preview with existing Broadcast payload
- POST /api/jobs with existing Broadcast payload
- PUT /api/jobs/{id} with existing Broadcast payload
- DELETE /api/jobs/{id}
- Authorization: tma + Telegram WebApp initData

Never change backend files, databases, Monday data or business rules for this frontend task. Never bypass Telegram authentication for production. Any test fixtures must be explicit and isolated from real operations.

## Acceptance

Check every navigation and editor action, empty/loading/error/403/retry states, button ordering after edit, media replacement/removal, schedule timezone summaries and real-operation feedback. Visually inspect at 320, 390 and 768px in light and dark themes. Check no horizontal overflow or keyboard-hidden actions. Run JavaScript syntax checks and applicable existing tests. Report exactly what was implemented, what was visually verified and which API limitations remain. Do not claim full completion based only on backend tests.
