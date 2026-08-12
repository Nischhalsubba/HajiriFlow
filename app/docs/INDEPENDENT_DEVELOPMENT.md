# Independent Development Policy

HajiriFlow is an independently designed and implemented product. This policy applies to every contributor, generated patch, design file, migration, test, and document committed to the repository.

## Purpose

The project may study publicly observable product behavior to understand common attendance-management workflows. It must not reproduce another project's source code, templates, written documentation, visual assets, database migrations, test fixtures, hidden implementation details, or distinctive internal structure.

## Allowed inputs

Contributors may use:

- user-provided business requirements;
- publicly observable capabilities and workflows;
- device protocol documentation and SDK documentation used under their own licenses;
- public standards, government rules, and official tax or labor guidance;
- independently created wireframes, schemas, algorithms, tests, and copy;
- generic domain knowledge such as attendance, leave, payroll, audit, and reporting concepts.

## Prohibited inputs

Do not copy or adapt:

- source files, functions, classes, queries, migrations, or comments from another application;
- HTML, CSS, JavaScript, templates, screenshots, icons, logos, or downloadable assets from another product;
- README wording, troubleshooting text, report descriptions, or installation instructions;
- database table layouts merely because another implementation used them;
- distinctive route names, file organization, variable names, or error messages;
- fingerprint templates, production data, credentials, or personally identifiable information.

## Required development method

For every module:

1. Write a HajiriFlow requirement describing the user outcome.
2. Define permissions, failure states, audit behavior, and privacy controls.
3. Design the domain model and API from HajiriFlow's architecture principles.
4. Implement from the written requirement without consulting third-party source code.
5. Add tests based on HajiriFlow acceptance criteria.
6. Record important design decisions in an ADR when multiple reasonable approaches exist.

## Naming and user experience

HajiriFlow uses its own terminology, navigation, report layouts, visual language, and interaction patterns. Generic Nepali administrative terms such as attendance, hajiri, bida, kaaj, and talab may be used because they describe the domain, not a particular implementation.

## Device integrations

Vendor support must be isolated behind adapters. The core application may not depend on a vendor-specific schema. Device adapters return normalized users, credentials metadata, and punch events to the application service layer.

## Verification checklist

A reviewer approving a feature confirms that:

- the implementation was written for HajiriFlow;
- no third-party code or assets were copied;
- new dependencies have compatible licenses;
- tests describe HajiriFlow behavior rather than another application's internals;
- user-visible copy and layouts are original;
- privacy, audit, and authorization requirements are covered.
