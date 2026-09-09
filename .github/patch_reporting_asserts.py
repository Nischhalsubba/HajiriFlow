from pathlib import Path

path = Path("app/src/hajiriflow/reporting/service.py")
text = path.read_text()

old_import = "from datetime import UTC, date, datetime, time, timedelta\nfrom uuid import UUID\n"
new_import = (
    "from datetime import UTC, date, datetime, time, timedelta\n"
    "from typing import cast\n"
    "from uuid import UUID\n"
)
if text.count(old_import) != 1:
    raise SystemExit("unexpected reporting service import block")
text = text.replace(old_import, new_import)

old_context = '''        duties = context["duties"]
        leaves = context["leaves"]
        holidays = context["holidays"]
        weekends = context["weekends"]
        assert isinstance(duties, dict)
        assert isinstance(leaves, dict)
        assert isinstance(holidays, dict)
        assert isinstance(weekends, set)
'''
new_context = '''        duties = cast(dict[UUID, list[FieldDutyRequest]], context["duties"])
        leaves = cast(dict[UUID, list[LeaveRequest]], context["leaves"])
        holidays = cast(dict[date, Holiday], context["holidays"])
        weekends = cast(set[int], context["weekends"])
'''
if text.count(old_context) != 1:
    raise SystemExit("unexpected fallback context block")
text = text.replace(old_context, new_context)

old_employee_list = '''            employee_list = bucket["employee_ids"]
            assert isinstance(employee_list, list)
'''
new_employee_list = '''            employee_list = cast(list[UUID], bucket["employee_ids"])
'''
if text.count(old_employee_list) != 1:
    raise SystemExit("unexpected employee list narrowing block")
text = text.replace(old_employee_list, new_employee_list)

old_statuses = '''            statuses = bucket["statuses"]
            assert isinstance(statuses, defaultdict)
'''
new_statuses = '''            statuses = cast(defaultdict[str, int], bucket["statuses"])
'''
if text.count(old_statuses) != 2:
    raise SystemExit("unexpected status narrowing count")
text = text.replace(old_statuses, new_statuses)

path.write_text(text)
