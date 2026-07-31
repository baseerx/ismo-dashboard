from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import F
from django.utils import timezone
from .models import EmployeeActivity
import json
import datetime


# ─────────────────────────────────────────────────────────────
# HELPER: grade-9 head detection
# Returns list of SubSection objects if employee is a head, else []
#
# NOTE: head_employee_id column stores erp_id directly (that's how
# create_sub_section / update_sub_section write it, and how the
# frontend compares it), even though the Django FK is technically
# declared against Employees.id. So a plain column match is correct
# here — do NOT traverse the relation with head_employee__erp_id,
# since that would join against Employees.id instead.
# ─────────────────────────────────────────────────────────────
def _get_head_subsections(erp_id, section_id=None):
    """Return list of SubSections where erp_id is head. Empty list if not a head."""
    from subsections.models import SubSection
    return list(SubSection.objects.filter(head_employee_id=erp_id))


# ─────────────────────────────────────────────────────────────
# HELPER: keep BusinessPlan.completion_pct in sync with activities
#
# Root cause of the bug: submit_activity / update_activity were
# saving overall_pct on EmployeeActivity only — they never wrote
# back to BusinessPlan.completion_pct. So BusinessPlan.tsx,
# EmpDailyActivities.tsx and ActivitiesReport.tsx all kept showing
# a stale/zero completion_pct because the BP row itself never changed.
#
# This recomputes completion_pct from the most recent activity
# logged against that bp_task, and is called after every
# create / update / delete of an activity.
# ─────────────────────────────────────────────────────────────
def _sync_bp_completion(bp_task_id):
    if not bp_task_id:
        return
    from businessplan.models import BusinessPlan, sync_parent_completion

    latest = (
        EmployeeActivity.objects
        .filter(bp_task_id=bp_task_id)
        .order_by('-activity_date', '-created_at')
        .first()
    )
    new_pct = max(0, min(100, latest.overall_pct)) if latest else 0
    BusinessPlan.objects.filter(pk=bp_task_id).update(completion_pct=new_pct)

    # 🔧 FIX: if this task is a sub-task of some parent task, also
    # recompute the parent's (and the chain above it) completion_pct —
    # parent = average of its direct children
    bp_task = BusinessPlan.objects.filter(pk=bp_task_id).first()
    if bp_task:
        sync_parent_completion(bp_task)


# ─────────────────────────────────────────────────────────────
# GET /activities/my/
# ─────────────────────────────────────────────────────────────
@csrf_exempt
def get_my_activities(request):
    erpid = request.GET.get('erp_id') or request.GET.get('erpid')
    if not erpid:
        return JsonResponse({'error': 'erp_id required'}, status=400)

    activities = EmployeeActivity.objects.filter(erp_id=int(erpid)).annotate(
        bp_task_sr=F('bp_task__sr_number'),
        bp_task_name=F('bp_task__task'),
        bp_task_start_date=F('bp_task__start_date'),
        bp_task_end_date=F('bp_task__end_date'),
    ).values(
        'id', 'erp_id', 'bp_task_id', 'bp_task_sr', 'bp_task_name',
        'bp_task_start_date', 'bp_task_end_date',
        'task_description', 'risk_comment', 'activity_date',
        'today_progress', 'overall_pct', 'status', 'created_at',
    )
    return JsonResponse(list(activities), safe=False)


# ─────────────────────────────────────────────────────────────
# POST /activities/submit/
# ─────────────────────────────────────────────────────────────
@csrf_exempt
def submit_activity(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body)
        bp_task_id = data.get('bp_task_id') or None
        EmployeeActivity.objects.create(
            erp_id           = data.get('erp_id') or data.get('erpid'),
            bp_task_id       = bp_task_id,
            task_description = data.get('task_description', ''),
            risk_comment     = data.get('risk_comment', ''),
            activity_date    = data['activity_date'],
            today_progress   = data.get('today_progress', 0),
            overall_pct      = data.get('overall_pct', 0),
            status           = data.get('status', 'In Progress'),
        )
        # 🔧 FIX: sync the BP task's completion_pct with the activity's overall_pct
        _sync_bp_completion(bp_task_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────
# PUT /activities/update/<pk>/
# ─────────────────────────────────────────────────────────────
@csrf_exempt
def update_activity(request, pk):
    if request.method != 'PUT':
        return JsonResponse({'error': 'PUT only'}, status=405)
    try:
        data = json.loads(request.body)
        act = EmployeeActivity.objects.get(pk=pk)
        old_bp_task_id       = act.bp_task_id
        act.bp_task_id       = data.get('bp_task_id', act.bp_task_id)
        act.task_description = data.get('task_description', act.task_description)
        act.risk_comment     = data.get('risk_comment', act.risk_comment)
        act.activity_date    = data.get('activity_date', act.activity_date)
        act.today_progress   = data.get('today_progress', act.today_progress)
        act.overall_pct      = data.get('overall_pct', act.overall_pct)
        act.status           = data.get('status', act.status)
        act.save()
        # 🔧 FIX: refresh the BP completion_pct — if bp_task changed,
        # also resync the old task, so it doesn't stay stale
        if old_bp_task_id and old_bp_task_id != act.bp_task_id:
            _sync_bp_completion(old_bp_task_id)
        _sync_bp_completion(act.bp_task_id)
        return JsonResponse({'success': True})
    except EmployeeActivity.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────
# DELETE /activities/delete/<pk>/
# ─────────────────────────────────────────────────────────────
@csrf_exempt
def delete_activity(request, pk):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE only'}, status=405)
    try:
        act = EmployeeActivity.objects.get(pk=pk)
        bp_task_id = act.bp_task_id
        act.delete()
        # 🔧 FIX: after an activity is deleted, resync the BP task's
        # completion_pct from the remaining activities (otherwise the
        # deleted activity's value used to stay stuck in BusinessPlan)
        _sync_bp_completion(bp_task_id)
        return JsonResponse({'success': True})
    except EmployeeActivity.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


# ─────────────────────────────────────────────────────────────
# GET /activities/bp-tasks/
#
# Access rules (same spirit as get_activities_report):
#   superuser             → all BP tasks
#   grade 10/11           → tasks of ALL sub-sections in their section
#   grade 9, IS head      → only tasks of the sub-section(s) they head
#   grade 9, NOT head     → only tasks of their own (from the employee table) sub_section
#   grade < 9             → only tasks of their own (from the employee table) sub_section
#
# "Tasks of their own sub-section" means: that sub-section's L1 (level=0)
# BusinessPlan row (lead_team = sub-section) + all its L2/L3 descendants —
# so that EmpDailyActivities.tsx's cascading L1→L2→L3 dropdown chain doesn't break.
# ─────────────────────────────────────────────────────────────
@csrf_exempt
def get_bp_tasks(request):
    from businessplan.models import BusinessPlan
    from users.models import Employees

    section_id   = request.GET.get('section_id')
    grade_id     = int(request.GET.get('grade_id') or 0)
    is_superuser = request.GET.get('is_superuser', 'false').lower() == 'true'
    erp_id       = int(request.GET.get('erpid') or request.GET.get('erp_id') or 0)

    qs = BusinessPlan.objects.all()
    if not is_superuser and section_id and section_id != '0':
        qs = qs.filter(section_id=int(section_id))

    # ── Sub-section level restriction (superuser and grade 10/11 exempt) ──
    if not is_superuser and grade_id not in (10, 11):
        allowed_ss_ids = []

        if grade_id == 9:
            head_sss = _get_head_subsections(erp_id, section_id)
            if head_sss:
                allowed_ss_ids = [ss.id for ss in head_sss]

        if not allowed_ss_ids:
            # grade 9 (not head) or grade < 9 → own sub_section from the employee table
            emp = Employees.objects.filter(erp_id=erp_id).first()
            if emp and emp.sub_section_id:
                allowed_ss_ids = [emp.sub_section_id]

        if allowed_ss_ids:
            # Qualifying L1 (main) tasks whose lead_team is in the allowed sub-sections
            qualifying_srs = set(
                qs.filter(level=0, lead_team_id__in=allowed_ss_ids)
                  .values_list('sr_number', flat=True)
            )

            def root_sr(sr):
                parts = sr.split('-')
                return '-'.join(parts[:3]) if len(parts) >= 3 else sr

            allowed_ids = [
                t['id'] for t in qs.values('id', 'sr_number')
                if root_sr(t['sr_number']) in qualifying_srs
            ]
            qs = qs.filter(id__in=allowed_ids)
        else:
            # Neither a head nor any sub_section assigned — security: return nothing
            qs = qs.none()

    tasks = qs.values('id', 'sr_number', 'task', 'start_date', 'end_date', 'completion_pct')
    return JsonResponse(list(tasks), safe=False)


# ─────────────────────────────────────────────────────────────
# GET /activities/report/
#
# Access rules:
#   grade < 9            → only own activities
#   grade 9, NOT head    → only own activities
#   grade 9, IS head     → all employees of their sub_section(s)
#   grade 10/11          → all employees of their section
#   superuser            → everyone
# ─────────────────────────────────────────────────────────────
@csrf_exempt
def get_activities_report(request):
    section_id   = request.GET.get('section_id')
    grade_id     = int(request.GET.get('grade_id', 0))
    is_superuser = request.GET.get('is_superuser', 'false').lower() == 'true'
    erp_id       = int(request.GET.get('erp_id', 0))

    # Optional filters from frontend
    filter_erpid   = request.GET.get('filter_erp_id') or request.GET.get('erpid')
    # Multi-select: getlist returns all values sent as sub_section_id
    filter_sub_secs = [x for x in request.GET.getlist('sub_section_id') if x]
    date_from      = request.GET.get('date_from')
    date_to        = request.GET.get('date_to')

    qs = EmployeeActivity.objects.annotate(
        bp_task__sr_number     = F('bp_task__sr_number'),
        bp_task__task          = F('bp_task__task'),
        bp_task__section__name = F('bp_task__section__name'),
        bp_task__start_date    = F('bp_task__start_date'),
        bp_task__end_date      = F('bp_task__end_date'),
    )

    # ── Determine scope ──────────────────────────────────────
    if is_superuser:
        pass  # no restriction

    elif grade_id in [10, 11]:
        if section_id and section_id != '0':
            qs = qs.filter(bp_task__section_id=int(section_id))
        else:
            # No valid section_id — return nothing (security: don't leak all data)
            return JsonResponse([], safe=False)

    elif grade_id == 9:
        head_sss = _get_head_subsections(erp_id, section_id)
        if head_sss:
            from users.models import Employees
            head_ss_ids = [ss.id for ss in head_sss]
            sub_emp_ids = list(
                Employees.objects.filter(sub_section_id__in=head_ss_ids).values_list('erp_id', flat=True)
            )
            qs = qs.filter(erp_id__in=sub_emp_ids)
            # Sub-section filter still applies if frontend sends specific sub_section(s)
            # but only within the head's allowed sub_sections
            if filter_sub_secs:
                allowed = [str(sid) for sid in head_ss_ids]
                filter_sub_secs = [s for s in filter_sub_secs if s in allowed]
        else:
            # Not a head → own activities only
            qs = qs.filter(erp_id=erp_id)
            filter_erpid    = None
            filter_sub_secs = []

    else:
        # Grade < 9 → own activities only
        qs = qs.filter(erp_id=erp_id)
        filter_erpid    = None
        filter_sub_secs = []

    # ── Optional frontend filters ─────────────────────────────
    if filter_sub_secs:
        from users.models import Employees
        sub_emp_ids = list(
            Employees.objects.filter(
                sub_section_id__in=[int(s) for s in filter_sub_secs]
            ).values_list('erp_id', flat=True)
        )
        qs = qs.filter(erp_id__in=sub_emp_ids)

    if filter_erpid:
        qs = qs.filter(erp_id=int(filter_erpid))

    if date_from:
        qs = qs.filter(activity_date__gte=date_from)
    if date_to:
        qs = qs.filter(activity_date__lte=date_to)

    # ── Fetch rows ───────────────────────────────────────────
    rows = list(qs.values(
        'id', 'erp_id',
        'bp_task__sr_number',
        'bp_task__task',
        'bp_task__section__name',
        'bp_task__start_date',
        'bp_task__end_date',
        'task_description', 'risk_comment', 'activity_date',
        'today_progress', 'overall_pct', 'status',
    ))

    # Build erp_id → name map
    erp_ids = list({r['erp_id'] for r in rows})
    try:
        from users.models import Employees
        emp_map = {
            e['erp_id']: e['name']
            for e in Employees.objects.filter(erp_id__in=erp_ids).values('erp_id', 'name')
        }
    except Exception:
        emp_map = {}

    for r in rows:
        r['employee_name'] = emp_map.get(r['erp_id'], str(r['erp_id']))

    return JsonResponse(rows, safe=False)


# ─────────────────────────────────────────────────────────────
# GET /activities/section-employees/
# ─────────────────────────────────────────────────────────────
@csrf_exempt
def get_section_employees(request):
    section_id   = request.GET.get('section_id')
    grade_id     = int(request.GET.get('grade_id', 0))
    is_superuser = request.GET.get('is_superuser', 'false').lower() == 'true'
    erp_id       = int(request.GET.get('erp_id', 0))

    try:
        from users.models import Employees

        if is_superuser:
            emps = Employees.objects.all()

        elif grade_id in [10, 11]:
            if section_id and section_id != '0':
                emps = Employees.objects.filter(section_id=int(section_id))
            else:
                emps = Employees.objects.none()

        elif grade_id == 9:
            head_sss = _get_head_subsections(erp_id, section_id)
            if head_sss:
                head_ss_ids = [ss.id for ss in head_sss]
                emps = Employees.objects.filter(sub_section_id__in=head_ss_ids)
            else:
                emps = Employees.objects.filter(erp_id=erp_id)

        else:
            emps = Employees.objects.filter(erp_id=erp_id)

        data = list(emps.values('erp_id', 'name', 'grade_id', 'sub_section_id'))
        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────
# GET /activities/sub-sections/
# ─────────────────────────────────────────────────────────────
@csrf_exempt
def get_sub_sections(request):
    section_id   = request.GET.get('section_id')
    grade_id     = int(request.GET.get('grade_id', 0))
    is_superuser = request.GET.get('is_superuser', 'false').lower() == 'true'
    erp_id       = int(request.GET.get('erp_id', 0))

    try:
        from subsections.models import SubSection

        if is_superuser:
            ss_qs = SubSection.objects.all()

        elif grade_id in [10, 11]:
            if section_id and section_id != '0':
                ss_qs = SubSection.objects.filter(section_id=int(section_id))
            else:
                ss_qs = SubSection.objects.none()

        elif grade_id == 9:
            # Return ALL sub_sections where this employee is head (may be multiple)
            head_sss = _get_head_subsections(erp_id, section_id)
            if head_sss:
                head_ids = [ss.id for ss in head_sss]
                ss_qs = SubSection.objects.filter(pk__in=head_ids)
            else:
                ss_qs = SubSection.objects.none()

        else:
            ss_qs = SubSection.objects.none()

        data = list(ss_qs.values('id', 'sub_section_name', 'head_employee_id', 'section_id'))
        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────
# GET /activities/attendance-report/
#
# "How many and which employees of a section entered an activity
# today, and who didn't" — only for section-head (grade-9 head),
# grade-10/11, and superuser. An individual employee (who is not a
# head of any sub_section) can only see their own data through this
# endpoint — the frontend doesn't even show them the button, but
# the same access-scope used in get_sub_sections / get_section_employees
# is reused here too, so that no one can pull another section's data
# by hitting the endpoint URL directly.
#
# Query params:
#   section_id, grade_id, is_superuser, erp_id   (same as the other endpoints)
#   date   (YYYY-MM-DD, optional — defaults to today's date)
#
# Response: list of sub_sections, each containing a list of employees
# with an 'active' flag (whether they submitted an activity for
# today/selected date or not) + active/inactive counts.
# ─────────────────────────────────────────────────────────────
@csrf_exempt
def get_attendance_report(request):
    section_id   = request.GET.get('section_id')
    grade_id     = int(request.GET.get('grade_id', 0))
    is_superuser = request.GET.get('is_superuser', 'false').lower() == 'true'
    erp_id       = int(request.GET.get('erp_id', 0))
    date_str     = request.GET.get('date')

    # Resolve target date (default: today)
    if date_str:
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date format, expected YYYY-MM-DD'}, status=400)
    else:
        target_date = timezone.localdate()

    try:
        from subsections.models import SubSection
        from users.models import Employees

        # ── Determine which sub_sections this user is allowed to see ──
        if is_superuser:
            ss_qs = SubSection.objects.all()

        elif grade_id in [10, 11]:
            if section_id and section_id != '0':
                ss_qs = SubSection.objects.filter(section_id=int(section_id))
            else:
                ss_qs = SubSection.objects.none()

        elif grade_id == 9:
            head_sss = _get_head_subsections(erp_id, section_id)
            ss_qs = SubSection.objects.filter(pk__in=[ss.id for ss in head_sss]) if head_sss else SubSection.objects.none()

        else:
            # Individual employee (not a head) — no team to report on
            ss_qs = SubSection.objects.none()

        sub_sections = list(ss_qs.values('id', 'sub_section_name'))

        if not sub_sections:
            return JsonResponse({'date': str(target_date), 'sections': []}, safe=False)

        ss_ids = [ss['id'] for ss in sub_sections]

        # ── All employees belonging to these sub_sections ──
        employees = list(
            Employees.objects.filter(sub_section_id__in=ss_ids)
            .values('erp_id', 'name', 'sub_section_id')
        )
        all_erp_ids = [e['erp_id'] for e in employees]

        # ── Who submitted an activity on target_date ──
        active_erp_ids = set(
            EmployeeActivity.objects
            .filter(erp_id__in=all_erp_ids, activity_date=target_date)
            .values_list('erp_id', flat=True)
            .distinct()
        )

        # ── Group employees by sub_section ──
        emp_by_ss = {}
        for e in employees:
            emp_by_ss.setdefault(e['sub_section_id'], []).append(e)

        sections_out = []
        for ss in sub_sections:
            ss_employees = emp_by_ss.get(ss['id'], [])
            emp_list = []
            active_count = 0
            for e in ss_employees:
                is_active = e['erp_id'] in active_erp_ids
                if is_active:
                    active_count += 1
                emp_list.append({
                    'erp_id': e['erp_id'],
                    'name':   e['name'],
                    'active': is_active,
                })
            # Sort: inactive first (need attention), then active
            emp_list.sort(key=lambda x: (x['active'], x['name'] or ''))

            sections_out.append({
                'sub_section_id':   ss['id'],
                'sub_section_name': ss['sub_section_name'],
                'total_count':      len(ss_employees),
                'active_count':     active_count,
                'inactive_count':   len(ss_employees) - active_count,
                'employees':        emp_list,
            })

        return JsonResponse({'date': str(target_date), 'sections': sections_out}, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)