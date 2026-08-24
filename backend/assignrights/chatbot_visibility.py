"""Who may see the HR Assistant launcher.

Administered from the Assign Rights screen. The rule is stored here so it
applies to everyone's browser rather than the one that set it; the check that
acts on it lives in the frontend widget, and nothing about how the assistant
answers questions is affected.

Reading the rule is open, like the rest of this API — it reveals only whether a
feature is switched on. Changing it is not: a policy that governs every user
should not be rewritable by an unauthenticated POST, so the write verifies the
signature on the dashboard's own login token and requires a superuser. That is
the same token and the same signing key the chat service verifies.

It does not enforce the token's one-hour `expires` stamp, because nothing else
in this API does and the frontend does not sign people out - see
`_admin_from_token`.
"""

import json
import logging

import jwt
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import ChatbotVisibilityModel, ChatbotVisibilityUserModel

logger = logging.getLogger(__name__)


def _policy() -> ChatbotVisibilityModel:
    """The single settings row, created on first use as "all"."""
    policy = ChatbotVisibilityModel.objects.order_by("id").first()
    if policy is None:
        policy = ChatbotVisibilityModel.objects.create(
            mode=ChatbotVisibilityModel.MODE_ALL
        )
    return policy


def _allowed_user_ids() -> list:
    return sorted(
        ChatbotVisibilityUserModel.objects.values_list("user_id", flat=True)
    )


def _is_visible_to(policy: ChatbotVisibilityModel, user_id) -> bool:
    if policy.mode == ChatbotVisibilityModel.MODE_NONE:
        return False
    if policy.mode == ChatbotVisibilityModel.MODE_ALL:
        return True

    try:
        return int(user_id) in set(_allowed_user_ids())
    except (TypeError, ValueError):
        return False


def _admin_from_token(request):
    """The superuser behind this request, or (None, reason).

    Accepts the JWT the dashboard's login issues, in the Authorization header.
    """
    header = request.headers.get("Authorization") or ""
    token = header[7:].strip() if header.lower().startswith("bearer ") else header.strip()

    if not token:
        return None, "Sign in as an administrator to change this."

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except jwt.PyJWTError:
        return None, "That session is not valid any more. Sign in again."

    # The token's stamped `expires` is deliberately not enforced. The dashboard
    # sets it an hour out but nothing else in this API checks it, and the
    # frontend keeps the session until the user signs out - so enforcing it here
    # rejected administrators who had simply been logged in since the morning,
    # while every other endpoint kept working. Being stricter than the
    # application's own idea of a session made this feature look broken.
    #
    # A real session lifetime belongs in one place - an axios interceptor plus a
    # middleware - rather than in this one view. Until then the signature is
    # what is checked, which still refuses anything not issued by this
    # dashboard.

    if not payload.get("is_superuser"):
        return None, "Only an administrator can change this."

    return payload, None


@require_GET
def get_visibility(request):
    """The current rule.

    With `?user_id=` it answers only "can this user see it", which is all the
    widget needs. Without it, it returns the whole rule for the Assign Rights
    screen.
    """
    policy = _policy()
    user_id = request.GET.get("user_id")

    if user_id:
        return JsonResponse(
            {
                "mode": policy.mode,
                "visible": _is_visible_to(policy, user_id),
            },
            status=200,
        )

    return JsonResponse(
        {
            "mode": policy.mode,
            "user_ids": _allowed_user_ids(),
            "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
            "updated_by": policy.updated_by,
        },
        status=200,
    )


@csrf_exempt
@require_POST
def set_visibility(request):
    """Replace the rule. Administrators only."""
    admin, refusal = _admin_from_token(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    mode = str(data.get("mode", "")).strip().lower()
    if mode not in ChatbotVisibilityModel.MODES:
        return JsonResponse(
            {"error": f"mode must be one of {', '.join(ChatbotVisibilityModel.MODES)}"},
            status=400,
        )

    user_ids = data.get("user_ids") or []
    if not isinstance(user_ids, list):
        return JsonResponse({"error": "user_ids must be a list"}, status=400)

    cleaned = []
    for value in user_ids:
        try:
            cleaned.append(int(value))
        except (TypeError, ValueError):
            return JsonResponse({"error": f"Not a user id: {value!r}"}, status=400)

    if mode == ChatbotVisibilityModel.MODE_SPECIFIC and not cleaned:
        return JsonResponse(
            {"error": "Choose at least one user, or set the mode to nobody."},
            status=400,
        )

    policy = _policy()
    policy.mode = mode
    policy.updated_by = admin.get("user_id")
    policy.save()

    # The list is only meaningful for "specific"; clearing it otherwise keeps a
    # stale selection from silently coming back the next time that mode is set.
    ChatbotVisibilityUserModel.objects.all().delete()
    if mode == ChatbotVisibilityModel.MODE_SPECIFIC:
        ChatbotVisibilityUserModel.objects.bulk_create(
            [ChatbotVisibilityUserModel(user_id=uid) for uid in set(cleaned)]
        )

    logger.info(
        "chatbot visibility set to %s for %d user(s) by auth user %s",
        mode, len(set(cleaned)), policy.updated_by,
    )

    return JsonResponse(
        {"mode": policy.mode, "user_ids": _allowed_user_ids()}, status=200
    )
