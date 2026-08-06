<!-- interactive-readme-standard:start -->

<div align="center">

# HajiriFlow

**Branch-aware technical guide for [`agent/frontend-application-redesign`](https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign)**

<p><img alt="branch: agent/frontend-application-redesign" src="https://img.shields.io/static/v1?label=&message=branch%3A%20agent%2Ffrontend-application-redesign&color=5965F2&style=flat-square"> <img alt="Python" src="https://img.shields.io/static/v1?label=&message=Python&color=24292F&style=flat-square"> <img alt="Docker" src="https://img.shields.io/static/v1?label=&message=Docker&color=24292F&style=flat-square"> <img alt="Docker Compose" src="https://img.shields.io/static/v1?label=&message=Docker%20Compose&color=24292F&style=flat-square"> <img alt="JavaScript" src="https://img.shields.io/static/v1?label=&message=JavaScript&color=24292F&style=flat-square"> <img alt="CSS" src="https://img.shields.io/static/v1?label=&message=CSS&color=24292F&style=flat-square"> <img alt="HTML" src="https://img.shields.io/static/v1?label=&message=HTML&color=24292F&style=flat-square"> <img alt="docs: branch-aware" src="https://img.shields.io/static/v1?label=&message=docs%3A%20branch-aware&color=8250DF&style=flat-square"></p>

<p>
  <a href="https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign"><strong>Browse source</strong></a> ·
  <a href="https://github.com/Nischhalsubba/HajiriFlow/issues"><strong>Issues</strong></a> ·
  <a href="https://github.com/Nischhalsubba/HajiriFlow/codespaces/new?ref=agent%2Ffrontend-application-redesign"><strong>Open in Codespaces</strong></a>
</p>

</div>

> [!IMPORTANT]
> This guide is generated from the files actually present on `agent/frontend-application-redesign`. It links to detected source paths, preserves project-authored notes, and avoids claiming components that were not found.

## At a glance

| Item | Detected value |
|---|---|
| Purpose | A web or interface project documented from the files currently present on this branch. |
| Branch role | Compared with `main` |
| Stack | Python, Docker, Docker Compose, JavaScript, CSS, HTML |
| Manifests | pyproject.toml, Dockerfile, compose.yaml |
| Prerequisites | Python |
| Delivery | Dockerfile, compose.yaml, netlify.toml, GitHub Actions |
| License | No license file detected |

## Branch scope

This branch differs from the default branch in the following detected paths:

- [`.github/workflows/ci.yml`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/.github/workflows/ci.yml)
- [`README.md`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/README.md)
- [`site/assets/app.js`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/site/assets/app.js)
- [`site/assets/core.js`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/site/assets/core.js)
- [`site/assets/enhancements.js`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/site/assets/enhancements.js)
- [`site/assets/forms.js`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/site/assets/forms.js)
- [`site/assets/styles-components.css`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/site/assets/styles-components.css)
- [`site/assets/styles-responsive.css`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/site/assets/styles-responsive.css)
- [`site/assets/styles.css`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/site/assets/styles.css)
- [`site/assets/ui-core.js`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/site/assets/ui-core.js)
- [`site/assets/views-operations.js`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/site/assets/views-operations.js)
- [`site/assets/views-workforce.js`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/site/assets/views-workforce.js)

## Quick start

```bash
python -m venv .venv
pip install -e .
```

### Configuration surface

- `.env.example`

> Never commit secrets, private keys, production credentials, customer data, or unredacted infrastructure details.

## Repository map

```mermaid
flowchart TD
    ROOT["HajiriFlow / agent/frontend-application-redesign"]
    ROOT --> P0[".github/"]
    ROOT --> P1["docs/"]
    ROOT --> P2["migrations/"]
    ROOT --> P3["site/"]
    ROOT --> P4["src/"]
    ROOT --> P5["tests/"]
    ROOT --> P6[".env.example"]
    ROOT --> P7[".gitignore"]
    ROOT --> P8["alembic.ini"]
    ROOT --> P9["compose.yaml"]
    ROOT --> P10["Dockerfile"]
    ROOT --> P11["netlify.toml"]
    ROOT --> P12["pyproject.toml"]
```

| Responsibility | Detected source paths |
|---|---|
| Interface | [`site`](https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign/site), [`src`](https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign/src) |
| Data | [`migrations`](https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign/migrations) |
| Quality | [`tests`](https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign/tests) |
| Documentation | [`docs`](https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign/docs) |
| Delivery | [`.github`](https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign/.github) |

## Website or application map

```mermaid
flowchart TD
    APP["HajiriFlow"]
    APP --> R0["site"]
    R0 --> F0["site/index.html"]
```

## Architecture and responsibility flow

```mermaid
flowchart LR
    USER["User / contributor"]
    USER --> A0["Interface: site, src"]
    A0 --> A1["Data: migrations"]
    A1 --> A2["Quality: tests"]
    A2 --> A3["Documentation: docs"]
    A3 --> A4["Delivery: .github"]
    A4 --> DELIVERY["Delivery: Dockerfile, compose.yaml, netlify.toml, GitHub Actions"]
```

<details>
<summary><strong>Authentication and authorization flow</strong></summary>

```mermaid
flowchart LR
    USER["User"] --> SIGNIN["Sign-in or identity step"]
    SIGNIN --> VERIFY["Verify credentials / session"]
    VERIFY --> AUTHORIZE["Resolve permissions"]
    AUTHORIZE --> PROTECTED["Protected feature or data"]
    VERIFY -->|failure| RECOVER["Error or recovery path"]
```

Relevant detected files: [`tests/test_permissions.py`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/tests/test_permissions.py), [`src/hajiriflow/identity/permissions.py`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/src/hajiriflow/identity/permissions.py), [`src/hajiriflow/db/session.py`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/src/hajiriflow/db/session.py).

> The diagram expresses the responsibility sequence only. Confirm exact providers, token formats, roles, and recovery behavior in the linked source.

</details>
<details>
<summary><strong>Data flow and model surface</strong></summary>

```mermaid
flowchart LR
    INPUT["User or system input"] --> VALIDATE["Validate and normalize"]
    VALIDATE --> LOGIC["Application logic"]
    LOGIC --> STORE["Persistent or local storage"]
    STORE --> READ["Query / retrieval"]
    READ --> OUTPUT["UI, API, report, or export"]
```

Detected data areas: [`migrations`](https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign/migrations), [`migrations/script.py.mako`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/migrations/script.py.mako), [`migrations/env.py`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/migrations/env.py), [`migrations/versions/20260803_0001_identity_foundation.py`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/migrations/versions/20260803_0001_identity_foundation.py), [`tests/test_database.py`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/tests/test_database.py), [`src/hajiriflow/db/models/__init__.py`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/src/hajiriflow/db/models/__init__.py), [`src/hajiriflow/db/models/identity.py`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/src/hajiriflow/db/models/identity.py).

</details>
<details>
<summary><strong>Background jobs and scheduled work</strong></summary>

```mermaid
flowchart LR
    EVENT["Event / schedule"] --> QUEUE["Queue or job definition"]
    QUEUE --> WORKER["Worker / processor"]
    WORKER --> RESULT["Persist result or emit side effect"]
    WORKER -->|failure| RETRY["Retry, alert, or dead-letter path"]
```

Relevant detected files: [`src/hajiriflow/worker/__init__.py`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/src/hajiriflow/worker/__init__.py), [`src/hajiriflow/worker/__main__.py`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/src/hajiriflow/worker/__main__.py).

</details>

## Quality, security, and operations

<table>
<tr>
<td width="33%" valign="top">

### Quality

- [`tests`](https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign/tests)

Detected commands:
- No standard quality command detected.

</td>
<td width="33%" valign="top">

### Security

- No dedicated security policy or automated dependency configuration was detected.

Review authentication, authorization, input validation, dependency updates, secret handling, and failure recovery before release.

</td>
<td width="34%" valign="top">

### Observability

- No dedicated observability integration was detected automatically.

Define useful logs, metrics, traces, alerts, and rollback signals for production-facing branches.

</td>
</tr>
</table>

## Delivery flow

```mermaid
flowchart LR
    CHANGE["Change on agent/frontend-application-redesign"] --> CHECK["Tests and quality checks"]
    CHECK --> REVIEW["Review architecture and documentation impact"]
    REVIEW --> BUILD["Build or package"]
    BUILD --> DEPLOY["Deploy or release"]
    DEPLOY --> VERIFY["Verify health and rollback readiness"]
```

### Automation detected

- [`.github/workflows/ci.yml`](https://github.com/Nischhalsubba/HajiriFlow/blob/agent/frontend-application-redesign/.github/workflows/ci.yml)

## Contribution flow

```mermaid
flowchart LR
    FORK["Create branch"] --> CHANGE["Make focused change"]
    CHANGE --> TEST["Run relevant checks"]
    TEST --> DOCS["Update README and diagrams"]
    DOCS --> PR["Open pull request"]
    PR --> REVIEW["Review and iterate"]
    REVIEW --> MERGE["Merge when ready"]
```

- Keep changes focused and explain architectural consequences.
- Run the checks relevant to the changed area.
- Update diagrams whenever routes, modules, data models, authentication, jobs, or delivery paths change.
- Add screenshots or recordings for visual behavior changes when useful.
- Use issues for reproducible defects and pull requests for reviewable changes.

## Ownership and support

| Topic | Source |
|---|---|
| Repository | [`Nischhalsubba/HajiriFlow`](https://github.com/Nischhalsubba/HajiriFlow) |
| Branch | [`agent/frontend-application-redesign`](https://github.com/Nischhalsubba/HajiriFlow/tree/agent/frontend-application-redesign) |
| Ownership | No CODEOWNERS file detected |
| Contributing | Use the contribution flow above |
| Support | [Open or review issues](https://github.com/Nischhalsubba/HajiriFlow/issues) |
| License | No license file detected |

<details>
<summary><strong>Documentation maintenance checklist</strong></summary>

- [ ] Purpose and branch scope are accurate.
- [ ] Setup and configuration commands still work.
- [ ] Repository, application, API, data, authentication, job, and deployment diagrams match the code.
- [ ] Tests, security controls, observability, and rollback behavior are documented.
- [ ] Links point to real files on this branch.
- [ ] No secrets or private operational details are exposed.

</details>

<!-- interactive-readme-standard:end -->

<!-- project-authored-notes:start -->
<details>
<summary><strong>Project-authored notes preserved from this branch</strong></summary>

# HajiriFlow

Attendance to payroll, with every record accounted for.

HajiriFlow is a Nepal-ready workforce platform for biometric attendance, employee management, leave, field duty, reporting, employee self-service, and payroll. Device vendors are integrations, not the product architecture.

## Baseline scope

The accepted baseline contains 66 tracked capabilities across:

- secure accounts, multi-role permissions, and redacted audit history;
- company structure, employees, shifts, and effective assignments;
- biometric device registry, diagnostics, scheduling, pulling, identity sync, migration, and encrypted archives;
- immutable raw punches, manual correction approvals, and spreadsheet imports;
- AD/BS calendar services, holidays, leave balances and approvals, and kaaj/field duty;
- a shared attendance engine for daily status, late/early time, overtime, overnight shifts, and locked periods;
- daily, absence, department, monthly, Hajiri, and attendance-to-salary reports with Excel/PDF/print outputs;
- fiscal years, salary heads, deductions, tax slabs, payroll runs, payslips, annual summaries, and employee self-service;
- backup, restore, monitoring, deployment, and recovery controls.

See:

- [Baseline product scope](docs/PRODUCT_SCOPE.md)
- [Feature matrix](docs/FEATURE_MATRIX.md)
- [Implementation sequence](docs/IMPLEMENTATION_SEQUENCE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Domain model](docs/DATA_MODEL.md)
- [Independent development policy](docs/INDEPENDENT_DEVELOPMENT.md)

## Current status

Foundation infrastructure is complete. Product modules are being implemented in dependency order, beginning with database migrations, identity, and deny-by-default authorization.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Web health check: `http://localhost:8000/health`

## Local development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn hajiriflow.main:app --reload
pytest
```

## Architecture principles

1. Raw biometric punches are immutable.
2. PostgreSQL is the sole runtime source of configuration.
3. Web and device-worker processes run separately.
4. Permissions are deny-by-default.
5. Unknown roles never inherit access.
6. Manual or synthetic attendance is attributed, approved where required, and audited.
7. Payroll uses approved and locked attendance snapshots.
8. Device-specific behavior stays behind adapters.
9. User-visible design, implementation, tests, and documentation are independently created for HajiriFlow.

## License

A HajiriFlow license has not yet been selected. Until one is added, all rights are reserved.

</details>
<!-- project-authored-notes:end -->
