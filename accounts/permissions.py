from .models import PermissionToggle


def has_permission_toggle(user, key: str, default: bool = True) -> bool:
    if not user or not user.is_authenticated:
        return False

    user_toggle = (
        PermissionToggle.objects.filter(user=user, key=key)
        .values_list("is_allowed", flat=True)
        .first()
    )
    if user_toggle is not None:
        return user_toggle

    role_toggle = (
        PermissionToggle.objects.filter(role=user.role, user__isnull=True, key=key)
        .values_list("is_allowed", flat=True)
        .first()
    )
    if role_toggle is not None:
        return role_toggle

    return default
