from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from ai_playground.models import PlaygroundGeneration, PlaygroundRateLimitEvent, PlaygroundSession


class Command(BaseCommand):
    help = (
        "Delete expired AI Playground sessions, old generations, and stale rate-limit events "
        "based on retention policy."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention-hours",
            type=int,
            default=None,
            help="Retention period in hours (defaults to AI_PLAYGROUND_DATA_RETENTION_HOURS).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without applying changes.",
        )

    def handle(self, *args, **options):
        retention_hours = options.get("retention_hours")
        if retention_hours is None:
            retention_hours = int(getattr(settings, "AI_PLAYGROUND_DATA_RETENTION_HOURS", 24))
        retention_hours = max(1, int(retention_hours))

        dry_run = bool(options.get("dry_run", False))
        cutoff = timezone.now() - timedelta(hours=retention_hours)

        expired_session_ids = list(
            PlaygroundSession.objects.filter(expires_at__lt=cutoff).values_list("id", flat=True)
        )
        stale_generation_qs = PlaygroundGeneration.objects.filter(
            Q(created_at__lt=cutoff) | Q(session_id__in=expired_session_ids)
        ).distinct()
        stale_generations = list(stale_generation_qs)
        stale_sessions = list(PlaygroundSession.objects.filter(id__in=expired_session_ids))
        stale_rate_events_qs = PlaygroundRateLimitEvent.objects.filter(
            Q(created_at__lt=cutoff) | Q(session_id__in=expired_session_ids)
        ).distinct()

        self.stdout.write(
            self.style.NOTICE(
                f"[AI Playground cleanup] cutoff={cutoff.isoformat()} "
                f"sessions={len(stale_sessions)} generations={len(stale_generations)} "
                f"rate_events={stale_rate_events_qs.count()} dry_run={dry_run}"
            )
        )

        if dry_run:
            return

        for generation in stale_generations:
            if generation.selfie_image:
                generation.selfie_image.delete(save=False)
            if generation.custom_style_image:
                generation.custom_style_image.delete(save=False)
            if generation.result_image:
                generation.result_image.delete(save=False)

        deleted_generations = stale_generation_qs.delete()[0]

        for session in stale_sessions:
            if session.selfie_image:
                session.selfie_image.delete(save=False)

        deleted_sessions = PlaygroundSession.objects.filter(id__in=expired_session_ids).delete()[0]
        deleted_events = stale_rate_events_qs.delete()[0]

        self.stdout.write(
            self.style.SUCCESS(
                f"[AI Playground cleanup] deleted generations={deleted_generations} "
                f"sessions={deleted_sessions} rate_events={deleted_events}"
            )
        )
