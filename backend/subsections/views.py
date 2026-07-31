from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import SubSection
import json


# ─────────────────────────────────────────────────────────────────────────────
# NOTE: head_employee_id stores the employee's erp_id directly (that's how
# create_sub_section / update_sub_section write it), even though the Django
# FK is technically declared against Employees.id. So we must NOT resolve the
# head employee's name via the ORM relation (head_employee__name) — that
# performs a JOIN against Employees.id and silently drops any row whose
# head_employee_id (erp_id) doesn't happen to match a real Employees.id.
# Instead we resolve the name manually by erp_id. (Same convention already
# used in activities/views.py._get_head_subsections.)
# ─────────────────────────────────────────────────────────────────────────────
def _attach_head_employee_names(rows):
    from users.models import Employees

    erp_ids = {r['head_employee_id'] for r in rows if r.get('head_employee_id') is not None}
    name_map = {
        e['erp_id']: e['name']
        for e in Employees.objects.filter(erp_id__in=erp_ids).values('erp_id', 'name')
    }
    for r in rows:
        r['head_employee__name'] = name_map.get(r.get('head_employee_id'))
    return rows


# ─── List all Sub Sections ────────────────────────────────────────────────────
@csrf_exempt
def get_sub_sections(request):
    section_id   = request.GET.get('section_id', '')
    is_superuser = request.GET.get('is_superuser', 'false') == 'true'

    qs = SubSection.objects.all()

    if not is_superuser and section_id:
        qs = qs.filter(section_id=int(section_id))

    data = list(qs.values(
        'id',
        'sub_section_name',
        'section_id',
        'section__name',
        'head_employee_id',
        'created_at',
    ))
    data = _attach_head_employee_names(data)
    return JsonResponse(data, safe=False)


# ─── Get single Sub Section ───────────────────────────────────────────────────
@csrf_exempt
def get_sub_section_detail(request, pk):
    try:
        obj = SubSection.objects.values(
            'id',
            'sub_section_name',
            'section_id',
            'section__name',
            'head_employee_id',
            'created_at',
        ).get(pk=pk)
        obj = _attach_head_employee_names([obj])[0]
        return JsonResponse(obj)
    except SubSection.DoesNotExist:
        return JsonResponse({'error': 'Sub section not found'}, status=404)


# ─── Create Sub Section ───────────────────────────────────────────────────────
@csrf_exempt
def create_sub_section(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data             = json.loads(request.body)
        sub_section_name = data.get('sub_section_name', '').strip()
        section_id       = data.get('section_id')
        head_employee_id = data.get('head_employee_id')

        if not sub_section_name:
            return JsonResponse({'error': 'sub_section_name is required'}, status=400)
        if not section_id:
            return JsonResponse({'error': 'section_id is required'}, status=400)
        if not head_employee_id:
            return JsonResponse({'error': 'head_employee_id is required'}, status=400)

        # Guard: prevent case-variant duplicates (e.g. "IT" and "it") within the
        # same section. Business Plan resolves lead_team by name using a
        # case-insensitive match (sub_section_name__iexact) — if two rows in
        # the same section differed only by case, that lookup would raise
        # MultipleObjectsReturned. Name uniqueness here is case-insensitive
        # per section (different sections may still reuse the same name).
        if SubSection.objects.filter(
            section_id=int(section_id), sub_section_name__iexact=sub_section_name
        ).exists():
            return JsonResponse(
                {'error': f'A sub section named "{sub_section_name}" already exists in this section.'},
                status=400,
            )

        obj = SubSection.objects.create(
            sub_section_name=sub_section_name,
            section_id=int(section_id),
            head_employee_id=int(head_employee_id),
        )
        return JsonResponse({'success': True, 'id': obj.id, 'sub_section_name': obj.sub_section_name})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─── Update Sub Section ───────────────────────────────────────────────────────
@csrf_exempt
def update_sub_section(request, pk):
    if request.method != 'PUT':
        return JsonResponse({'error': 'PUT only'}, status=405)
    try:
        data = json.loads(request.body)
        obj  = SubSection.objects.get(pk=pk)

        new_name       = data.get('sub_section_name', obj.sub_section_name).strip()
        new_section_id = int(data['section_id']) if 'section_id' in data else obj.section_id

        # Same guard as create: avoid case-variant duplicates within a section
        if SubSection.objects.filter(
            section_id=new_section_id, sub_section_name__iexact=new_name
        ).exclude(pk=pk).exists():
            return JsonResponse(
                {'error': f'A sub section named "{new_name}" already exists in this section.'},
                status=400,
            )

        obj.sub_section_name = new_name
        obj.section_id = new_section_id

        if 'head_employee_id' in data:
            obj.head_employee_id = int(data['head_employee_id'])

        obj.save()
        return JsonResponse({'success': True, 'id': obj.id, 'sub_section_name': obj.sub_section_name})
    except SubSection.DoesNotExist:
        return JsonResponse({'error': 'Sub section not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─── Delete Sub Section ───────────────────────────────────────────────────────
@csrf_exempt
def delete_sub_section(request, pk):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE only'}, status=405)
    try:
        obj = SubSection.objects.get(pk=pk)

        # Guard: employees.sub_section_id has a DB-level FK constraint pointing
        # to this table. If any employee is still assigned to this sub section,
        # deleting it would fail with a raw SQL Server FK-constraint error.
        from users.models import Employees
        force = request.GET.get('force', 'false').lower() == 'true'
        assigned_qs = Employees.objects.filter(sub_section_id=pk)
        assigned_count = assigned_qs.count()

        if assigned_count > 0:
            if not force:
                return JsonResponse(
                    {
                        'error': (
                            f"Cannot delete: {assigned_count} employee(s) are currently "
                            "assigned to this sub section. Please reassign them to a "
                            "different sub section first (via Assign Sub Section page)."
                        ),
                        'assigned_count': assigned_count,
                    },
                    status=409,
                )
            # force=true: unassign the affected employees first, then delete
            assigned_qs.update(sub_section_id=None)

        obj.delete()
        return JsonResponse({'success': True, 'unassigned_employees': assigned_count})
    except SubSection.DoesNotExist:
        return JsonResponse({'error': 'Sub section not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
