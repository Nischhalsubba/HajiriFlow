<div align="center">

# HajiriFlow

**An attendance and workforce-flow product repository focused on making daily presence, records, review, and operational follow-up easier to understand.**

![Top language](https://img.shields.io/github/languages/top/Nischhalsubba/HajiriFlow?style=flat-square)
![Last commit](https://img.shields.io/github/last-commit/Nischhalsubba/HajiriFlow?style=flat-square)
![Repo size](https://img.shields.io/github/repo-size/Nischhalsubba/HajiriFlow?style=flat-square)

[Browse source](https://github.com/Nischhalsubba/HajiriFlow/tree/main) · [Issues](https://github.com/Nischhalsubba/HajiriFlow/issues)

</div>

## Overview

**HajiriFlow** is documented as an attendance-oriented operational product. The README describes the system in human terms first, then maps those ideas to the software so employees, managers, designers, developers, and reviewers can share the same mental model.

| Audience | Focus |
|---|---|
| Employees | Understand attendance actions and status |
| Managers / operations | Review records and exceptions |
| Developers | UI, application rules, data and state transitions |
| Designers | Dense operational workflows, errors, permissions and mobile use |

<details open>
<summary><strong>🏗️ Interactive product architecture</strong></summary>

```mermaid
flowchart LR
    PERSON["Employee / operator"] --> UI["HajiriFlow interface"]
    UI --> ACTION["Attendance action"]
    ACTION --> RULES["Validation / business rules"]
    RULES --> RECORDS["Attendance records"]
    RECORDS --> REVIEW["Manager / operations review"]
    REVIEW --> STATUS["Approved / corrected / follow-up state"]
    STATUS --> UI
```

</details>

## Operational flow

```mermaid
flowchart TD
    START["Start workday / attendance task"] --> ACTION["Record or review attendance"]
    ACTION --> VALIDATE["Validate time / required information"]
    VALIDATE -->|Needs attention| FIX["Explain exception"]
    FIX --> ACTION
    VALIDATE -->|Valid| SAVE["Store record"]
    SAVE --> REVIEW["Review when required"]
    REVIEW --> DONE["Final status"]
```

## Getting started

```bash
git clone https://github.com/Nischhalsubba/HajiriFlow.git
cd HajiriFlow
```

Use the committed manifests and lockfiles to determine the current runtime and development commands.

## Product & design principles

Operational software should make state visible. Show what was recorded, when it happened, who can change it, why something is blocked, and what the next step is. Preserve keyboard access, clear tables, responsive layouts, explicit empty/error states, and readable audit context.

## SEO & discoverability

Use terms such as **attendance management, employee attendance, workforce attendance, attendance workflow, time records, and HR operations** only when they accurately describe implemented product behavior. Public metadata should remain specific, useful and non-misleading.

## Contribution flow

```mermaid
flowchart LR
    RULE["Workflow / rule change"] --> IMPACT["Map affected states"] --> BUILD["Implement"] --> TEST["Test happy + exception paths"] --> REVIEW["UX / data review"] --> PR["Pull request"]
```
