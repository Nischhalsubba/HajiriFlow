# Biometric privacy and device-enrollment policy

HajiriFlow treats biometric verification as a device-side capability, not an application data store.

## Data minimization

HajiriFlow MUST NOT ingest, persist, log, export, or return fingerprint templates, face templates, scans, photos, images, biometric passwords, or other biometric payloads. Device synchronization may keep only the minimum metadata needed to reconcile device identities with employees: an opaque external user identifier, active state, privilege label, template count, and a source hash. Raw attendance punches may record the verification method (for example `fingerprint`) but never the biometric sample or template.

The ingestion service rejects evidence/metadata keys that look like biometric, template, image, password, secret, or token material. Ordinary request logging records only request ID, method, route template, status, and duration.

## Purpose and consent

Biometric use is allowed only for a declared attendance-verification purpose and only after an organization has recorded the employee's decision against a named policy version. Consent, decline, and revocation decisions are append-only. General workforce administrators do not automatically receive biometric permissions; the dedicated `biometric_administrator` role is intentionally narrower.

A revoked or declined decision MUST NOT be interpreted as permission to enroll or re-enroll an employee on a biometric device.

## Retention

Because HajiriFlow does not store biometric templates, scans, or images, there is no application-side biometric payload to retain. Device-side biometric enrollment must be removed when consent is revoked, when the employee requests deletion, or when the organization otherwise determines the enrollment is no longer authorized.

HajiriFlow retains only the minimum governance evidence needed to prove what happened:

- append-only consent decision records;
- a deletion request and its status;
- a SHA-256 hash of the external deletion receipt when the device/provider confirms deletion;
- normal attendance evidence that contains no biometric sample/template.

Raw provider receipts must remain outside HajiriFlow. They may contain vendor or device details that are unnecessary for application operation; only their SHA-256 hash is accepted as completion evidence.

Organizations must define the retention period for non-biometric attendance and audit records according to their employment, accounting, and legal obligations. This repository intentionally does not invent a jurisdiction-specific retention duration.

## Deletion workflow

1. A user with `biometric.deletion.manage` requests deletion for a mapped device user.
2. HajiriFlow immediately disables the local device-user mapping and marks the synchronized device user inactive.
3. An authorized operator removes the enrollment from the physical device/provider using the supported vendor process.
4. The operator hashes the external completion receipt with SHA-256 outside HajiriFlow.
5. HajiriFlow records only that hash and marks the request complete.
6. If the external operation fails, HajiriFlow stores only a short non-sensitive failure code; secrets and raw provider errors are not accepted.

A completed record is an audit assertion that the external deletion was performed. Independent operational/security testing is still required before production launch.

## Logging and exports

Do not add biometric fields to request logs, analytics, frontend payloads, CSV exports, ordinary admin reports, support bundles, or exception messages. Any future adapter that requires biometric payload access must keep that processing inside the vendor/device boundary and must not return the payload through the `DeviceAdapter` abstraction.

## Vendor adapters

This policy does not claim support for any biometric hardware vendor. Concrete adapters may be added only after the supported hardware, authentication method, deletion semantics, rate limits, and failure behavior are known and testable. Vendor credentials must remain unique per device, encrypted with externally managed keys, revocable, and rotatable.
