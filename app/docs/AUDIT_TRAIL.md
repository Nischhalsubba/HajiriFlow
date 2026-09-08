# High-risk audit trail contract

HajiriFlow treats attendance corrections, payroll controls, device administration, and biometric governance as high-risk business domains. Audit records for those domains are append-only and are completed by a central session contract before persistence.

## Required evidence

Every business audit event whose action begins with `attendance.`, `payroll.`, `device.`, or `biometric.` must contain:

- an organization reference in `context_data.organization_id`;
- an actor reference and actor type (`user` or `system`);
- an action, target type, and target identifier;
- a request ID from the active HTTP request, or a generated `op-...` correlation ID for background/system work;
- a safe source marker in `context_data.source`;
- a redacted new-state snapshot in `after_data`;
- a previous-state snapshot when the operation changes known state;
- an approval reference for maker/checker, correction-decision, deletion-completion, and similar approval actions.

Creation and observational events may have no prior object state. Known payroll transitions are normalized centrally so the prior status is explicit even when the service historically recorded only the resulting run snapshot.

## Privacy

Audit payloads use the same recursive redaction contract as the rest of the identity layer. Passwords, tokens, device secrets, bank-account identifiers, national identifiers, and biometric/template fields are redacted before the record is committed.

Business audit records are immutable: application-level update/delete hooks reject mutation after insert, and the database migration also protects the audit table against UPDATE and DELETE.

## Correlation and background work

HTTP-originated events inherit the middleware request ID. Background operations have no HTTP request, so the audit contract generates an opaque `op-<uuid>` correlation identifier. This is an operation correlation ID, not a fabricated client request ID.

## Approval references

For approval-class actions, `context_data.approval_reference` identifies the governed object or workflow request. Domain-specific history remains authoritative for detailed maker/checker lineage:

- attendance corrections retain the correction record, requester, decision-maker, reason, and immutable attendance history;
- payroll retains run/period maker-checker fields and append-only payroll history;
- biometric deletion retains the deletion request and hashed external completion receipt.

## Verification boundary

These controls provide application-internal evidence. They do not replace independent authorization, payroll-control, or biometric/privacy testing before production launch.
