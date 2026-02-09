from datetime import datetime, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RoleChoices, User
from clients.models import Client
from services.models import Service

from .models import Appointment, AppointmentStatusChoices


class AppointmentViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner1",
            password="pass12345",
            role=RoleChoices.OWNER_ADMIN,
        )
        self.barber = User.objects.create_user(
            username="barber2",
            password="pass12345",
            role=RoleChoices.BARBER,
        )
        self.client.force_login(self.user)

        self.client_profile = Client.objects.create(
            full_name="Ahmed Magdy",
            phone="01011112222",
            created_by=self.user,
            updated_by=self.user,
        )
        self.service = Service.objects.create(
            name_ar="لحية",
            name_en="Beard",
            default_duration_minutes=25,
            price=Decimal("80.00"),
            is_active=True,
        )
        self.service_2 = Service.objects.create(
            name_ar="شعر",
            name_en="Haircut",
            default_duration_minutes=35,
            price=Decimal("120.00"),
            is_active=True,
        )

    def test_appointment_create(self):
        start_at = timezone.localtime().replace(second=0, microsecond=0)
        response = self.client.post(
            reverse("appointment-list"),
            {
                "classification": "booking",
                "phone": self.client_profile.phone,
                "full_name": "",
                "barber": str(self.barber.id),
                "services": [str(self.service.id), str(self.service_2.id)],
                "start_at": start_at.strftime("%Y-%m-%dT%H:%M"),
                "status": AppointmentStatusChoices.CANCELLED,
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.objects.count(), 1)
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.client_id, self.client_profile.id)
        self.assertEqual(appointment.status, AppointmentStatusChoices.SCHEDULED)
        self.assertEqual(set(appointment.services.values_list("id", flat=True)), {self.service.id, self.service_2.id})
        self.assertEqual(appointment.total_price, Decimal("200.00"))
        self.assertEqual(
            appointment.end_at - appointment.start_at,
            timezone.timedelta(minutes=self.service.default_duration_minutes + self.service_2.default_duration_minutes),
        )

    def test_appointment_form_create_without_end_at(self):
        start_at = timezone.localtime().replace(second=0, microsecond=0)
        response = self.client.post(
            reverse("appointment-list"),
            {
                "classification": "booking",
                "phone": "01033334444",
                "full_name": "New Booking Client",
                "barber": str(self.barber.id),
                "services": [str(self.service.id), str(self.service_2.id)],
                "start_at": start_at.strftime("%Y-%m-%dT%H:%M"),
                "status": AppointmentStatusChoices.CANCELLED,
                "notes": "Customer requested classic cut.",
            },
        )

        self.assertEqual(response.status_code, 302)
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.client.phone, "01033334444")
        self.assertEqual(appointment.client.full_name, "New Booking Client")
        self.assertEqual(appointment.status, AppointmentStatusChoices.SCHEDULED)
        self.assertEqual(set(appointment.services.values_list("id", flat=True)), {self.service.id, self.service_2.id})
        self.assertEqual(appointment.total_price, Decimal("200.00"))
        self.assertEqual(
            appointment.end_at - appointment.start_at,
            timezone.timedelta(minutes=self.service.default_duration_minutes + self.service_2.default_duration_minutes),
        )

    def test_appointment_update(self):
        appointment = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service,
            start_at=timezone.now(),
            end_at=timezone.now() + timezone.timedelta(minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            created_by=self.user,
            updated_by=self.user,
            total_price=Decimal("80.00"),
        )
        appointment.services.set([self.service])

        response = self.client.post(
            reverse("appointment-update", args=[appointment.id]),
            {
                "client": str(self.client_profile.id),
                "barber": str(self.barber.id),
                "services": [str(self.service.id), str(self.service_2.id)],
                "start_at": timezone.localtime(appointment.start_at).strftime("%Y-%m-%dT%H:%M"),
                "end_at": timezone.localtime(appointment.end_at).strftime("%Y-%m-%dT%H:%M"),
                "status": AppointmentStatusChoices.CONFIRMED,
                "notes": "Updated from form",
            },
        )
        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatusChoices.CONFIRMED)
        self.assertEqual(set(appointment.services.values_list("id", flat=True)), {self.service.id, self.service_2.id})
        self.assertEqual(appointment.total_price, Decimal("200.00"))
        self.assertEqual(appointment.notes, "Updated from form")

    def test_walkin_create(self):
        before_create = timezone.now()
        response = self.client.post(
            reverse("appointment-list"),
            {
                "classification": "walk_in",
                "full_name": "Walk In User",
                "phone": "01555555555",
                "services": [str(self.service.id), str(self.service_2.id)],
                "barber": str(self.barber.id),
                "status": AppointmentStatusChoices.CANCELLED,
                "notes": "Rush",
            },
        )
        after_create = timezone.now()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.objects.filter(is_walk_in=True).count(), 1)
        appointment = Appointment.objects.get(is_walk_in=True)
        self.assertGreaterEqual(appointment.start_at, before_create)
        self.assertLessEqual(appointment.start_at, after_create)
        self.assertEqual(appointment.status, AppointmentStatusChoices.SCHEDULED)
        self.assertEqual(set(appointment.services.values_list("id", flat=True)), {self.service.id, self.service_2.id})
        self.assertEqual(appointment.total_price, Decimal("200.00"))
        self.assertEqual(
            appointment.end_at - appointment.start_at,
            timezone.timedelta(minutes=self.service.default_duration_minutes + self.service_2.default_duration_minutes),
        )

    def test_walkin_form_create_without_start_or_duration(self):
        before_create = timezone.now()
        response = self.client.post(
            reverse("appointment-list"),
            {
                "classification": "walk_in",
                "full_name": "Quick Walkin",
                "phone": "01555555556",
                "services": [str(self.service.id), str(self.service_2.id)],
                "barber": str(self.barber.id),
                "status": AppointmentStatusChoices.CANCELLED,
                "notes": "Needs quick service.",
            },
        )
        after_create = timezone.now()

        self.assertEqual(response.status_code, 302)
        appointment = Appointment.objects.get(is_walk_in=True, client__phone="01555555556")
        self.assertGreaterEqual(appointment.start_at, before_create)
        self.assertLessEqual(appointment.start_at, after_create)
        self.assertEqual(appointment.status, AppointmentStatusChoices.SCHEDULED)
        self.assertEqual(set(appointment.services.values_list("id", flat=True)), {self.service.id, self.service_2.id})
        self.assertEqual(appointment.total_price, Decimal("200.00"))
        self.assertEqual(
            appointment.end_at - appointment.start_at,
            timezone.timedelta(minutes=self.service.default_duration_minutes + self.service_2.default_duration_minutes),
        )

    def test_appointment_list_defaults_to_today_queue(self):
        today_start = timezone.make_aware(datetime.combine(timezone.localdate(), time(hour=12, minute=0)))
        yesterday_start = today_start - timezone.timedelta(days=1)

        booking_today = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service,
            start_at=today_start,
            end_at=today_start + timezone.timedelta(minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=False,
            total_price=Decimal("80.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        booking_today.services.set([self.service])
        walkin_today = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service_2,
            start_at=today_start + timezone.timedelta(hours=1),
            end_at=today_start + timezone.timedelta(hours=1, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=True,
            total_price=Decimal("120.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        walkin_today.services.set([self.service_2])
        old_booking = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service,
            start_at=yesterday_start,
            end_at=yesterday_start + timezone.timedelta(minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=False,
            total_price=Decimal("80.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        old_booking.services.set([self.service])

        response = self.client.get(reverse("appointment-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["scope"], "today_queue")

        listed_ids = [appointment.id for appointment in response.context["appointments"]]
        self.assertEqual(listed_ids, [booking_today.id, walkin_today.id])
        self.assertNotIn(old_booking.id, listed_ids)

    def test_appointment_list_all_history_orders_by_latest_start(self):
        now = timezone.now().replace(second=0, microsecond=0)
        booking_old = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service,
            start_at=now - timezone.timedelta(days=3),
            end_at=now - timezone.timedelta(days=3) + timezone.timedelta(minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=False,
            total_price=Decimal("80.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        booking_old.services.set([self.service])
        walkin_recent = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service_2,
            start_at=now - timezone.timedelta(hours=2),
            end_at=now - timezone.timedelta(hours=1, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=True,
            total_price=Decimal("120.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        walkin_recent.services.set([self.service_2])
        booking_latest = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service,
            start_at=now + timezone.timedelta(days=1),
            end_at=now + timezone.timedelta(days=1, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=False,
            total_price=Decimal("80.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        booking_latest.services.set([self.service])

        response = self.client.get(reverse("appointment-list"), {"scope": "all_history"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["scope"], "all_history")

        listed_ids = [appointment.id for appointment in response.context["appointments"]]
        self.assertEqual(listed_ids[:3], [booking_latest.id, walkin_recent.id, booking_old.id])

    def test_appointment_list_type_filter_walk_ins_only(self):
        now = timezone.now().replace(second=0, microsecond=0)
        booking = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service,
            start_at=now + timezone.timedelta(hours=1),
            end_at=now + timezone.timedelta(hours=1, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=False,
            total_price=Decimal("80.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        booking.services.set([self.service])
        walkin = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service_2,
            start_at=now + timezone.timedelta(hours=2),
            end_at=now + timezone.timedelta(hours=2, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=True,
            total_price=Decimal("120.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        walkin.services.set([self.service_2])

        response = self.client.get(
            reverse("appointment-list"),
            {"scope": "all_history", "entry_type": "walk_in"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["entry_type"], "walk_in")

        listed_ids = [appointment.id for appointment in response.context["appointments"]]
        self.assertEqual(listed_ids, [walkin.id])
        self.assertNotIn(booking.id, listed_ids)

    def test_appointment_list_upcoming_7_days_bookings_only(self):
        now = timezone.now().replace(second=0, microsecond=0)
        booking_near = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service,
            start_at=now + timezone.timedelta(days=2),
            end_at=now + timezone.timedelta(days=2, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=False,
            total_price=Decimal("80.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        booking_near.services.set([self.service])
        walkin_near = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service_2,
            start_at=now + timezone.timedelta(days=1),
            end_at=now + timezone.timedelta(days=1, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=True,
            total_price=Decimal("120.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        walkin_near.services.set([self.service_2])
        booking_far = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service,
            start_at=now + timezone.timedelta(days=9),
            end_at=now + timezone.timedelta(days=9, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=False,
            total_price=Decimal("80.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        booking_far.services.set([self.service])

        response = self.client.get(reverse("appointment-list"), {"scope": "upcoming_7_days"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["scope"], "upcoming_7_days")
        self.assertEqual(response.context["entry_type"], "booking")

        listed_ids = [appointment.id for appointment in response.context["appointments"]]
        self.assertEqual(listed_ids, [booking_near.id])
        self.assertNotIn(walkin_near.id, listed_ids)
        self.assertNotIn(booking_far.id, listed_ids)

    def test_appointment_list_upcoming_month_orders_ascending(self):
        now = timezone.now().replace(second=0, microsecond=0)
        booking_soon = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service,
            start_at=now + timezone.timedelta(days=4),
            end_at=now + timezone.timedelta(days=4, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=False,
            total_price=Decimal("80.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        booking_soon.services.set([self.service])
        booking_later = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service_2,
            start_at=now + timezone.timedelta(days=22),
            end_at=now + timezone.timedelta(days=22, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=False,
            total_price=Decimal("120.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        booking_later.services.set([self.service_2])
        booking_outside_window = Appointment.objects.create(
            client=self.client_profile,
            barber=self.barber,
            service=self.service,
            start_at=now + timezone.timedelta(days=40),
            end_at=now + timezone.timedelta(days=40, minutes=30),
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=False,
            total_price=Decimal("80.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        booking_outside_window.services.set([self.service])

        response = self.client.get(reverse("appointment-list"), {"scope": "upcoming_month"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["scope"], "upcoming_month")
        self.assertEqual(response.context["entry_type"], "booking")

        listed_ids = [appointment.id for appointment in response.context["appointments"]]
        self.assertEqual(listed_ids, [booking_soon.id, booking_later.id])
        self.assertNotIn(booking_outside_window.id, listed_ids)
