# GFS SPEAKER — TELEGRAM MINI APP
## Professional UI/UX Design & Frontend Technical Specification

### 1. PROJECT OBJECTIVE

Design and implement a premium, production-quality Telegram Mini App for **GFS Group LLC — Safety & Fleet Team**.

The application is an internal operational dashboard for managers to manage Telegram broadcasting campaigns, monitor truck-related Telegram groups, resolve Unit mapping conflicts, review COI audit results, and manage authorized administrators.

**IMPORTANT:**
- Focus exclusively on UI/UX and frontend implementation.
- Do not develop or modify backend services, databases, or business logic.
- If an existing frontend project is provided, inspect its structure, screens, components, styles, and existing functionality before modifying anything.
- Preserve all working API integrations and existing functionality.
- Never simulate successful backend operations as if they were real.
- Build reusable, responsive, accessible frontend components.
- Make the application feel like a premium native mobile application inside Telegram.

### 2. DESIGN SYSTEM

**Design direction:** Premium enterprise SaaS + modern Telegram-native interface.

The overall interface should be minimal, elegant, functional, visually consistent, and optimized for daily operational use.

**Colors:**
- Primary: `#2563EB`
- Primary dark: `#1D4ED8`
- Background: `#F8FAFC`
- Surface: `#FFFFFF`
- Text primary: `#0F172A`
- Text secondary: `#64748B`
- Border: `#E2E8F0`
- Success: `#16A34A`
- Warning: `#F59E0B`
- Danger: `#DC2626`
- Info: `#0EA5E9`

Use a carefully balanced color hierarchy. Avoid unnecessary gradients, excessive shadows, and overly colorful dashboard elements.

**Typography:**
- Primary font: Inter
- Large page titles: 24px, semibold/bold
- Section titles: 18px, semibold
- Card titles: 15–16px
- Body: 14px
- Supporting text: 12–13px

**Components:**
- Cards: 14–18px border radius
- Inputs: 12px radius
- Buttons: 12px radius
- Minimum touch targets: 44×44px
- Consistent 8px spacing system
- Subtle shadows
- Clean iconography using Lucide icons
- Skeleton loading states
- Clear empty states and error states
- Native-feeling transitions and bottom sheets

**Theme:**
- Light mode
- Dark mode
- Automatic Telegram theme synchronization
- Proper contrast in both themes

### 3. APPLICATION NAVIGATION

Create a bottom navigation system optimized for Telegram Mini Apps.

Main navigation:

1. Dashboard
2. Broadcasts
3. Groups
4. Audits
5. More

Use a fixed bottom navigation bar with safe-area support, clear active states, recognizable icons, and minimal visual noise.

Subpages should use contextual back navigation instead of additional permanent navigation bars.

### 4. DASHBOARD SCREEN

Create a professional operational overview.

**Header:**
- GFS Speaker logo/name
- Current administrator information
- Notification icon
- Current date

**Summary cards:**
- Total Telegram groups
- Eligible broadcasting groups
- Scheduled broadcasts
- Completed broadcasts
- Groups with Unit conflicts
- COI audit warnings

Use informative cards with meaningful status indicators.

**Quick actions:**
- Create Broadcast
- Schedule Message
- View Groups
- Review Conflicts
- View COI Audit Results

**Recent activity:**
- Recently sent broadcasts
- Upcoming broadcasts
- Recent Unit conflicts
- Latest COI audit results

Use real data where integrations exist. Otherwise show explicit unavailable or empty states rather than invented operational statistics.

### 5. BROADCAST MANAGEMENT

Design the central broadcast management module.

**Broadcast list screen:**
- Search
- Status filters
- Date filters
- Broadcast cards
- New Broadcast floating or primary action

Broadcast statuses:
- Draft
- Scheduled
- Recurring
- Sending
- Completed
- Failed
- Cancelled

Each broadcast card displays:
- Message preview
- Attachment indicator
- Scheduled date/time
- Delivery status
- Recipient group count
- Contextual actions

**Broadcast creation flow:**

Use a clear multi-step workflow.

**Step 1 — Compose Message**

Provide a premium Telegram-style message editor.

Features:
- Multiline message editor
- Bold
- Italic
- Monospace
- Spoiler
- Telegram-supported formatting
- Character count
- Message preview
- Emoji support

Attachment options:
- Image
- Video
- PDF
- Excel/document
- Sticker where supported

Display attachment previews with remove/replace actions.

**Step 2 — Inline Buttons**

Allow managers to configure buttons.

Fields:
- Button label
- Button type: URL or callback
- URL or callback value

Features:
- Add button
- Remove button
- Reorder buttons
- Preview button layout

Validate required fields and URL format.

**Step 3 — Recipient Groups**

Create a group selection interface.

Features:
- Search groups
- Select all eligible groups
- Select individual groups
- View selected groups
- Filter by eligibility
- Display exclusions clearly

Show:
- Total groups
- Eligible groups
- Excluded groups
- Selected groups

**Critical eligibility rule:**

A group must be excluded from broadcasting only when BOTH conditions are true:

1. The group title contains `INACTIVE`, case-insensitively.
2. The group has no avatar.

Decision matrix:

| INACTIVE in title | Avatar | Broadcast |
|---|---|---|
| Yes | No | Exclude |
| Yes | Yes | Include |
| No | No | Include |
| No | Yes | Include |

Never exclude a group merely because its title contains INACTIVE.

Display an eligibility explanation when a group is excluded.

**Step 4 — Scheduling**

Provide three scheduling modes:
- Send Now
- Schedule Once
- Recurring Broadcast

Schedule Once:
- Date picker
- Time picker
- Timezone indicator

Recurring:
- Weekday selector
- Time selector
- Repeat frequency
- Recurrence summary

Example:

"Every Wednesday at 15:00"

**Step 5 — Review & Confirm**

Display:
- Full Telegram-style message preview
- Media attachments
- Inline buttons
- Selected recipient groups
- Excluded groups
- Delivery schedule
- Final confirmation action

Before sending immediately, show a confirmation modal explaining the action and recipient scope.

### 6. TELEGRAM MESSAGE PREVIEW

Build a high-quality Telegram chat preview.

It must accurately represent:
- Text formatting
- Media
- File attachments
- Inline keyboards
- Spoiler styling
- Message spacing
- Telegram-like message bubbles

The preview should update instantly as the administrator edits the message.

Support both Telegram light and dark themes.

### 7. SCHEDULED BROADCASTS

Create a dedicated scheduling management interface.

**Views:**
- Upcoming
- Recurring
- Completed
- Cancelled

Each item includes:
- Broadcast title or preview
- Date and time
- Recurrence details
- Status
- Recipient count

Actions:
- View
- Edit
- Reschedule
- Cancel

Use appropriate confirmation dialogs for destructive actions.

### 8. TELEGRAM GROUP MANAGEMENT

Create a clean group directory screen.

**Group list:**
- Search by group title
- Search by Unit number
- Group avatar or placeholder
- Group name
- Linked Unit
- Mapping status
- Broadcast eligibility

**Filters:**
- All groups
- Mapped
- Conflict
- Eligible
- Excluded

**Group details:**
- Group title
- Telegram chat ID
- Avatar availability
- Linked Unit number
- Mapping status
- Broadcast eligibility
- Eligibility explanation

Provide readable status labels, not color-only indicators.

### 9. UNIT MAPPING CONFLICT RESOLUTION

Create a dedicated conflict management interface.

A group becomes conflicting when:
- No matching Unit is found in Monday data.
- Multiple matching Units are found.

**Conflict card:**
- Telegram group title
- Detected numeric values
- Candidate Unit matches
- Conflict reason
- Resolve action

**Resolve screen:**
- Current group information
- Extracted numeric sequences
- Suggested matching Units
- Searchable Unit selector
- Selected Unit preview
- Confirm assignment action

Display an informative success state only after the real operation succeeds.

Provide empty, loading, and retry states.

### 10. COI AUDIT INTERFACE

The specification defines COI PDF submission through the Telegram bot chat. Keep that workflow intact.

Create a UI for viewing audit results in the Mini App only if the corresponding audit data is exposed to the frontend.

**Audit overview:**
- Latest audit
- Processing state
- Extracted VIN count
- Discrepancy count
- Warning count

**Section A — COI vs Monday discrepancies**

Display VINs present in the COI but absent from the configured Monday working groups.

Show:
- VIN
- Related Unit, when known
- Discrepancy description

**Section B — Telegram active group vs Monday status**

Display active Telegram groups whose related truck has one of the mismatching Monday statuses:

- SHOP
- INACTIVE
- AVAILIBLE

Show:
- Telegram group title
- Unit number
- Monday status
- Warning description

**Important:**

Do not label the Telegram group as inactive merely because Monday reports SHOP, INACTIVE, or AVAILIBLE.

The active Telegram group is the specified source of truth for this warning workflow.

Use warning cards and expandable details to make discrepancies easy to investigate.

### 11. ADMIN ACCESS INTERFACE

The Mini App is available only to authorized managers.

**Access-denied screen:**
- Clear restricted-access illustration/icon
- Short explanation
- Close button

**Administrator directory:**
- Authorized users
- Telegram User ID
- Username when available

**Add administrator:**
- Telegram User ID input
- Optional username support where available
- Validation
- Confirmation state

**Critical restriction:**

Do not implement administrator deletion through the Mini App.

Deletion is handled manually by the system administrator or DevOps engineer according to the specification.

### 12. SETTINGS SCREEN

Create a minimal settings page.

Include:
- Current admin profile
- Telegram theme preferences
- Language preference
- Notification preferences, if supported
- App version
- Help / About

Settings requiring backend support must be hidden or disabled until the corresponding capability exists.

### 13. UX STATES

Every screen must support:

- Initial loading
- Skeleton loading
- Empty results
- Search with no results
- Validation errors
- Network errors
- Unauthorized access
- Successful action
- Failed action
- Retry behavior

Never show a false success message.

Use toast notifications for lightweight feedback and confirmation dialogs for important actions.

### 14. MICROINTERACTIONS

Create smooth, subtle interactions.

Examples:
- Press feedback on buttons
- Animated selected states
- Bottom-sheet transitions
- Smooth search filtering
- Attachment preview transitions
- Loading indicators
- Success confirmation
- Pull-to-refresh where appropriate

Avoid animations that slow down operational workflows.

Respect reduced-motion preferences.

### 15. RESPONSIVE DESIGN

Primary target: Telegram Mini App on mobile.

Support:
- 320px narrow displays
- 360–430px common mobile widths
- Tablets
- Telegram Desktop

Requirements:
- No horizontal scrolling caused by layout overflow
- Keyboard-safe form interaction
- Safe-area support
- Proper bottom navigation spacing
- Readable long group names
- Responsive modal and bottom-sheet positioning
- Large enough controls for touch interaction

### 16. TELEGRAM MINI APP INTEGRATION

Implement appropriate Telegram WebApp frontend support.

Consider:
- Telegram theme parameters
- Safe-area insets
- Viewport changes
- Main/back navigation integration
- Expand behavior
- Haptic feedback when supported
- Native-feeling launch experience

Use official Telegram Mini App APIs and supported capabilities.

### 17. FRONTEND ARCHITECTURE

Recommended stack, if the project does not already define one:

- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- Lucide React
- Framer Motion or Motion
- Telegram Mini Apps SDK

Organize the frontend with reusable components, shared design tokens, typed UI models, and clear separation between presentation and data-access layers.

If the existing project uses another framework, preserve that architecture unless a migration is explicitly requested.

### 18. QUALITY REQUIREMENTS

The finished Mini App must have:

- Pixel-consistent spacing
- Professional visual hierarchy
- Consistent typography
- Clear actionable controls
- Accessible contrast
- Functional frontend navigation
- No broken layouts
- No placeholder buttons pretending to work
- No fabricated backend results
- No unnecessary UI clutter
- No dead-end navigation
- No confusing operational states

Validate on realistic mobile viewport sizes and both Telegram themes.

### 19. EXPECTED DELIVERABLES

1. Complete responsive Mini App UI.
2. Consistent design system.
3. All required screens and navigation.
4. Reusable frontend components.
5. Broadcast creation interface.
6. Group management interface.
7. Unit conflict resolution interface.
8. Audit results interface where data is available.
9. Scheduling management screens.
10. Administrator access screens.
11. Loading, empty, error, and success states.
12. Visual and responsive quality review.

**FINAL INSTRUCTION:**

Build the application as a polished internal enterprise product. Prioritize usability, operational clarity, performance, and visual consistency.

Do not change backend code, invent API capabilities, or alter business rules defined in the GFS Speaker technical specification.