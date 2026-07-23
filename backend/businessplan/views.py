from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import F
from .models import BusinessPlan
import json
import openpyxl


def get_user_grade(request):
    grade = request.headers.get('X-Grade-Id')
    if grade:
        return int(grade)
    return 0


def get_user_erpid(request):
    """Current user's ERP ID — from header (GET/DELETE) or POST/PUT body/query."""
    erpid = request.headers.get('X-Erp-Id')
    if erpid:
        try:
            return int(erpid)
        except (TypeError, ValueError):
            return 0
    return 0


def get_head_sub_section_ids(erp_id):
    """List of sub-section IDs that this grade-9 employee heads (DB-verified)."""
    if not erp_id:
        return []
    from subsections.models import SubSection
    return list(SubSection.objects.filter(head_employee_id=erp_id).values_list('id', flat=True))


def get_own_sub_section_id(erp_id):
    """Which sub-section the employee is themselves a member of (from employees.sub_section_id)."""
    if not erp_id:
        return None
    from users.models import Employees
    return Employees.objects.filter(erp_id=erp_id).values_list('sub_section_id', flat=True).first()


def get_bp_scope(grade, erp_id, is_superuser, section_id=None):
    """
    Business Plan module's access scope — DB-verified, server-side (we don't
    trust any flag/role coming from the frontend):

      {'type': 'all'}                       -> superuser: all sections, all sub-sections
      {'type': 'section', 'section_id': X}  -> grade 10/11: their entire section
      {'type': 'subsections', 'ids': [..]}  -> grade-9 sub-section-head: only their headed sub-section(s)
      {'type': 'own', 'sub_section_id': X}  -> grade 1-9 (non-head): only their own sub-section
      {'type': 'none'}                      -> section/sub-section unknown, nothing will show
    """
    if is_superuser:
        return {'type': 'all'}
    if grade in [10, 11]:
        if not section_id or str(section_id) == '0':
            return {'type': 'none'}
        return {'type': 'section', 'section_id': int(section_id)}
    if grade == 9:
        head_ids = get_head_sub_section_ids(erp_id)
        if head_ids:
            return {'type': 'subsections', 'ids': head_ids}
        # grade 9 but not a head of any sub-section — treat like a normal employee
    own_ss = get_own_sub_section_id(erp_id)
    if own_ss:
        return {'type': 'own', 'sub_section_id': own_ss}
    return {'type': 'none'}


def apply_bp_scope(qs, scope, extra_sub_section_id=None):
    """Applies the scope dict to the queryset. extra_sub_section_id
    is an optional narrowing filter coming from a dropdown (only works within the allowed scope)."""
    if scope['type'] == 'all':
        if extra_sub_section_id and str(extra_sub_section_id) != '0':
            qs = qs.filter(lead_team_id=int(extra_sub_section_id))
        return qs
    if scope['type'] == 'section':
        qs = qs.filter(section_id=scope['section_id'])
        if extra_sub_section_id and str(extra_sub_section_id) != '0':
            qs = qs.filter(lead_team_id=int(extra_sub_section_id))
        return qs
    if scope['type'] == 'subsections':
        ids = scope['ids']
        if extra_sub_section_id and int(extra_sub_section_id) in ids:
            ids = [int(extra_sub_section_id)]
        return qs.filter(lead_team_id__in=ids)
    if scope['type'] == 'own':
        return qs.filter(lead_team_id=scope['sub_section_id'])
    return qs.none()


def can_modify_row(bp, scope, erp_id):
    """Whether editing/deleting a specific BusinessPlan row is allowed or not."""
    if scope['type'] == 'all':
        return True
    if scope['type'] == 'section':
        return bp.section_id == scope['section_id']
    if scope['type'] == 'subsections':
        return bp.lead_team_id in scope['ids']
    if scope['type'] == 'own':
        return bp.lead_team_id == scope['sub_section_id'] and bp.created_by == erp_id
    return False


def resolve_lead_team(value):
    """
    lead_team can come from the frontend as either a name (e.g. 'DPC') or an id —
    dropdown options are always built from sub_section_name, so the name
    is more common. Try by name first, then by id (same logic as
    upload_excel, so add/update/upload all stay consistent).
    Returns (obj_or_None, found_bool).
    """
    from subsections.models import SubSection
    if not value:
        return None, True  # empty = clearing it, valid
    value = str(value).strip()
    try:
        return SubSection.objects.get(sub_section_name__iexact=value), True
    except SubSection.DoesNotExist:
        try:
            return SubSection.objects.get(pk=int(value)), True
        except (SubSection.DoesNotExist, ValueError):
            return None, False


def validate_date_range(start_date, end_date, parent_sr):
    """
    A sub-task's start/end date must fall within its parent task's date
    range — it shouldn't start before the parent or end after the parent.
    start_date/end_date can be a string (YYYY-MM-DD) or a date object.
    Returns an error message (string) or None (valid).
    """
    from django.utils.dateparse import parse_date

    def _to_date(val):
        if not val:
            return None
        if isinstance(val, str):
            return parse_date(val)
        return val  # already a date object

    start = _to_date(start_date)
    end = _to_date(end_date)

    if start and end and start > end:
        return "Start date must be earlier than the end date"

    if parent_sr:
        parent = BusinessPlan.objects.filter(sr_number=parent_sr).values('start_date', 'end_date').first()
        if parent:
            p_start, p_end = parent['start_date'], parent['end_date']
            if start and p_start and start < p_start:
                return f"Start date cannot be earlier than the parent task's start date ({p_start})"
            if end and p_end and end > p_end:
                return f"End date cannot be later than the parent task's end date ({p_end})"

    return None


@csrf_exempt
def get_my_scope(request):
    """
    Current user's access-scope + display info for the Business Plan page,
    in a single call — section name, sub-section dropdown options (admin-tier)
    or own sub-section (regular employee), so the frontend doesn't have to
    hit separate endpoints.
    """
    from sections.models import Sections
    from subsections.models import SubSection

    section_id   = request.GET.get('section_id')
    is_superuser = request.GET.get('is_superuser', 'false').lower() == 'true'
    grade        = get_user_grade(request)
    erpid        = get_user_erpid(request)

    scope = get_bp_scope(grade, erpid, is_superuser, section_id)

    section_name = None
    if section_id and str(section_id) != '0':
        section_name = Sections.objects.filter(pk=int(section_id)).values_list('name', flat=True).first()

    result = {'scope_type': scope['type'], 'section_name': section_name}

    if scope['type'] == 'all':
        ss_qs = SubSection.objects.all()
        if section_id and str(section_id) != '0':
            ss_qs = ss_qs.filter(section_id=int(section_id))
        result['sub_sections'] = list(ss_qs.values('id', 'sub_section_name'))
    elif scope['type'] == 'section':
        ss_qs = SubSection.objects.filter(section_id=scope['section_id'])
        result['sub_sections'] = list(ss_qs.values('id', 'sub_section_name'))
    elif scope['type'] == 'subsections':
        result['sub_sections'] = list(
            SubSection.objects.filter(pk__in=scope['ids']).values('id', 'sub_section_name')
        )
    elif scope['type'] == 'own':
        result['own_sub_section'] = SubSection.objects.filter(
            pk=scope['sub_section_id']
        ).values('id', 'sub_section_name').first()

    return JsonResponse(result)


@csrf_exempt
def get_all(request):
    section_id     = request.GET.get('section_id')
    sub_section_id = request.GET.get('sub_section_id')  # optional dropdown narrowing
    is_superuser   = request.GET.get('is_superuser', 'false').lower() == 'true'
    grade_id       = int(request.GET.get('grade_id', '0') or 0)
    erp_id         = get_user_erpid(request)

    scope = get_bp_scope(grade_id, erp_id, is_superuser, section_id)

    qs = BusinessPlan.objects.annotate(
        section_name=F('section__name'),
        lead_team_name=F('lead_team__sub_section_name'),
    )
    qs = apply_bp_scope(qs, scope, sub_section_id)

    plans = qs.values(
        'id', 'sr_number', 'parent_sr', 'level',
        'section_id', 'section_name',
        'task', 'start_date', 'end_date',
        'lead_team_id', 'lead_team_name',
        'support_team', 'dependencies', 'deliverables',
        'completion_pct', 'created_by', 'created_at', 'uploaded_by_grade',
    )

    return JsonResponse(list(plans), safe=False)


@csrf_exempt
def upload_excel(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    excel_file = request.FILES.get('file')
    if not excel_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    try:
        from datetime import date, datetime

        wb = openpyxl.load_workbook(excel_file)
        ws = wb.active
        created          = 0
        skipped_dup      = 0
        skipped_section  = 0
        skipped_lead     = 0   # lead_team not found in sub_sections
        skipped_lead_scope = 0 # lead_team found, but not in uploader's allowed subsection list
        erpid            = int(request.POST.get('erpid', 0))
        section_id       = request.POST.get('section_id', None)
        grade            = get_user_grade(request)
        is_superuser     = request.POST.get('is_superuser', 'false').lower() == 'true'

        user_sec_id = int(section_id) if section_id else None

        # Only grade 10/11, grade-9 sub-section-head, or superuser can
        # upload Excel (verified from DB — we don't trust the frontend flag)
        scope = get_bp_scope(grade, erpid, is_superuser, user_sec_id)
        if scope['type'] not in ('all', 'section', 'subsections'):
            return JsonResponse(
                {'error': 'Permission denied — only a section head (grade 9), grade 10/11, or superuser can upload Excel'},
                status=403
            )

        def parse_date(val):
            if not val:
                return None
            if isinstance(val, (date, datetime)):
                return val
            val = str(val).strip()
            for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y'):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
            return None

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue

            sr = str(row[0]).strip()

            # Decide the section
            row_sec_id = int(row[1]) if row[1] else None

            if is_superuser:
                sec_id = row_sec_id or user_sec_id
            else:
                if row_sec_id and row_sec_id != user_sec_id:
                    skipped_section += 1
                    continue
                sec_id = user_sec_id

            task    = str(row[2] or '').strip()
            start   = parse_date(row[3])
            end     = parse_date(row[4])
            lead    = str(row[5] or '').strip()   # sub_section_name or id in Excel
            support = str(row[6] or '').strip()
            dep     = str(row[7] or '').strip()
            deliv   = str(row[8] or '').strip()
            level   = int(row[9] or 0)
            parent  = str(row[10]).strip() if len(row) > 10 and row[10] else None

            # Validate lead_team against the sub_sections table (optional, soft-fail)
            lead_team_obj, found = resolve_lead_team(lead) if lead else (None, True)
            if lead and not found:
                skipped_lead += 1  # no match found — row will still be saved

            # A grade-9 sub-section-head can only upload rows against their own
            # headed subsection(s) — if the lead_team belongs to a different
            # subsection, that row will be skipped (same restriction as add_row, consistent)
            if scope['type'] == 'subsections' and lead_team_obj and lead_team_obj.id not in scope['ids']:
                skipped_lead_scope += 1
                continue

            # Duplicate check — no longer GLOBAL, only checks within its own
            # section + subsection (lead_team). This way, if two different
            # sections/subsections use a similar sr_number scheme
            # (e.g. both have "T-01"), they won't wrongly skip each other
            # as a "duplicate".
            dup_filter = {'sr_number': sr, 'section_id': sec_id}
            if lead_team_obj:
                dup_filter['lead_team_id'] = lead_team_obj.id
            if BusinessPlan.objects.filter(**dup_filter).exists():
                skipped_dup += 1
                continue

            BusinessPlan.objects.create(
                sr_number         = sr,
                parent_sr         = parent or None,
                level             = level,
                section_id        = sec_id,
                task              = task,
                start_date        = start,
                end_date          = end,
                lead_team         = lead_team_obj,
                support_team      = support,
                dependencies      = dep,
                deliverables      = deliv,
                completion_pct    = 0,
                created_by        = erpid,
                uploaded_by_grade = grade,
            )
            created += 1

        return JsonResponse({
            'success': True,
            'rows_created': created,
            'skipped_duplicate': skipped_dup,
            'skipped_other_section': skipped_section,
            'skipped_invalid_lead_team': skipped_lead,
            'skipped_lead_out_of_scope': skipped_lead_scope,
        })

    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)


@csrf_exempt
def add_row(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body)
        grade = get_user_grade(request)
        erpid = get_user_erpid(request)  # from header — we don't trust the body's 'created_by'
        is_superuser = request.GET.get('is_superuser', 'false').lower() == 'true' or data.get('is_superuser', False)
        user_section_id = data.get('user_section_id') or data.get('section_id')

        scope = get_bp_scope(grade, erpid, is_superuser, user_section_id)
        if scope['type'] == 'none':
            return JsonResponse({'error': 'Section/sub-section not found for this user'}, status=403)

        if is_superuser:
            section_id = data.get('section_id') or None
        else:
            section_id = int(user_section_id) if user_section_id else None

        # Validate lead_team against sub_sections — name (comes from dropdown) or id, both work
        lead_team_value = data.get('lead_team_id') or data.get('lead_team')
        lead_team_obj, found = resolve_lead_team(lead_team_value)
        if not found:
            return JsonResponse(
                {'error': f'lead_team "{lead_team_value}" not found in sub_sections table'},
                status=400
            )

        # A normal employee (scope 'own') can only assign their own sub-section as lead_team
        if scope['type'] == 'own':
            if lead_team_obj is None:
                lead_team_obj, _ = resolve_lead_team(str(scope['sub_section_id']))  # default: own sub-section
            elif lead_team_obj.id != scope['sub_section_id']:
                return JsonResponse(
                    {'error': 'You can only add tasks against your own sub-section'},
                    status=403
                )
        elif scope['type'] == 'subsections' and lead_team_obj and lead_team_obj.id not in scope['ids']:
            return JsonResponse(
                {'error': 'You can only add tasks against the sub-section(s) you head'},
                status=403
            )

        # A sub-task's dates must fall within its parent task's date range
        date_error = validate_date_range(
            data.get('start_date'), data.get('end_date'), data.get('parent_sr')
        )
        if date_error:
            return JsonResponse({'error': date_error}, status=400)

        BusinessPlan.objects.create(
            sr_number         = data.get('sr_number'),
            parent_sr         = data.get('parent_sr') or None,
            level             = data.get('level', 0),
            section_id        = section_id,
            task              = data.get('task', ''),
            start_date        = data.get('start_date') or None,
            end_date          = data.get('end_date') or None,
            lead_team         = lead_team_obj,
            support_team      = data.get('support_team', ''),
            dependencies      = data.get('dependencies', ''),
            deliverables      = data.get('deliverables', ''),
            completion_pct    = 0,
            created_by        = erpid,
            uploaded_by_grade = grade,
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def update_row(request, pk):
    if request.method != 'PUT':
        return JsonResponse({'error': 'PUT only'}, status=405)
    try:
        data         = json.loads(request.body)
        grade        = get_user_grade(request)
        erpid        = get_user_erpid(request)
        is_superuser = request.GET.get('is_superuser', 'false').lower() == 'true'
        user_sec_id  = request.GET.get('section_id')

        bp = BusinessPlan.objects.get(pk=pk)

        scope = get_bp_scope(grade, erpid, is_superuser, user_sec_id)
        if not can_modify_row(bp, scope, erpid):
            return JsonResponse({'error': 'Permission denied — this task is outside your scope'}, status=403)

        bp.task           = data.get('task', bp.task)
        bp.start_date     = data.get('start_date') or bp.start_date
        bp.end_date       = data.get('end_date') or bp.end_date
        bp.support_team   = data.get('support_team', bp.support_team)
        bp.dependencies   = data.get('dependencies', bp.dependencies)
        bp.deliverables   = data.get('deliverables', bp.deliverables)
        bp.completion_pct = data.get('completion_pct', bp.completion_pct)

        # lead_team update — validate against sub_sections (name or id, both work)
        if 'lead_team_id' in data or 'lead_team' in data:
            lead_team_value = data.get('lead_team_id') or data.get('lead_team')
            lead_team_obj, found = resolve_lead_team(lead_team_value)
            if not found:
                return JsonResponse(
                    {'error': f'lead_team "{lead_team_value}" not found in sub_sections table'},
                    status=400
                )
            bp.lead_team = lead_team_obj

        if 'section_id' in data:
            bp.section_id = data.get('section_id') or None

        # A sub-task's dates must fall within its parent task's date range
        date_error = validate_date_range(bp.start_date, bp.end_date, bp.parent_sr)
        if date_error:
            return JsonResponse({'error': date_error}, status=400)

        bp.save()

        # 🔧 FIX: if completion_pct was changed manually (defensive — the UI
        # now keeps this field read-only, but for API safety), also
        # resync the parent chain
        from .models import sync_parent_completion
        sync_parent_completion(bp)

        return JsonResponse({'success': True})
    except BusinessPlan.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_all_descendant_ids(task_sr):
    """
    Given a task's sr_number, returns the IDs of all its children and grandchildren (cascade).
    """
    all_ids = []
    queue = [task_sr]
    while queue:
        current_sr = queue.pop(0)
        children = BusinessPlan.objects.filter(parent_sr=current_sr)
        for child in children:
            all_ids.append(child.id)
            queue.append(child.sr_number)
    return all_ids


def resequence_siblings(parent_sr):
    """
    Updates the sr_number of all a parent's child tasks as 01, 02, 03... etc.
    If parent_sr is None, top-level tasks are resequenced.
    """
    siblings = BusinessPlan.objects.filter(parent_sr=parent_sr).order_by('sr_number')
    for idx, sibling in enumerate(siblings, start=1):
        if parent_sr:
            new_sr = f"{parent_sr}-{str(idx).zfill(2)}"
        else:
            # Top-level: preserve the prefix, only update the number
            parts = sibling.sr_number.rsplit('-', 1)
            if len(parts) == 2:
                prefix = parts[0]
                new_sr = f"{prefix}-{str(idx).zfill(2)}"
            else:
                new_sr = sibling.sr_number  # couldn't understand the format, leave it as is

        if sibling.sr_number != new_sr:
            old_sr = sibling.sr_number
            sibling.sr_number = new_sr
            sibling.save(update_fields=['sr_number'])
            # Also update this sibling's children's parent_sr
            BusinessPlan.objects.filter(parent_sr=old_sr).update(parent_sr=new_sr)
            # Recursively resequence this sibling's children too
            resequence_siblings(new_sr)


@csrf_exempt
def delete_row(request, pk):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE only'}, status=405)
    try:
        from activities.models import EmployeeActivity

        is_superuser     = request.GET.get('is_superuser', 'false').lower() == 'true'
        user_section_id  = request.GET.get('section_id')
        grade            = get_user_grade(request)
        erpid            = get_user_erpid(request)

        bp = BusinessPlan.objects.get(pk=pk)

        scope = get_bp_scope(grade, erpid, is_superuser, user_section_id)
        if not can_modify_row(bp, scope, erpid):
            return JsonResponse(
                {'error': 'Permission denied — this task is outside your scope'},
                status=403
            )

        # Get the IDs of all this task's children and grandchildren
        descendant_ids = get_all_descendant_ids(bp.sr_number)
        all_task_ids = [pk] + descendant_ids

        # Check: does an activity exist against any task (parent or child)?
        if EmployeeActivity.objects.filter(bp_task_id__in=all_task_ids).exists():
            return JsonResponse(
                {
                    'error': (
                        'Cannot delete — employee activities exist against this task '
                        'or its child tasks'
                    )
                },
                status=400
            )

        parent_sr = bp.parent_sr

        # First delete all children (cascade), then the parent
        BusinessPlan.objects.filter(id__in=descendant_ids).delete()
        bp.delete()

        # NOTE: This used to call resequence_siblings(parent_sr) here, which
        # would resequence the remaining siblings' sr_number as 01,02,03...
        # This has been deliberately removed — the sr_number needs to stay
        # STABLE/PERMANENT, otherwise duplicate-detection gives a wrong
        # result on Excel re-upload (a deleted task gets mistaken for a
        # "duplicate" and skipped, and another task's number gets changed,
        # creating a new duplicate). After a delete, a gap in the numbering
        # is left behind — the way invoice/ticket numbering works.

        # Resync the parent chain's completion %
        from .models import recalc_chain_from_parent_sr
        recalc_chain_from_parent_sr(parent_sr)

        return JsonResponse({'success': True})
    except BusinessPlan.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)


# ─────────────────────────────────────────────────────────────
# GET /businessplan/main-task-report/
#
# Comprehensive report: for every Level-0 (main) task —
#   - how many sub-tasks (level 1, level 2 ... all descendants) it has
#   - how much % each employee has done against each sub-task
#     (from EmployeeActivity, latest record per employee per task)
#   - each sub-task's own completion_pct (from BusinessPlan)
#   - the main task's overall completion_pct (already-maintained rollup)
#
# Access rules same as get_all(): superuser sees everything,
# others restricted to their own section.
# ─────────────────────────────────────────────────────────────
@csrf_exempt
def get_main_task_report(request):
    from activities.models import EmployeeActivity

    section_id   = request.GET.get('section_id')
    is_superuser = request.GET.get('is_superuser', 'false').lower() == 'true'
    grade        = get_user_grade(request)
    erpid        = get_user_erpid(request)

    # Only section-head (grade 9), grade 10/11, or superuser can see the
    # Main Task Report — not for a normal employee
    scope = get_bp_scope(grade, erpid, is_superuser, section_id)
    if scope['type'] not in ('all', 'section', 'subsections'):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    qs = BusinessPlan.objects.annotate(
        section_name=F('section__name'),
        lead_team_name=F('lead_team__sub_section_name'),
    )
    qs = apply_bp_scope(qs, scope)

    all_tasks = list(qs.values(
        'id', 'sr_number', 'parent_sr', 'level',
        'section_id', 'section_name', 'task',
        'start_date', 'end_date', 'lead_team_name',
        'completion_pct',
    ))

    # Index by sr_number for quick child lookup
    by_parent = {}
    for t in all_tasks:
        by_parent.setdefault(t['parent_sr'], []).append(t)

    def get_descendants(sr_number):
        """All children, grandchildren, etc. of a task (flat list)."""
        result = []
        queue = [sr_number]
        while queue:
            current = queue.pop(0)
            children = by_parent.get(current, [])
            for child in children:
                result.append(child)
                queue.append(child['sr_number'])
        return result

    # Pull all activities once, build erp_id -> name map
    all_task_ids = [t['id'] for t in all_tasks]
    activities = list(
        EmployeeActivity.objects
        .filter(bp_task_id__in=all_task_ids)
        .order_by('bp_task_id', 'erp_id', '-activity_date', '-created_at')
        .values('bp_task_id', 'erp_id', 'overall_pct', 'status', 'activity_date')
    )

    erp_ids = list({a['erp_id'] for a in activities})
    try:
        from users.models import Employees
        emp_map = {
            e['erp_id']: e['name']
            for e in Employees.objects.filter(erp_id__in=erp_ids).values('erp_id', 'name')
        }
    except Exception:
        emp_map = {}

    # Keep only the LATEST activity per (bp_task, erp_id) — list is already
    # ordered so first occurrence per pair is the latest one
    latest_seen = set()
    activities_by_task = {}
    for a in activities:
        key = (a['bp_task_id'], a['erp_id'])
        if key in latest_seen:
            continue
        latest_seen.add(key)
        activities_by_task.setdefault(a['bp_task_id'], []).append({
            'erp_id': a['erp_id'],
            'employee_name': emp_map.get(a['erp_id'], str(a['erp_id'])),
            'overall_pct': a['overall_pct'],
            'status': a['status'],
            'activity_date': a['activity_date'],
        })

    # Build report: only Level-0 (main) tasks as top-level report entries
    report = []
    main_tasks = [t for t in all_tasks if t['level'] == 0]

    for main in main_tasks:
        descendants = get_descendants(main['sr_number'])
        sub_tasks = []
        for d in descendants:
            sub_tasks.append({
                'id': d['id'],
                'sr_number': d['sr_number'],
                'level': d['level'],
                'task': d['task'],
                'lead_team_name': d['lead_team_name'],
                'start_date': d['start_date'],
                'end_date': d['end_date'],
                'completion_pct': d['completion_pct'],
                'employees': activities_by_task.get(d['id'], []),
            })

        report.append({
            'id': main['id'],
            'sr_number': main['sr_number'],
            'task': main['task'],
            'section_name': main['section_name'],
            'lead_team_name': main['lead_team_name'],
            'start_date': main['start_date'],
            'end_date': main['end_date'],
            'overall_completion_pct': main['completion_pct'],
            'total_sub_tasks': len(sub_tasks),
            'sub_tasks': sub_tasks,
            # Direct activities logged on the main task itself (if any)
            'employees': activities_by_task.get(main['id'], []),
        })

    return JsonResponse(report, safe=False)


@csrf_exempt
def delete_all(request):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE only'}, status=405)
    try:
        from activities.models import EmployeeActivity

        grade        = get_user_grade(request)
        erpid        = get_user_erpid(request)
        is_superuser = request.GET.get('is_superuser', 'false').lower() == 'true'
        section_id   = request.GET.get('section_id')

        scope = get_bp_scope(grade, erpid, is_superuser, section_id)
        if scope['type'] not in ('all', 'section', 'subsections'):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        target_qs = apply_bp_scope(BusinessPlan.objects.all(), scope)
        target_ids = list(target_qs.values_list('id', flat=True))

        if EmployeeActivity.objects.filter(bp_task_id__in=target_ids).exists():
            return JsonResponse(
                {'error': 'Cannot delete — employee activities exist against some tasks. Please delete the activities first.'},
                status=400
            )

        BusinessPlan.objects.filter(id__in=target_ids).delete()
        return JsonResponse({'success': True, 'deleted_count': len(target_ids)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)