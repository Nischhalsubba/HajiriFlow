# Accessibility baseline

HajiriFlow uses WCAG 2.2 Level AA as the interaction baseline for the browser application. Automated checks are regression guards, not a claim that every WCAG success criterion can be proven without manual testing and assistive-technology review.

## Keyboard and focus

- Interactive controls retain a visible focus indicator.
- The document reserves scroll space for the sticky application header so focused controls are not obscured when brought into view.
- Modal and command dialogs keep Tab and Shift+Tab focus inside the active dialog.
- Closing a dialog returns focus to the previously focused control when it still exists.
- Escape continues to close dialogs through the application keyboard handler.
- Wide data tables are labeled, keyboard-focusable horizontal scroll regions.
- Column headers receive `scope="col"`; action-only columns receive an accessible name.
- Production's skip link follows the visible production-status surface when the generated operational workspace is intentionally locked.

## Target sizes

Primary controls and form fields use at least a 44 CSS pixel block size. Compact row actions use at least 40 CSS pixels. These values exceed WCAG 2.2's 24 by 24 CSS pixel Target Size (Minimum) baseline while preserving the existing dense operations interface.

## Motion and contrast modes

- `prefers-reduced-motion: reduce` suppresses non-essential animation, transitions, and smooth scrolling.
- Forced-colors mode uses the platform `Highlight` color for focus outlines instead of relying on custom palette rendering.
- Status is communicated with text as well as color.

## Responsive data

Operational tables remain real tables and scroll horizontally on narrow screens instead of collapsing sensitive payroll or attendance fields into ambiguous card layouts. The scroll container itself is keyboard reachable and named for assistive technology.

## Sensitive workflow principles

- Payroll/salary routes are protected independently from workforce/attendance administration.
- The production frontend must not expose generated operational data when the authoritative API-backed provider is unavailable.
- Biometric interfaces must never render or transport biometric templates, images, or scans.
- Attendance corrections and payroll decisions should preserve the existing server-side reason, actor, checker, status, and immutable-history model when the authoritative operational frontend is connected.

## Verification

Repository checks cover focus-management contracts, target sizing, reduced motion, forced-colors focus, responsive table semantics, production skip-link behavior, and JavaScript syntax. The existing real Chromium/PostgreSQL authorization workflow exercises the frontend against the live test API whenever site assets change.

Before a production launch, also perform manual keyboard-only review, screen-reader review, browser zoom/reflow checks, contrast review in real content states, and independent security testing of authorization-sensitive workflows.
