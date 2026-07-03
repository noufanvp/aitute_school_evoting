from django.contrib import admin
from django.utils import timezone

from .models import Ballot
from .models import Candidate
from .models import Election
from .models import Position
from .models import UserProfile
from .models import Vote


class CandidateInline(admin.TabularInline):
	model = Candidate
	extra = 0
	fields = ("order", "name", "class_name", "motto", "photo", "symbol", "is_nota")
	ordering = ("order", "id")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
	list_display = ("name", "election", "order")
	list_filter = ("election",)
	search_fields = ("name", "election__title")
	ordering = ("election", "order")
	inlines = (CandidateInline,)


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
	list_display = ("title", "school_name", "school_slug", "status", "results_published", "starts_at", "ends_at")
	list_filter = ("status", "results_published")
	search_fields = ("title", "school_name", "school_slug")
	list_editable = ("results_published",)
	readonly_fields = ("school_slug",)  # managed by portal; shown read-only here
	actions = ["publish_results", "unpublish_results"]
	fieldsets = (
		("School", {"fields": ("school_name", "school_slug", "logo")}),
		("Election", {"fields": ("title", "status", "starts_at", "ends_at")}),
		("Results", {"fields": ("results_published",)}),
	)

	@admin.action(description="✅ Publish results for selected elections")
	def publish_results(self, request, queryset):
		updated = queryset.update(results_published=True)
		self.message_user(request, f"{updated} election(s) results published successfully.")

	@admin.action(description="🔒 Unpublish results for selected elections")
	def unpublish_results(self, request, queryset):
		updated = queryset.update(results_published=False)
		self.message_user(request, f"{updated} election(s) results unpublished.")


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
	list_display = ("name", "position", "class_name", "symbol", "order", "is_nota")
	list_filter = ("position__election", "position")
	search_fields = ("name", "position__name")
	ordering = ("position", "order")


class VoteInline(admin.TabularInline):
	model = Vote
	extra = 0
	fields = ("position", "candidate", "created_at")
	readonly_fields = ("position", "candidate", "created_at")
	can_delete = False


@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):
	list_display = ("receipt_token", "election", "status", "created_at", "submitted_at")
	list_filter = ("election", "status")
	search_fields = ("receipt_token", "session_token")
	readonly_fields = (
		"election",
		"started_by",
		"session_token",
		"receipt_token",
		"status",
		"created_at",
		"submitted_at",
	)
	inlines = (VoteInline,)

	def has_add_permission(self, request):
		return False


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
	list_display = ("ballot", "position", "candidate", "created_at")
	readonly_fields = ("ballot", "position", "candidate", "created_at")
	list_filter = ("position__election", "position")

	def has_add_permission(self, request):
		return False


# ── User Profile / Lock Management ───────────────────────────────────────
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "is_locked", "locked_reason", "locked_at")
	list_filter = ("is_locked",)
	search_fields = ("user__username", "user__first_name", "user__last_name", "locked_reason")
	readonly_fields = ("user", "locked_at")
	actions = ["lock_users", "unlock_users"]

	@admin.action(description="🔒 Lock selected invigilators (block voting)")
	def lock_users(self, request, queryset):
		# Protect superusers
		safe = queryset.filter(user__is_superuser=False)
		count = safe.update(
			is_locked=True,
			locked_at=timezone.now(),
			locked_reason="Locked by admin action",
		)
		self.message_user(request, f"🔒 {count} user(s) locked — they can no longer start or submit ballots.")

	@admin.action(description="✅ Unlock selected invigilators (restore voting)")
	def unlock_users(self, request, queryset):
		count = queryset.update(is_locked=False, locked_at=None, locked_reason="")
		self.message_user(request, f"✅ {count} user(s) unlocked — they can vote again.")

	def has_add_permission(self, request):
		return False  # profiles are created automatically
