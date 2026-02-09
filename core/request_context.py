from contextvars import ContextVar


_current_user = ContextVar("current_user", default=None)


def set_current_user(user):
    return _current_user.set(user)


def reset_current_user(token):
    _current_user.reset(token)


def get_current_user():
    user = _current_user.get()
    if user and getattr(user, "is_authenticated", False):
        return user
    return None
