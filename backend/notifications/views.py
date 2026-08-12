import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Notification

# Cap on a single page of notifications, so the dropdown never pulls the whole
# history of a long-serving employee.
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def serialize(notification):
    return {
        "id": notification.pk,
        "category": notification.category,
        "event": notification.event,
        "title": notification.title,
        "message": notification.message,
        "link": notification.link,
        "related_id": notification.related_id,
        "actor_erp_id": notification.actor_erp_id,
        "is_read": notification.is_read,
        "created_at": notification.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


@require_GET
def get_notifications(request, erpid):
    """Notifications for one employee, newest first.

    `?unread=1` restricts to unread. `unread_count` is always the total unread
    count, not the count within this page, so the badge stays correct even
    when the list is truncated.
    """
    queryset = Notification.objects.filter(recipient_erp_id=erpid)

    unread_count = queryset.filter(is_read=False).count()

    if request.GET.get("unread") in ("1", "true", "True"):
        queryset = queryset.filter(is_read=False)

    try:
        limit = min(int(request.GET.get("limit", DEFAULT_LIMIT)), MAX_LIMIT)
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    items = [serialize(n) for n in queryset[:max(1, limit)]]

    return JsonResponse(
        {"notifications": items, "unread_count": unread_count},
        status=200,
    )


@csrf_exempt
@require_POST
def mark_read(request):
    """Mark one or more notifications read.

    Accepts {"id": 1} or {"ids": [1,2,3]}. Scoped by erp_id when supplied so
    one employee cannot clear another's notifications by guessing ids.
    """
    data = json.loads(request.body.decode("utf-8"))

    ids = data.get("ids")
    if ids is None and data.get("id") is not None:
        ids = [data.get("id")]

    if not ids:
        return JsonResponse({"error": "id or ids is required"}, status=400)

    queryset = Notification.objects.filter(pk__in=ids)
    if data.get("erp_id"):
        queryset = queryset.filter(recipient_erp_id=data.get("erp_id"))

    updated = queryset.update(is_read=True)
    return JsonResponse({"updated": updated}, status=200)


@csrf_exempt
@require_POST
def mark_all_read(request):
    data = json.loads(request.body.decode("utf-8"))
    erp_id = data.get("erp_id")

    if not erp_id:
        return JsonResponse({"error": "erp_id is required"}, status=400)

    updated = Notification.objects.filter(
        recipient_erp_id=erp_id, is_read=False
    ).update(is_read=True)

    return JsonResponse({"updated": updated}, status=200)
