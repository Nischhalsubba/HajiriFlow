from pathlib import Path

service_path = Path("app/src/hajiriflow/calendar_leave/service.py")
text = service_path.read_text()

old_import = "from sqlalchemy.orm import Session\n\nfrom hajiriflow.db.models.calendar_leave import ("
new_import = (
    "from sqlalchemy.orm import Session\n\n"
    "from hajiriflow.calendar_leave.bs_dates import BsDateService\n"
    "from hajiriflow.db.models.calendar_leave import ("
)
if old_import not in text:
    raise SystemExit("service import anchor not found")
text = text.replace(old_import, new_import, 1)

old_bounds = """        base_filters = [
            LeaveRequest.organization_id == organization_id,
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.leave_policy_id == leave_policy_id,
            LeaveRequest.start_date >= date(period_year, 1, 1),
            LeaveRequest.start_date <= date(period_year, 12, 31),
        ]"""
new_bounds = """        period_start = BsDateService.bs_to_ad(f"{period_year:04d}-01-01")
        next_period_start = BsDateService.bs_to_ad(f"{period_year + 1:04d}-01-01")
        period_end = next_period_start - timedelta(days=1)
        base_filters = [
            LeaveRequest.organization_id == organization_id,
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.leave_policy_id == leave_policy_id,
            LeaveRequest.start_date >= period_start,
            LeaveRequest.start_date <= period_end,
        ]"""
if old_bounds not in text:
    raise SystemExit("leave balance period anchor not found")
text = text.replace(old_bounds, new_bounds, 1)

old_cross = """        if start_date.year != end_date.year:
            raise ValueError("leave requests cannot cross allocation years")"""
new_cross = """        start_bs_year = int(BsDateService.ad_to_bs(start_date).split("-", 1)[0])
        end_bs_year = int(BsDateService.ad_to_bs(end_date).split("-", 1)[0])
        if start_bs_year != end_bs_year:
            raise ValueError("leave requests cannot cross BS allocation years")"""
if old_cross not in text:
    raise SystemExit("leave request year anchor not found")
text = text.replace(old_cross, new_cross, 1)

old_balance_year = """            period_year=start_date.year,
        )"""
new_balance_year = """            period_year=start_bs_year,
        )"""
if old_balance_year not in text:
    raise SystemExit("leave request balance year anchor not found")
text = text.replace(old_balance_year, new_balance_year, 1)
service_path.write_text(text)

test_path = Path("app/tests/test_calendar_leave_api.py")
tests = test_path.read_text()
if '"period_year": 2026' not in tests:
    raise SystemExit("legacy allocation year test anchor not found")
tests = tests.replace('"period_year": 2026', '"period_year": 2083', 1)
if 'f"{policy_id}/2026"' not in tests:
    raise SystemExit("legacy balance URL year test anchor not found")
tests = tests.replace('f"{policy_id}/2026"', 'f"{policy_id}/2083"', 1)
test_path.write_text(tests)
