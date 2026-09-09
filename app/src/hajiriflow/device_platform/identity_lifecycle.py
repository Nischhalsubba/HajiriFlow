import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.db.models.device import Device, DeviceEmployeeMapping, DeviceUser
from hajiriflow.db.models.device_identity import DeviceArchive, DeviceIdentityAction
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.workforce import Employee
from hajiriflow.db.models.workforce_profile import EmployeeProfile
from hajiriflow.device_platform.adapters import (
    DeviceAdapter,
    DeviceIdentityBundle,
    DeviceWriteResult,
)
from hajiriflow.device_platform.crypto import DeviceSecretCipher
from hajiriflow.device_platform.privacy import BiometricPrivacyService
from hajiriflow.device_platform.service import DevicePlatformService

ACTION_TYPES = {"push_users", "migrate_users", "archive_export", "archive_restore"}
MAX_ACTION_ROWS = 200


def utc_now() -> datetime:
    return datetime.now(UTC)


def _canonical_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _bundle_payload(bundle: DeviceIdentityBundle) -> dict:
    return asdict(bundle)


def _bundle_from_payload(payload: object) -> DeviceIdentityBundle:
    if not isinstance(payload, dict):
        raise ValueError("archive identity bundle is invalid")
    external_user_id = payload.get("external_user_id")
    if not isinstance(external_user_id, str) or not external_user_id:
        raise ValueError("archive identity bundle is missing external_user_id")
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict) or not all(
        isinstance(key, str)
        and isinstance(value, (str, int, bool, type(None)))
        for key, value in metadata.items()
    ):
        raise ValueError("archive identity metadata is invalid")
    biometric_payload = payload.get("biometric_payload")
    if biometric_payload is not None and not isinstance(biometric_payload, str):
        raise ValueError("archive biometric payload is invalid")
    return DeviceIdentityBundle(
        external_user_id=external_user_id,
        display_name=(str(payload["display_name"]) if payload.get("display_name") else None),
        privilege=(str(payload["privilege"]) if payload.get("privilege") else None),
        active=bool(payload.get("active", True)),
        template_count=max(0, int(payload.get("template_count", 0))),
        metadata=metadata,
        biometric_payload=biometric_payload,
    )


class DeviceIdentityLifecycleService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.platform = DevicePlatformService(session)
        self.privacy = BiometricPrivacyService(session)

    def _device(self, organization_id: UUID, device_id: UUID) -> Device:
        item = self.session.get(Device, device_id)
        if not item or item.organization_id != organization_id:
            raise LookupError("device not found")
        return item

    def _employee(self, organization_id: UUID, employee_id: UUID) -> Employee:
        item = self.session.get(Employee, employee_id)
        if not item or item.organization_id != organization_id:
            raise LookupError("employee not found")
        return item

    def _device_user(
        self,
        organization_id: UUID,
        device_id: UUID,
        device_user_id: UUID,
    ) -> DeviceUser:
        item = self.session.get(DeviceUser, device_user_id)
        if (
            not item
            or item.organization_id != organization_id
            or item.device_id != device_id
        ):
            raise LookupError("device user not found")
        return item

    def _target_user(self, device_id: UUID, external_user_id: str) -> DeviceUser | None:
        return self.session.scalar(
            select(DeviceUser).where(
                DeviceUser.device_id == device_id,
                DeviceUser.external_user_id == external_user_id,
                DeviceUser.active.is_(True),
            )
        )

    def _mapping(self, device_user_id: UUID) -> DeviceEmployeeMapping | None:
        return self.session.scalar(
            select(DeviceEmployeeMapping).where(
                DeviceEmployeeMapping.device_user_id == device_user_id,
                DeviceEmployeeMapping.status == "active",
            )
        )

    def _biometric_move_allowed(
        self,
        *,
        organization_id: UUID,
        device_user: DeviceUser,
    ) -> tuple[bool, UUID | None, str | None]:
        if device_user.template_count <= 0:
            mapping = self._mapping(device_user.id)
            return True, mapping.employee_id if mapping else None, None
        mapping = self._mapping(device_user.id)
        if mapping is None:
            return False, None, "biometric_identity_is_not_mapped"
        consent = self.privacy.latest_consent(
            organization_id=organization_id,
            employee_id=mapping.employee_id,
        )
        if consent is None or consent.decision != "granted":
            return False, mapping.employee_id, "biometric_consent_not_granted"
        return True, mapping.employee_id, None

    def compare_device(
        self,
        *,
        organization_id: UUID,
        device_id: UUID,
    ) -> dict:
        self._device(organization_id, device_id)
        device_users = list(
            self.session.scalars(
                select(DeviceUser)
                .where(
                    DeviceUser.organization_id == organization_id,
                    DeviceUser.device_id == device_id,
                    DeviceUser.active.is_(True),
                )
                .order_by(DeviceUser.external_user_id)
            ).all()
        )
        employees = list(
            self.session.scalars(
                select(Employee)
                .where(
                    Employee.organization_id == organization_id,
                    Employee.status == "active",
                )
                .order_by(Employee.employee_code)
            ).all()
        )
        profiles = {
            item.employee_id: item
            for item in self.session.scalars(
                select(EmployeeProfile).where(
                    EmployeeProfile.organization_id == organization_id
                )
            ).all()
        }
        mappings = {
            item.device_user_id: item.employee_id
            for item in self.session.scalars(
                select(DeviceEmployeeMapping).where(
                    DeviceEmployeeMapping.organization_id == organization_id,
                    DeviceEmployeeMapping.device_id == device_id,
                    DeviceEmployeeMapping.status == "active",
                )
            ).all()
        }
        mapped_employee_ids = set(mappings.values())
        unknown = [
            {
                "device_user_id": str(user.id),
                "external_user_id": user.external_user_id,
                "display_name": user.display_name,
                "template_count": user.template_count,
            }
            for user in device_users
            if user.id not in mappings
        ]
        missing: list[dict] = []
        for employee in employees:
            if employee.id in mapped_employee_ids:
                continue
            profile = profiles.get(employee.id)
            missing.append(
                {
                    "employee_id": str(employee.id),
                    "employee_code": employee.employee_code,
                    "display_name": employee.display_name,
                    "attendance_id": profile.attendance_id if profile else None,
                    "ready_for_enrollment": bool(profile and profile.attendance_id),
                }
            )
        return {
            "device_id": str(device_id),
            "registered_count": len(device_users),
            "mapped_count": len(mapped_employee_ids),
            "unknown_count": len(unknown),
            "missing_count": len(missing),
            "unknown_users": unknown,
            "missing_employees": missing,
        }

    def _push_preview(
        self,
        *,
        organization_id: UUID,
        target_device_id: UUID,
        employee_ids: list[UUID],
    ) -> dict:
        self._device(organization_id, target_device_id)
        if not employee_ids or len(employee_ids) > MAX_ACTION_ROWS:
            raise ValueError("select between 1 and 200 employees")
        rows: list[dict] = []
        blocking = 0
        for employee_id in employee_ids:
            employee = self._employee(organization_id, employee_id)
            profile = self.session.get(EmployeeProfile, employee.id)
            if not profile or profile.attendance_id is None:
                rows.append(
                    {
                        "employee_id": str(employee.id),
                        "external_user_id": None,
                        "status": "invalid",
                        "code": "attendance_id_required",
                    }
                )
                blocking += 1
                continue
            external_user_id = str(profile.attendance_id)
            existing = self._target_user(target_device_id, external_user_id)
            if existing is not None:
                mapping = self._mapping(existing.id)
                if mapping and mapping.employee_id == employee.id:
                    rows.append(
                        {
                            "employee_id": str(employee.id),
                            "external_user_id": external_user_id,
                            "status": "already_present",
                            "code": "already_mapped",
                        }
                    )
                else:
                    rows.append(
                        {
                            "employee_id": str(employee.id),
                            "external_user_id": external_user_id,
                            "status": "conflict",
                            "code": "target_external_id_conflict",
                        }
                    )
                    blocking += 1
                continue
            rows.append(
                {
                    "employee_id": str(employee.id),
                    "external_user_id": external_user_id,
                    "status": "ready",
                    "code": "ready",
                }
            )
        return {"rows": rows, "blocking_count": blocking}

    def _source_user_preview(
        self,
        *,
        organization_id: UUID,
        source_device_id: UUID,
        device_user_ids: list[UUID],
        target_device_id: UUID | None = None,
    ) -> dict:
        self._device(organization_id, source_device_id)
        if target_device_id is not None:
            if target_device_id == source_device_id:
                raise ValueError("source and target devices must be different")
            self._device(organization_id, target_device_id)
        if not device_user_ids or len(device_user_ids) > MAX_ACTION_ROWS:
            raise ValueError("select between 1 and 200 device users")
        rows: list[dict] = []
        blocking = 0
        for device_user_id in device_user_ids:
            user = self._device_user(
                organization_id,
                source_device_id,
                device_user_id,
            )
            allowed, employee_id, consent_code = self._biometric_move_allowed(
                organization_id=organization_id,
                device_user=user,
            )
            status_value = "ready"
            code = "ready"
            if not allowed:
                status_value = "blocked"
                code = consent_code or "biometric_move_blocked"
                blocking += 1
            elif target_device_id is not None:
                existing = self._target_user(target_device_id, user.external_user_id)
                if existing is not None:
                    status_value = "conflict"
                    code = "target_external_id_conflict"
                    blocking += 1
            rows.append(
                {
                    "device_user_id": str(user.id),
                    "external_user_id": user.external_user_id,
                    "employee_id": str(employee_id) if employee_id else None,
                    "template_count": user.template_count,
                    "status": status_value,
                    "code": code,
                }
            )
        return {"rows": rows, "blocking_count": blocking}

    def _restore_preview(
        self,
        *,
        organization_id: UUID,
        target_device_id: UUID,
        archive_id: UUID,
    ) -> dict:
        self._device(organization_id, target_device_id)
        archive = self.session.get(DeviceArchive, archive_id)
        if not archive or archive.organization_id != organization_id:
            raise LookupError("device archive not found")
        manifest_rows = archive.manifest_data.get("rows", [])
        if not isinstance(manifest_rows, list):
            raise ValueError("device archive manifest is invalid")
        rows: list[dict] = []
        blocking = 0
        for manifest in manifest_rows:
            if not isinstance(manifest, dict):
                raise ValueError("device archive manifest row is invalid")
            external_user_id = str(manifest.get("external_user_id", ""))
            employee_id_text = manifest.get("employee_id")
            template_count = max(0, int(manifest.get("template_count", 0)))
            status_value = "ready"
            code = "ready"
            if not external_user_id:
                status_value = "blocked"
                code = "archive_external_id_missing"
                blocking += 1
            elif self._target_user(target_device_id, external_user_id) is not None:
                status_value = "conflict"
                code = "target_external_id_conflict"
                blocking += 1
            elif template_count > 0:
                if not employee_id_text:
                    status_value = "blocked"
                    code = "archive_biometric_identity_is_not_mapped"
                    blocking += 1
                else:
                    employee_id = UUID(str(employee_id_text))
                    consent = self.privacy.latest_consent(
                        organization_id=organization_id,
                        employee_id=employee_id,
                    )
                    if consent is None or consent.decision != "granted":
                        status_value = "blocked"
                        code = "biometric_consent_not_granted"
                        blocking += 1
            rows.append(
                {
                    "external_user_id": external_user_id,
                    "employee_id": employee_id_text,
                    "template_count": template_count,
                    "status": status_value,
                    "code": code,
                }
            )
        return {"rows": rows, "blocking_count": blocking}

    def preview_action(
        self,
        *,
        organization_id: UUID,
        action_type: str,
        requested_by: UUID,
        source_device_id: UUID | None = None,
        target_device_id: UUID | None = None,
        employee_ids: list[UUID] | None = None,
        device_user_ids: list[UUID] | None = None,
        archive_id: UUID | None = None,
    ) -> DeviceIdentityAction:
        if action_type not in ACTION_TYPES:
            raise ValueError("unsupported device identity action")
        request_data: dict = {}
        if action_type == "push_users":
            if target_device_id is None:
                raise ValueError("push preview requires a target device")
            selected = employee_ids or []
            preview = self._push_preview(
                organization_id=organization_id,
                target_device_id=target_device_id,
                employee_ids=selected,
            )
            request_data["employee_ids"] = [str(item) for item in selected]
        elif action_type in {"migrate_users", "archive_export"}:
            if source_device_id is None:
                raise ValueError("source device is required")
            if action_type == "migrate_users" and target_device_id is None:
                raise ValueError("migration preview requires a target device")
            selected_users = device_user_ids or []
            preview = self._source_user_preview(
                organization_id=organization_id,
                source_device_id=source_device_id,
                device_user_ids=selected_users,
                target_device_id=(
                    target_device_id if action_type == "migrate_users" else None
                ),
            )
            request_data["device_user_ids"] = [str(item) for item in selected_users]
        else:
            if target_device_id is None or archive_id is None:
                raise ValueError("archive restore requires archive and target device")
            preview = self._restore_preview(
                organization_id=organization_id,
                target_device_id=target_device_id,
                archive_id=archive_id,
            )
            request_data["archive_id"] = str(archive_id)

        preview_payload = {
            "action_type": action_type,
            "source_device_id": str(source_device_id) if source_device_id else None,
            "target_device_id": str(target_device_id) if target_device_id else None,
            "request_data": request_data,
            "preview": preview,
        }
        action = DeviceIdentityAction(
            organization_id=organization_id,
            action_type=action_type,
            status="preview",
            source_device_id=source_device_id,
            target_device_id=target_device_id,
            requested_by=requested_by,
            request_data=request_data,
            preview_data=preview,
            preview_hash=_canonical_hash(preview_payload),
        )
        self.session.add(action)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_user_id=requested_by,
                action=f"device.identity.{action_type}.preview",
                object_type="device_identity_action",
                object_id=str(action.id),
                after_data={
                    "action_type": action_type,
                    "source_device_id": (
                        str(source_device_id) if source_device_id else None
                    ),
                    "target_device_id": (
                        str(target_device_id) if target_device_id else None
                    ),
                    "row_count": len(preview.get("rows", [])),
                    "blocking_count": preview.get("blocking_count", 0),
                    "preview_hash": action.preview_hash,
                },
                context_data={"organization_id": str(organization_id)},
            )
        )
        return action

    def approve_action(
        self,
        *,
        organization_id: UUID,
        action_id: UUID,
        preview_hash: str,
        approved_by: UUID,
    ) -> DeviceIdentityAction:
        action = self.session.get(DeviceIdentityAction, action_id)
        if not action or action.organization_id != organization_id:
            raise LookupError("device identity action not found")
        if action.status != "preview":
            raise ValueError("only previewed device identity actions can be approved")
        if action.preview_hash != preview_hash.strip().lower():
            raise ValueError("preview hash does not match the reviewed action")
        if int(action.preview_data.get("blocking_count", 0)) > 0:
            raise ValueError("action preview contains blocking conflicts")
        action.status = "approved"
        action.approved_by = approved_by
        action.approved_at = utc_now()
        self.session.add(
            AuditEvent(
                actor_user_id=approved_by,
                action=f"device.identity.{action.action_type}.approve",
                object_type="device_identity_action",
                object_id=str(action.id),
                before_data={"status": "preview"},
                after_data={
                    "status": "approved",
                    "preview_hash": action.preview_hash,
                    "row_count": len(action.preview_data.get("rows", [])),
                },
                context_data={"organization_id": str(organization_id)},
            )
        )
        return action

    def cancel_action(
        self,
        *,
        organization_id: UUID,
        action_id: UUID,
        actor_user_id: UUID,
    ) -> DeviceIdentityAction:
        action = self.session.get(DeviceIdentityAction, action_id)
        if not action or action.organization_id != organization_id:
            raise LookupError("device identity action not found")
        if action.status not in {"preview", "approved"}:
            raise ValueError("only unstarted device identity actions can be cancelled")
        before = action.status
        action.status = "cancelled"
        action.ended_at = utc_now()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=f"device.identity.{action.action_type}.cancel",
                object_type="device_identity_action",
                object_id=str(action.id),
                before_data={"status": before},
                after_data={"status": "cancelled"},
                context_data={"organization_id": str(organization_id)},
            )
        )
        return action

    def pending_actions(self, *, limit: int = 20) -> tuple[DeviceIdentityAction, ...]:
        query = (
            select(DeviceIdentityAction)
            .where(DeviceIdentityAction.status == "approved")
            .order_by(DeviceIdentityAction.approved_at, DeviceIdentityAction.id)
            .limit(max(1, min(limit, 50)))
        )
        if self.session.get_bind().dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        return tuple(self.session.scalars(query).all())

    def _employee_bundle(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
    ) -> DeviceIdentityBundle:
        employee = self._employee(organization_id, employee_id)
        profile = self.session.get(EmployeeProfile, employee.id)
        if not profile or profile.attendance_id is None:
            raise ValueError("employee attendance ID is required for device enrollment")
        return DeviceIdentityBundle(
            external_user_id=str(profile.attendance_id),
            display_name=employee.display_name,
            active=employee.status == "active",
            metadata={"employee_code": employee.employee_code},
        )

    @staticmethod
    def _write_result(
        *,
        key: str,
        identifier: str,
        status_value: str,
        code: str,
    ) -> dict:
        return {
            key: identifier,
            "status": status_value,
            "code": code[:100],
        }

    def _target_has_conflict(
        self,
        *,
        target_device_id: UUID,
        external_user_id: str,
    ) -> bool:
        return self._target_user(target_device_id, external_user_id) is not None

    @staticmethod
    def _call_push(
        adapter: DeviceAdapter,
        bundle: DeviceIdentityBundle,
    ) -> DeviceWriteResult:
        push = getattr(adapter, "push_identity", None)
        if not adapter.capabilities().push_users or not callable(push):
            raise ValueError("target adapter does not support device identity writes")
        preview = push(bundle, dry_run=True)
        if not preview.accepted:
            return preview
        return push(bundle, dry_run=False)

    def _refresh_inventory(self, *, device: Device, adapter: DeviceAdapter) -> None:
        try:
            if adapter.capabilities().list_users:
                self.platform.sync_users(device=device, users=adapter.list_users())
        except Exception:
            return

    def _execute_push_users(
        self,
        action: DeviceIdentityAction,
        *,
        target: Device,
        target_adapter: DeviceAdapter,
    ) -> list[dict]:
        rows: list[dict] = []
        for employee_id_text in action.request_data.get("employee_ids", []):
            employee_id = UUID(str(employee_id_text))
            try:
                bundle = self._employee_bundle(
                    organization_id=action.organization_id,
                    employee_id=employee_id,
                )
                if self._target_has_conflict(
                    target_device_id=target.id,
                    external_user_id=bundle.external_user_id,
                ):
                    rows.append(
                        self._write_result(
                            key="employee_id",
                            identifier=str(employee_id),
                            status_value="failed",
                            code="target_external_id_conflict",
                        )
                    )
                    continue
                result = self._call_push(target_adapter, bundle)
                rows.append(
                    self._write_result(
                        key="employee_id",
                        identifier=str(employee_id),
                        status_value=("succeeded" if result.accepted else "failed"),
                        code=result.code,
                    )
                )
            except Exception as exc:
                rows.append(
                    self._write_result(
                        key="employee_id",
                        identifier=str(employee_id),
                        status_value="failed",
                        code=type(exc).__name__,
                    )
                )
        self._refresh_inventory(device=target, adapter=target_adapter)
        return rows

    def _execute_migration(
        self,
        action: DeviceIdentityAction,
        *,
        source: Device,
        target: Device,
        source_adapter: DeviceAdapter,
        target_adapter: DeviceAdapter,
    ) -> list[dict]:
        export = getattr(source_adapter, "export_identity", None)
        if not source_adapter.capabilities().archive_users or not callable(export):
            raise ValueError("source adapter does not support identity export")
        rows: list[dict] = []
        for device_user_id_text in action.request_data.get("device_user_ids", []):
            device_user_id = UUID(str(device_user_id_text))
            try:
                user = self._device_user(
                    action.organization_id,
                    source.id,
                    device_user_id,
                )
                allowed, _, consent_code = self._biometric_move_allowed(
                    organization_id=action.organization_id,
                    device_user=user,
                )
                if not allowed:
                    rows.append(
                        self._write_result(
                            key="device_user_id",
                            identifier=str(user.id),
                            status_value="failed",
                            code=consent_code or "biometric_move_blocked",
                        )
                    )
                    continue
                if self._target_has_conflict(
                    target_device_id=target.id,
                    external_user_id=user.external_user_id,
                ):
                    rows.append(
                        self._write_result(
                            key="device_user_id",
                            identifier=str(user.id),
                            status_value="failed",
                            code="target_external_id_conflict",
                        )
                    )
                    continue
                bundle = export(user.external_user_id)
                result = self._call_push(target_adapter, bundle)
                rows.append(
                    self._write_result(
                        key="device_user_id",
                        identifier=str(user.id),
                        status_value=("succeeded" if result.accepted else "failed"),
                        code=result.code,
                    )
                )
            except Exception as exc:
                rows.append(
                    self._write_result(
                        key="device_user_id",
                        identifier=str(device_user_id),
                        status_value="failed",
                        code=type(exc).__name__,
                    )
                )
        self._refresh_inventory(device=target, adapter=target_adapter)
        return rows

    def _execute_archive_export(
        self,
        action: DeviceIdentityAction,
        *,
        source: Device,
        source_adapter: DeviceAdapter,
        cipher: DeviceSecretCipher,
    ) -> tuple[list[dict], UUID | None]:
        export = getattr(source_adapter, "export_identity", None)
        if not source_adapter.capabilities().archive_users or not callable(export):
            raise ValueError("source adapter does not support encrypted identity archives")
        rows: list[dict] = []
        bundles: list[dict] = []
        manifest: list[dict] = []
        for device_user_id_text in action.request_data.get("device_user_ids", []):
            device_user_id = UUID(str(device_user_id_text))
            try:
                user = self._device_user(
                    action.organization_id,
                    source.id,
                    device_user_id,
                )
                allowed, employee_id, consent_code = self._biometric_move_allowed(
                    organization_id=action.organization_id,
                    device_user=user,
                )
                if not allowed:
                    rows.append(
                        self._write_result(
                            key="device_user_id",
                            identifier=str(user.id),
                            status_value="failed",
                            code=consent_code or "biometric_move_blocked",
                        )
                    )
                    continue
                bundle = export(user.external_user_id)
                bundles.append(_bundle_payload(bundle))
                manifest.append(
                    {
                        "external_user_id": bundle.external_user_id,
                        "employee_id": str(employee_id) if employee_id else None,
                        "template_count": bundle.template_count,
                    }
                )
                rows.append(
                    self._write_result(
                        key="device_user_id",
                        identifier=str(user.id),
                        status_value="succeeded",
                        code="archived",
                    )
                )
            except Exception as exc:
                rows.append(
                    self._write_result(
                        key="device_user_id",
                        identifier=str(device_user_id),
                        status_value="failed",
                        code=type(exc).__name__,
                    )
                )
        if not bundles:
            return rows, None
        encoded = json.dumps(
            {"version": 1, "bundles": bundles},
            sort_keys=True,
            separators=(",", ":"),
        )
        key_id, ciphertext = cipher.encrypt({"archive_json": encoded})
        archive = DeviceArchive(
            organization_id=action.organization_id,
            source_device_id=source.id,
            created_by=action.approved_by or action.requested_by,
            key_id=key_id,
            ciphertext=ciphertext,
            manifest_data={"version": 1, "rows": manifest},
            status="ready",
        )
        self.session.add(archive)
        self.session.flush()
        return rows, archive.id

    def _execute_archive_restore(
        self,
        action: DeviceIdentityAction,
        *,
        target: Device,
        target_adapter: DeviceAdapter,
        cipher: DeviceSecretCipher,
    ) -> list[dict]:
        archive_id = UUID(str(action.request_data.get("archive_id")))
        archive = self.session.get(DeviceArchive, archive_id)
        if not archive or archive.organization_id != action.organization_id:
            raise LookupError("device archive not found")
        if not target_adapter.capabilities().restore_users:
            raise ValueError("target adapter does not support archive restore")
        payload = cipher.decrypt(key_id=archive.key_id, ciphertext=archive.ciphertext)
        try:
            decoded = json.loads(payload["archive_json"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise ValueError("device archive could not be decoded") from exc
        raw_bundles = decoded.get("bundles") if isinstance(decoded, dict) else None
        if not isinstance(raw_bundles, list):
            raise ValueError("device archive payload is invalid")
        rows: list[dict] = []
        restored = 0
        for raw_bundle in raw_bundles:
            bundle = _bundle_from_payload(raw_bundle)
            try:
                if self._target_has_conflict(
                    target_device_id=target.id,
                    external_user_id=bundle.external_user_id,
                ):
                    rows.append(
                        self._write_result(
                            key="external_user_id",
                            identifier=bundle.external_user_id,
                            status_value="failed",
                            code="target_external_id_conflict",
                        )
                    )
                    continue
                result = self._call_push(target_adapter, bundle)
                succeeded = result.accepted
                restored += int(succeeded)
                rows.append(
                    self._write_result(
                        key="external_user_id",
                        identifier=bundle.external_user_id,
                        status_value=("succeeded" if succeeded else "failed"),
                        code=result.code,
                    )
                )
            except Exception as exc:
                rows.append(
                    self._write_result(
                        key="external_user_id",
                        identifier=bundle.external_user_id,
                        status_value="failed",
                        code=type(exc).__name__,
                    )
                )
        if restored:
            archive.last_restored_at = utc_now()
            if restored == len(raw_bundles):
                archive.status = "restored"
        self._refresh_inventory(device=target, adapter=target_adapter)
        return rows

    @staticmethod
    def _status_from_rows(rows: list[dict]) -> str:
        succeeded = sum(item.get("status") == "succeeded" for item in rows)
        failed = len(rows) - succeeded
        if succeeded and failed:
            return "partial"
        if succeeded:
            return "succeeded"
        return "failed"

    def execute_action(
        self,
        action: DeviceIdentityAction,
        *,
        adapter_resolver,
        cipher: DeviceSecretCipher,
    ) -> DeviceIdentityAction:
        if action.status != "approved":
            return action
        action.status = "running"
        action.started_at = utc_now()
        action.error_code = None
        action.error_detail = None
        self.session.flush()
        rows: list[dict] = []
        archive_id: UUID | None = None
        try:
            source = (
                self._device(action.organization_id, action.source_device_id)
                if action.source_device_id
                else None
            )
            target = (
                self._device(action.organization_id, action.target_device_id)
                if action.target_device_id
                else None
            )
            source_adapter = adapter_resolver(source) if source else None
            target_adapter = adapter_resolver(target) if target else None
            if action.action_type == "push_users":
                if target is None or target_adapter is None:
                    raise ValueError("target adapter is unavailable")
                rows = self._execute_push_users(
                    action,
                    target=target,
                    target_adapter=target_adapter,
                )
            elif action.action_type == "migrate_users":
                if (
                    source is None
                    or target is None
                    or source_adapter is None
                    or target_adapter is None
                ):
                    raise ValueError("source or target adapter is unavailable")
                rows = self._execute_migration(
                    action,
                    source=source,
                    target=target,
                    source_adapter=source_adapter,
                    target_adapter=target_adapter,
                )
            elif action.action_type == "archive_export":
                if source is None or source_adapter is None:
                    raise ValueError("source adapter is unavailable")
                rows, archive_id = self._execute_archive_export(
                    action,
                    source=source,
                    source_adapter=source_adapter,
                    cipher=cipher,
                )
            else:
                if target is None or target_adapter is None:
                    raise ValueError("target adapter is unavailable")
                rows = self._execute_archive_restore(
                    action,
                    target=target,
                    target_adapter=target_adapter,
                    cipher=cipher,
                )
            action.status = self._status_from_rows(rows)
            action.result_data = {
                "rows": rows,
                "counts": {
                    "total": len(rows),
                    "succeeded": sum(
                        item.get("status") == "succeeded" for item in rows
                    ),
                    "failed": sum(item.get("status") != "succeeded" for item in rows),
                },
                "archive_id": str(archive_id) if archive_id else None,
            }
        except Exception as exc:
            action.status = "failed"
            action.error_code = type(exc).__name__[:100]
            action.error_detail = "Device identity action failed; inspect sanitized worker diagnostics."
            action.result_data = {"rows": rows, "archive_id": None}
        finally:
            action.ended_at = utc_now()
            self.session.add(
                AuditEvent(
                    actor_user_id=action.approved_by or action.requested_by,
                    action=f"device.identity.{action.action_type}.execute",
                    object_type="device_identity_action",
                    object_id=str(action.id),
                    after_data={
                        "status": action.status,
                        "source_device_id": (
                            str(action.source_device_id) if action.source_device_id else None
                        ),
                        "target_device_id": (
                            str(action.target_device_id) if action.target_device_id else None
                        ),
                        "counts": action.result_data.get("counts", {}),
                        "archive_id": action.result_data.get("archive_id"),
                        "error_code": action.error_code,
                    },
                    context_data={"organization_id": str(action.organization_id)},
                )
            )
            self.session.flush()
        return action

    def process_approved(
        self,
        *,
        adapter_resolver,
        cipher: DeviceSecretCipher,
        limit: int = 20,
    ) -> tuple[DeviceIdentityAction, ...]:
        return tuple(
            self.execute_action(
                item,
                adapter_resolver=adapter_resolver,
                cipher=cipher,
            )
            for item in self.pending_actions(limit=limit)
        )
