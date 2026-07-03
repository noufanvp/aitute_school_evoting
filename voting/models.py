import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.hashers import make_password
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify


class Election(models.Model):
	STATUS_DRAFT = "draft"
	STATUS_OPEN = "open"
	STATUS_CLOSED = "closed"
	STATUS_CHOICES = (
		(STATUS_DRAFT, "Draft"),
		(STATUS_OPEN, "Open"),
		(STATUS_CLOSED, "Closed"),
	)

	title = models.CharField(max_length=200)
	school_name = models.CharField(max_length=200)
	school_slug = models.SlugField(
		max_length=100,
		blank=True,
		db_index=True,
		help_text="Auto-generated from school name. Used in kiosk URL: /vote/<slug>/",
	)
	logo = models.ImageField(
		upload_to="elections/logos/",
		blank=True,
		help_text="Optional school logo shown in the kiosk header.",
	)
	status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
	starts_at = models.DateTimeField(null=True, blank=True)
	ends_at = models.DateTimeField(null=True, blank=True)
	results_published = models.BooleanField(default=False)
	manual_override_password_hash = models.CharField(
		max_length=256,
		blank=True,
		help_text="Hashed password used for kiosk manual override at this school.",
	)
	manual_override_password_plain = models.CharField(
		max_length=256,
		blank=True,
		help_text="Plain text password used for kiosk manual override at this school.",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ("-created_at",)

	def __str__(self):
		return self.title

	def save(self, *args, **kwargs):
		"""Auto-populate school_slug from school_name if not set."""
		if not self.school_slug and self.school_name:
			base_slug = slugify(self.school_name)
			self.school_slug = base_slug or "school"
		super().save(*args, **kwargs)

	def is_active(self):
		now = timezone.now()
		if self.status != self.STATUS_OPEN:
			return False
		if self.starts_at and now < self.starts_at:
			return False
		if self.ends_at and now > self.ends_at:
			return False
		return True

	def set_manual_override_password(self, raw_password):
		if raw_password:
			self.manual_override_password_hash = make_password(raw_password)
			self.manual_override_password_plain = raw_password

	def clear_manual_override_password(self):
		self.manual_override_password_hash = ""
		self.manual_override_password_plain = ""

	def check_manual_override_password(self, raw_password):
		if not self.manual_override_password_hash:
			return False
		return check_password(raw_password, self.manual_override_password_hash)

	@property
	def logo_url(self):
		if not self.logo:
			return ""
		if self.logo.name.startswith("voting/"):
			return f"/static/{self.logo.name}"
		try:
			return self.logo.url
		except ValueError:
			return ""


class Position(models.Model):
	election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="positions")
	name = models.CharField(max_length=140)
	icon = models.CharField(max_length=16, blank=True)
	order = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ("order", "id")
		constraints = [
			models.UniqueConstraint(fields=("election", "name"), name="uniq_position_name_per_election"),
			models.UniqueConstraint(fields=("election", "order"), name="uniq_position_order_per_election"),
		]

	def __str__(self):
		return f"{self.election.title}: {self.name}"


class Candidate(models.Model):
	position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name="candidates")
	name = models.CharField(max_length=140)
	class_name = models.CharField(max_length=80, blank=True)
	motto = models.CharField(max_length=255, blank=True)
	photo = models.ImageField(upload_to="candidates/photos", blank=True, null=True)
	symbol = models.ImageField(upload_to="candidates/symbols", blank=True, null=True)
	symbol_name = models.CharField(max_length=50, blank=True, help_text="Text to display alongside the symbol (e.g. 'Globe')")
	order = models.PositiveIntegerField(default=0)
	is_nota = models.BooleanField(default=False)

	class Meta:
		ordering = ("order", "id")
		constraints = [
			models.UniqueConstraint(fields=("position", "order"), name="uniq_candidate_order_per_position"),
		]

	def __str__(self):
		return f"{self.position.name}: {self.name}"


class Ballot(models.Model):
	STATUS_STARTED = "started"
	STATUS_SUBMITTED = "submitted"
	STATUS_CANCELLED = "cancelled"
	STATUS_CHOICES = (
		(STATUS_STARTED, "Started"),
		(STATUS_SUBMITTED, "Submitted"),
		(STATUS_CANCELLED, "Cancelled"),
	)

	election = models.ForeignKey(Election, on_delete=models.PROTECT, related_name="ballots")
	started_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="started_ballots",
	)
	session_token = models.CharField(max_length=64, unique=True, db_index=True)
	receipt_token = models.CharField(max_length=12, unique=True, db_index=True)
	status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_STARTED)
	created_at = models.DateTimeField(auto_now_add=True)
	submitted_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ("-created_at",)

	def __str__(self):
		return f"Ballot {self.receipt_token} ({self.status})"

	@staticmethod
	def generate_session_token():
		return secrets.token_urlsafe(32)

	@staticmethod
	def generate_receipt_token():
		return secrets.token_hex(4).upper()


class Vote(models.Model):
	ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE, related_name="votes")
	position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="votes")
	candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT, related_name="votes")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=("ballot", "position"), name="uniq_vote_per_position_per_ballot"),
		]
		indexes = [
			models.Index(fields=("ballot", "position")),
			models.Index(fields=("position", "candidate")),
		]

	def __str__(self):
		return f"{self.ballot.receipt_token}: {self.position.name} -> {self.candidate.name}"


class VoterRegistration(models.Model):
	election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="voter_registrations")
	student_id_hash = models.CharField(max_length=64, db_index=True)
	voted_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=("election", "student_id_hash"), name="uniq_voter_registration_per_election")
		]

	def __str__(self):
		return f"Voter hash {self.student_id_hash[:8]}... in {self.election.title}"


# ── User Profile (lock / unlock invigilators) ─────────────────────────────
class UserProfile(models.Model):
	"""One-to-one extension of the built-in User, adds invigilator lock state."""

	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="profile",
	)
	is_locked = models.BooleanField(
		default=False,
		help_text="When True, this user cannot start or submit ballots.",
	)
	locked_at = models.DateTimeField(null=True, blank=True)
	locked_reason = models.CharField(max_length=255, blank=True)
	school_name = models.CharField(
		max_length=200,
		blank=True,
		help_text="The school this invigilator is assigned to (blank for superusers/all schools).",
	)
	school_slug = models.SlugField(
		max_length=100,
		blank=True,
		help_text="The school slug this invigilator is assigned to.",
	)
	exclude_votes = models.BooleanField(
		default=False,
		help_text="Exclude votes cast during sessions started by this invigilator from final results counting.",
	)
	plain_password = models.CharField(
		max_length=256,
		blank=True,
		help_text="Plain text password of the invigilator account.",
	)
	role = models.CharField(
		max_length=20,
		choices=(("invigilator", "Invigilator"), ("teacher", "Teacher"), ("kiosk", "Kiosk")),
		default="invigilator",
		help_text="The role of this user (invigilator, teacher, or kiosk).",
	)
	current_device_id = models.CharField(
		max_length=64,
		blank=True,
		help_text="Tracks the unique active device ID for this kiosk/user to prevent concurrent sessions.",
	)

	class Meta:
		verbose_name = "User Profile"
		verbose_name_plural = "User Profiles"

	def __str__(self):
		status = "🔒 LOCKED" if self.is_locked else "✅ Active"
		return f"{self.user.username} [{status}]"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def _auto_create_user_profile(sender, instance, created, **kwargs):
	"""Automatically create a UserProfile whenever a new User is saved."""
	if created:
		UserProfile.objects.get_or_create(user=instance)


class KioskPresence(models.Model):
	election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="kiosk_presences")
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	last_seen_at = models.DateTimeField(auto_now=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=("election", "user"), name="uniq_kiosk_presence_per_election_user")
		]

	def __str__(self):
		return f"{self.user.username} on {self.election.title}"


class KioskSession(models.Model):
	"""
	Tracks an invigilator-pushed voting session assigned to a specific kiosk.
	The kiosk polls for a pending session; when found, it activates the voting flow.
	"""
	STATUS_PENDING = "pending"   # Invigilator created it, kiosk hasn't picked it up yet
	STATUS_ACTIVE  = "active"    # Kiosk has picked it up and voter is voting
	STATUS_DONE    = "done"      # Voter submitted their ballot
	STATUS_EXPIRED = "expired"   # Timed out before kiosk picked it up
	STATUS_CANCELLED = "cancelled"  # Invigilator cancelled

	STATUS_CHOICES = (
		(STATUS_PENDING, "Pending"),
		(STATUS_ACTIVE, "Active"),
		(STATUS_DONE, "Done"),
		(STATUS_EXPIRED, "Expired"),
		(STATUS_CANCELLED, "Cancelled"),
	)

	election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="kiosk_sessions")
	kiosk_id = models.CharField(max_length=64, db_index=True)
	student_id_hash = models.CharField(max_length=64)
	ballot = models.OneToOneField(
		"Ballot", null=True, blank=True, on_delete=models.SET_NULL, related_name="kiosk_session"
	)
	status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
	activated_by = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="activated_kiosk_sessions"
	)
	created_at = models.DateTimeField(auto_now_add=True)
	activated_at = models.DateTimeField(null=True, blank=True)
	expires_at = models.DateTimeField()

	class Meta:
		ordering = ("-created_at",)

	def __str__(self):
		return f"KioskSession [{self.status}] kiosk={self.kiosk_id[:8]} election={self.election.title}"

	def is_expired(self):
		return timezone.now() > self.expires_at


class Student(models.Model):
	"""
	Voter roster for an election — onboarded by teachers/admin via UI or Excel import.
	Stores name, class, division. Student identity is used to derive a voting hash
	(student_id_hash) via the same scheme used in VoterRegistration.
	"""
	election = models.ForeignKey(
		Election, on_delete=models.CASCADE, related_name="students"
	)
	name = models.CharField(max_length=200)
	student_class = models.CharField(max_length=20, help_text="e.g. 10, 11, 12")
	division = models.CharField(max_length=10, blank=True, help_text="e.g. A, B, C")
	# Optional stable student identifier (admission no / roll no)
	student_id = models.CharField(
		max_length=100,
		blank=True,
		help_text="Admission/Roll number used to uniquely identify the student for voting.",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("student_class", "division", "name")
		constraints = [
			models.UniqueConstraint(
				fields=("election", "student_id"),
				condition=models.Q(student_id__gt=""),
				name="uniq_student_id_per_election",
			)
		]

	def __str__(self):
		return f"{self.name} | Class {self.student_class}{self.division} | {self.election.school_name}"

