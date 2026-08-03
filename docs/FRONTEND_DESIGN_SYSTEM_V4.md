# HajiriFlow Frontend Design System v4

## 1. Color

HajiriFlow uses neutral operational surfaces with an indigo action color and cyan evidence accent.

- Canvas: `#F6F7FB`
- Surface: `#FFFFFF`
- Sidebar: `#101828`
- Primary: `#4F46E5`
- Accent: `#0E7490`
- Success: `#16803D`
- Warning: `#B54708`
- Danger: `#D92D20`
- Text: `#172033`
- Muted text: `#667085`
- Focus: `#7F8CFF`

Status colors communicate meaning. They are not decorative chart confetti.

## 2. Typography

The interface uses the native system sans-serif stack for speed and predictable rendering.

- Browser root: 16px
- Page title: 22px
- Main greeting: 26–34px using `clamp`
- Panel heading: 17px
- Body and controls: 14–16px
- Table body: 13px
- Supporting text: 12px minimum
- Eyebrows and metadata: 11px minimum

Numerical values use tabular figures. No operational text should render below 11px.

## 3. Spacing

The spacing system is based on 4px increments, with practical control sizes rather than ornamental emptiness.

- Touch targets: 42px minimum, 44px preferred
- Card padding: 20–22px
- Page gutters: 22–52px responsively
- Section gap: 24px
- Grid gap: 16–18px

## 4. Layout

- Expanded desktop sidebar: 284px
- Collapsed desktop sidebar: 84px
- Tablet and mobile sidebar: off-canvas, 294px
- Top bar: 80px desktop, 70px compact
- Workspace: fluid width with no arbitrary 1600px cap
- Dashboard: two-column analytical layout, collapsing at 1320px
- Primary mobile breakpoint: 820px
- Small phone breakpoint: 560px

## 5. Components

All buttons, inputs, selects, table actions, navigation rows, dialogs, cards, and status pills use the same radius, focus, and type hierarchy.

States required:

- Default
- Hover
- Active
- Focus-visible
- Disabled
- Loading
- Success
- Warning
- Error
- Empty

Tables remain horizontally scrollable on small screens because hiding payroll or attendance columns would be a particularly creative form of data loss.

## 6. Motion

- Navigation and layout transition: 220ms
- Hover and component transition: 160ms
- Reduced-motion media query disables nonessential animation
- No looping decorative animation

## 7. Voice

- Direct and operational
- Use verbs for actions: “Add employee”, “Approve leave”, “Export payroll”
- Use specific empty-state guidance
- Avoid vague labels such as “Process” or “Manage” without an object

## 8. Brand

HajiriFlow should feel like reliable workforce infrastructure for Nepal, not a generic analytics template. The visual system combines a dark operational navigation rail, calm surfaces, restrained indigo actions, and explicit evidence states.

## 9. Anti-patterns

- Text below 11px
- Fixed narrow content canvases on large displays
- Hamburger controls that do nothing on desktop
- Card grids with identical visual priority
- Meaning conveyed only through color
- Hidden table columns on mobile
- Permanent sidebars on tablet widths
- Unlabeled icon-only controls
