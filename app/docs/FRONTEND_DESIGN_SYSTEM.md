# HajiriFlow Frontend Design System

## Product stance

HajiriFlow is an operations workspace for attendance, leave, device management, reporting, and payroll. The interface prioritizes trust, auditability, dense operational data, and fast repeated tasks over decorative marketing content.

## 1. Color

- Background: `#F4F6F3`
- Surface: `#FFFFFF`
- Subtle surface: `#F8FAF8`
- Text: `#17231F`
- Muted text: `#55645E`
- Border: `#DCE4DF`
- Primary: `#1B6F5A`
- Primary strong: `#145544`
- Primary soft: `#E2F2EC`
- Information: `#3268A8`
- Success: `#19724F`
- Warning: `#A26213`
- Danger: `#B3433C`
- Focus: `#2A7DF0`

Body text and controls target WCAG AA contrast. Status is never communicated by color alone; badges include text and indicators.

## 2. Typography

Use the native system sans-serif stack for fast rendering and broad platform support. Headings use compact negative tracking. Operational values use tabular numerals where alignment matters. Body copy remains short and direct.

## 3. Spacing

The base spacing rhythm is 4 pixels. Cards use 14 to 20 pixels of internal padding. Primary page sections use 14 to 18 pixel gaps. Data-heavy views remain compact without reducing touch targets below 39 pixels.

## 4. Layout

- Persistent desktop sidebar: 256 pixels
- Sticky top bar: 72 pixels
- Content maximum: 1560 pixels
- Desktop: four-column metrics and split operational dashboards
- Tablet: two-column cards and collapsible sidebar
- Mobile: single-column content, bottom-sheet modals, horizontally scrollable tables

## 5. Components

The system includes navigation groups, metric cards, filter toolbars, tables, badges, tabs, report cards, device cards, modals, command search, notifications, notices, empty states, and toasts.

Every component defines hover, focus, active, disabled, empty, warning, error, and responsive behavior. Destructive actions use a separate danger treatment and require confirmation.

## 6. Motion

Motion is restrained: 120 to 260 milliseconds using an ease-out curve. Pages fade and shift by only a few pixels. Modals scale subtly. `prefers-reduced-motion` disables non-essential transitions and animation.

## 7. Voice

Use clear operational language:

- “Add attendance” instead of “Create entry”
- “Review leave request” instead of “Process item”
- “Device needs attention” instead of vague failure copy

Avoid inflated claims, promotional slogans inside operational screens, and labels that hide consequences.

## 8. Brand

The visual identity uses a deep Nepal-ready forest green, neutral warm surfaces, clear status colors, line icons, and compact enterprise layouts. The logo mark is a simple “H” container rather than a copied vendor or biometric-device identity.

## 9. Anti-patterns

- Large marketing heroes inside authenticated workflows
- Decorative navigation that does not change screens
- Fake live operational claims
- Editable raw biometric evidence
- Color-only status
- Unbounded tables without filtering or pagination
- Hidden destructive outcomes
- Mixing production data with demo data without a visible label

## Information architecture

### Workspace

- Overview
- Attendance
- Employees
- Leave

### Operations

- Reports
- Devices
- Payroll

### Administration

- Organization
- Settings

## Prototype behavior

The Netlify frontend is an interactive prototype. Demo state is stored in browser `localStorage`. Forms, filtering, approvals, simulated device actions, exports, navigation, notifications, and reset controls work without claiming that the protected FastAPI, PostgreSQL, or biometric-worker services are online.
