from pathlib import Path

path = Path("app/src/hajiriflow/device_platform/jobs.py")
text = path.read_text()

text = text.replace(
    "from datetime import UTC, datetime\n",
    "from datetime import UTC, datetime, timedelta\n",
    1,
)
text = text.replace(
    "from hajiriflow.device_platform.pull import DevicePullCoordinator\n",
    "from hajiriflow.device_platform.pull import DevicePullCoordinator, device_pull_lock\n",
    1,
)
text = text.replace(
    'if end_at - start_at > __import__("datetime").timedelta(days=366):',
    "if end_at - start_at > timedelta(days=366):",
    1,
)
old = """        try:
            adapter = self.adapter_resolver(device)
            result = self._execute(job, device, adapter)
            job.result = result
"""
new = """        try:
            adapter = self.adapter_resolver(device)
            with device_pull_lock(self.session, device.id) as locked:
                if not locked:
                    return self._fail(
                        job,
                        "device_locked",
                        "Another worker is already operating on this device.",
                    )
                result = self._execute(job, device, adapter)
            job.result = result
"""
if old not in text:
    raise SystemExit("processor lock anchor not found")
text = text.replace(old, new, 1)
old_target = """            target_adapter = self.adapter_resolver(target)
            target_users = {
                item.external_user_id: item for item in target_adapter.list_users()
            }
            if external_user_id in target_users:
                raise ValueError("target device already contains this user; migration will not overwrite")
            push_user = getattr(target_adapter, "push_user", None)
            if push_user is None or not target_adapter.capabilities().push_users:
                raise ValueError("target device does not support user enrollment")
            migrated = push_user(
                DeviceUserRecord(
                    external_user_id=source_user.external_user_id,
                    display_name=source_user.display_name,
                    privilege=source_user.privilege,
                    active=source_user.active,
                ),
                overwrite=False,
            )
            self.platform.sync_device_users(device=target, users=(migrated,))
"""
new_target = """            with device_pull_lock(self.session, target.id) as target_locked:
                if not target_locked:
                    raise RuntimeError("target device is busy")
                target_adapter = self.adapter_resolver(target)
                target_users = {
                    item.external_user_id: item for item in target_adapter.list_users()
                }
                if external_user_id in target_users:
                    raise ValueError(
                        "target device already contains this user; migration will not overwrite"
                    )
                push_user = getattr(target_adapter, "push_user", None)
                if push_user is None or not target_adapter.capabilities().push_users:
                    raise ValueError("target device does not support user enrollment")
                migrated = push_user(
                    DeviceUserRecord(
                        external_user_id=source_user.external_user_id,
                        display_name=source_user.display_name,
                        privilege=source_user.privilege,
                        active=source_user.active,
                    ),
                    overwrite=False,
                )
                self.platform.sync_device_users(device=target, users=(migrated,))
"""
if old_target not in text:
    raise SystemExit("target lock anchor not found")
text = text.replace(old_target, new_target, 1)
path.write_text(text)
