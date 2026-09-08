from pathlib import Path

jobs_path = Path("app/src/hajiriflow/device_platform/jobs.py")
jobs = jobs_path.read_text()
old_jobs = "                metadata=dict(diagnostics.metadata),\n"
new_jobs = "                diagnostic_data=dict(diagnostics.metadata),\n"
if old_jobs not in jobs:
    raise SystemExit("diagnostic snapshot call-site anchor not found")
jobs_path.write_text(jobs.replace(old_jobs, new_jobs, 1))

api_path = Path("app/src/hajiriflow/api/device_baseline.py")
api = api_path.read_text()
old_api = "            metadata=item.metadata,\n"
new_api = "            metadata=item.diagnostic_data,\n"
if old_api not in api:
    raise SystemExit("diagnostic API call-site anchor not found")
api_path.write_text(api.replace(old_api, new_api, 1))
