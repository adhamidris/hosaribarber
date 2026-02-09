from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save, pre_save
from django.db.models.fields.files import FieldFile
from django.dispatch import receiver

from appointments.models import Appointment
from clients.models import Client
from core.request_context import get_current_user
from services.models import Service

from .models import AuditActionChoices, AuditLog


TRACKED_MODELS = (Client, Service, Appointment)


def _serialize_value(value):
    if isinstance(value, FieldFile):
        return value.name or ""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def _snapshot_instance(instance):
    data = {}
    for field in instance._meta.fields:
        data[field.name] = _serialize_value(getattr(instance, field.attname))
    return data


def _snapshot_db_values(sender, values):
    data = {}
    for field in sender._meta.fields:
        data[field.name] = _serialize_value(values.get(field.attname))
    return data


def _build_update_changes(old_state, new_state):
    changes = {}
    for field_name, new_value in new_state.items():
        old_value = old_state.get(field_name)
        if old_value != new_value:
            changes[field_name] = {"old": old_value, "new": new_value}
    return changes


def _build_create_changes(new_state):
    return {field_name: {"old": None, "new": value} for field_name, value in new_state.items()}


def _build_delete_changes(old_state):
    return {field_name: {"old": value, "new": None} for field_name, value in old_state.items()}


def _create_log(instance, action, changed_fields):
    AuditLog.objects.create(
        content_type=ContentType.objects.get_for_model(instance.__class__),
        object_id=instance.pk,
        action=action,
        changed_fields=changed_fields,
        actor=get_current_user(),
    )


@receiver(pre_save)
def capture_old_state(sender, instance, **kwargs):
    if sender not in TRACKED_MODELS or not instance.pk:
        return
    old_values = sender.objects.filter(pk=instance.pk).values().first()
    if old_values:
        instance._audit_old_state = _snapshot_db_values(sender, old_values)


@receiver(post_save)
def create_or_update_audit(sender, instance, created, raw=False, **kwargs):
    if raw or sender not in TRACKED_MODELS:
        return

    new_state = _snapshot_instance(instance)
    if created:
        changes = _build_create_changes(new_state)
        _create_log(instance, AuditActionChoices.CREATE, changes)
        return

    old_state = getattr(instance, "_audit_old_state", {})
    changes = _build_update_changes(old_state, new_state)
    if changes:
        _create_log(instance, AuditActionChoices.UPDATE, changes)


@receiver(post_delete)
def delete_audit(sender, instance, **kwargs):
    if sender not in TRACKED_MODELS:
        return
    old_state = _snapshot_instance(instance)
    _create_log(instance, AuditActionChoices.DELETE, _build_delete_changes(old_state))
