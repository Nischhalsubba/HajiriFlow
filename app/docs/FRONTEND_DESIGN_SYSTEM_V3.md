# HajiriFlow Frontend Design System v3

## Product stance

HajiriFlow is an operational workforce platform for administrators, HR teams, payroll officers, managers, and device operators. The interface prioritizes evidence, exceptions, approvals, and task completion over promotional content.

## 1. Color

- Background: `#F5F7FA`
- Surface: `#FFFFFF`
- Sidebar: `#0B1220`
- Text: `#101828`
- Secondary text: `#475467`
- Muted text: `#667085`
- Border: `#E4E7EC`
- Primary action: `#2563EB`
- Teal operational accent: `#0F9F8F`
- Success: `#15803D`
- Warning: `#D97706`
- Danger: `#DC2626`
- Focus ring: `#84ADFF`

The palette avoids decorative gradients as a default. Color communicates state, hierarchy, and action priority. Body text and primary controls target WCAG AA contrast.

## 2. Typography

The system uses the native UI sans-serif stack with Inter as the preferred face. Headings use tight tracking and restrained scale. Tables and metrics use tabular numerals where values are compared. Captions remain at least 9px only inside dense administrative tables; primary body content remains 11–14px.

## 3. Spacing

The base rhythm is 4px. Common values are 8, 12, 16, 18, 24, and 28px. Cards use 16–18px padding. Dense tables use 9–15px cell padding depending on the selected density preference.

## 4. Layout

- Fixed 272px desktop sidebar
- Sticky 76px top bar
- Maximum content width of 1540px
- Four-column metric grid on large screens
- Two-column analytical layouts on desktop
- Single-column workflow on narrow screens
- Mobile navigation becomes an off-canvas drawer
- Dialogs become bottom sheets below 760px

## 5. Components

The system defines:

- Primary, secondary, ghost, success, and danger buttons
- Icon buttons and text actions
- Inputs, selects, textareas, filters, and search fields
- Metric cards and summary strips
- Panels and analytical charts
- Dense data tables with person cells and evidence sources
- Status pills for success, warning, danger, and neutral states
- Tabs, calendars, report cards, device cards, payroll tables, and organization cards
- Command palette, modal dialogs, toasts, empty states, and confirmation states

All components include hover, focus-visible, active, disabled, loading-compatible, and responsive behavior.

## 6. Motion

Transitions use 160ms with a restrained easing curve. Hover movement is limited to 1–2px. Modals, drawers, and toasts use short opacity and translation transitions. `prefers-reduced-motion` disables meaningful motion.

## 7. Voice

Copy is direct, operational, and specific. Page descriptions explain the underlying data relationship rather than using marketing claims. Actions use verbs such as “Generate draft,” “Reprocess day,” and “Sync users.” The interface avoids vague labels such as “Learn more” when a concrete task exists.

## 8. Brand

The HajiriFlow brand combines a dark operational shell with cobalt blue actions and teal evidence states. The H mark uses a simple structural glyph. Imagery is unnecessary for the application workspace; data visualizations, status treatments, and employee initials provide the visual language.

## 9. Anti-patterns

Do not use:

- Static KPI values embedded in HTML
- Fake testimonials or fabricated business outcomes
- Decorative hero panels inside the authenticated application
- One color for every state
- Unbounded tables without filters
- Hidden destructive actions
- Silent device simulations
- Payroll totals disconnected from attendance inputs
- Immutable caching for unversioned frontend assets

## Dynamic demo data contract

The demo engine generates departments, shifts, devices, employees, attendance, leave requests, payroll periods, and activity events on first load. It stores the coherent dataset in browser local storage. Every screen reads from that same state. Mutations update the shared state, recalculate dependent views, and survive refreshes. “Regenerate demo” produces a new dataset without changing the application code.

The generated provider is intentionally isolated behind `window.HFData`. A future Supabase provider can replace persistence and authentication without rewriting the presentation components.
