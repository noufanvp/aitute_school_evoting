import json
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Ballot
from .models import Candidate
from .models import Election
from .models import Position
from .models import Vote
from .models import KioskPresence


class VotingFlowTests(TestCase):
	def setUp(self):
		self.client = Client()
		self.user = get_user_model().objects.create_user(username="operator", password="StrongPass123!")
		self.user.profile.exclude_votes = True
		self.user.profile.save()

		self.election = Election.objects.create(
			title="Test Election",
			school_name="Test School",
			status=Election.STATUS_OPEN,
			starts_at=timezone.now(),
		)
		self.position = Position.objects.create(election=self.election, name="President", icon="👑", order=1)
		self.candidate_1 = Candidate.objects.create(position=self.position, name="A", class_name="10-A", order=1)
		self.candidate_2 = Candidate.objects.create(position=self.position, name="B", class_name="10-B", order=2)

		self.client.login(username="operator", password="StrongPass123!")

	def test_start_session(self):
		response = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json")
		self.assertEqual(response.status_code, 201)
		payload = response.json()
		self.assertIn("ballot_id", payload)

	def test_vote_validation_candidate_position_mismatch(self):
		second_position = Position.objects.create(election=self.election, name="Vice", icon="🌟", order=2)
		wrong_candidate = Candidate.objects.create(position=second_position, name="Wrong", class_name="9-A", order=1)

		start = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json").json()
		response = self.client.post(
			reverse("api-save-selection"),
			data={
				"ballot_id": start["ballot_id"],
				"position_id": self.position.id,
				"candidate_id": wrong_candidate.id,
			},
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN=start["session_token"],
		)
		self.assertEqual(response.status_code, 400)

	def test_duplicate_submit_prevention(self):
		start = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json").json()
		self.client.post(
			reverse("api-save-selection"),
			data={
				"ballot_id": start["ballot_id"],
				"position_id": self.position.id,
				"candidate_id": self.candidate_1.id,
			},
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN=start["session_token"],
		)

		first_submit = self.client.post(
			reverse("api-submit-ballot"),
			data={"ballot_id": start["ballot_id"]},
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN=start["session_token"],
		)
		second_submit = self.client.post(
			reverse("api-submit-ballot"),
			data={"ballot_id": start["ballot_id"]},
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN=start["session_token"],
		)

		self.assertEqual(first_submit.status_code, 200)
		self.assertEqual(second_submit.status_code, 403)

	def test_election_closed_behavior(self):
		self.election.status = Election.STATUS_CLOSED
		self.election.save(update_fields=["status"])
		response = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json")
		self.assertEqual(response.status_code, 400)

	def test_anonymous_ballot_storage(self):
		start = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json").json()
		self.client.post(
			reverse("api-save-selection"),
			data={
				"ballot_id": start["ballot_id"],
				"position_id": self.position.id,
				"candidate_id": self.candidate_2.id,
			},
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN=start["session_token"],
		)
		self.client.post(
			reverse("api-submit-ballot"),
			data={"ballot_id": start["ballot_id"]},
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN=start["session_token"],
		)

		ballot = Ballot.objects.get(id=start["ballot_id"])
		vote = Vote.objects.get(ballot=ballot, position=self.position)

		self.assertTrue(ballot.receipt_token)
		self.assertEqual(ballot.status, Ballot.STATUS_SUBMITTED)
		self.assertEqual(vote.candidate_id, self.candidate_2.id)
		self.assertNotIn("student", ballot.__dict__)

	def test_save_and_submit_require_valid_ballot_token(self):
		start = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json").json()
		
		# Save selection without token
		response = self.client.post(
			reverse("api-save-selection"),
			data={
				"ballot_id": start["ballot_id"],
				"position_id": self.position.id,
				"candidate_id": self.candidate_1.id,
			},
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.json()["detail"], "Invalid or expired ballot token.")

		# Save selection with invalid token
		response = self.client.post(
			reverse("api-save-selection"),
			data={
				"ballot_id": start["ballot_id"],
				"position_id": self.position.id,
				"candidate_id": self.candidate_1.id,
			},
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN="invalid-token-123",
		)
		self.assertEqual(response.status_code, 403)

		# Submit ballot without token
		response = self.client.post(
			reverse("api-submit-ballot"),
			data={"ballot_id": start["ballot_id"]},
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.json()["detail"], "Invalid or expired ballot token.")

		# Submit ballot with invalid token
		response = self.client.post(
			reverse("api-submit-ballot"),
			data={"ballot_id": start["ballot_id"]},
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN="invalid-token-123",
		)
		self.assertEqual(response.status_code, 403)


class InvigilatorSecurityTests(TestCase):
	def setUp(self):
		self.client = Client()
		self.superuser = get_user_model().objects.create_superuser(username="admin_user", password="SuperPassword123")
		
		# Create invigilators
		self.invigilator_a = get_user_model().objects.create_user(username="inv_a", password="InvPassword123")
		self.invigilator_a.profile.school_name = "School A"
		self.invigilator_a.profile.school_slug = "school-a"
		self.invigilator_a.profile.save()

		self.invigilator_b = get_user_model().objects.create_user(username="inv_b", password="InvPassword123")
		self.invigilator_b.profile.school_name = "School B"
		self.invigilator_b.profile.school_slug = "school-b"
		self.invigilator_b.profile.save()

		# Create elections for both schools
		self.election_a = Election.objects.create(
			title="Election A",
			school_name="School A",
			school_slug="school-a",
			status=Election.STATUS_OPEN,
			starts_at=timezone.now(),
		)
		self.election_b = Election.objects.create(
			title="Election B",
			school_name="School B",
			school_slug="school-b",
			status=Election.STATUS_OPEN,
			starts_at=timezone.now(),
		)

	def test_invigilator_kiosk_access_and_redirection(self):
		# Log in as inv_a
		self.client.login(username="inv_a", password="InvPassword123")
		
		# Try to access school-a kiosk -> should redirect to invigilator dashboard
		response = self.client.get(reverse("kiosk-school", kwargs={"school_slug": "school-a"}))
		self.assertRedirects(response, reverse("invigilator-dashboard"))

	def test_invigilator_api_start_session_enforcement(self):
		# Log in as inv_a
		self.client.login(username="inv_a", password="InvPassword123")

		# Start session without slug or with school-b slug -> should still create Ballot for school-a (election_a)
		response = self.client.post(
			reverse("api-start-session"),
			data='{"school_slug": "school-b", "student_id": "STUDENT_INVA_1"}',
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 201)
		payload = response.json()
		ballot = Ballot.objects.get(id=payload["ballot_id"])
		self.assertEqual(ballot.election, self.election_a)

	def test_superuser_global_access(self):
		# Log in as superuser
		self.client.login(username="admin_user", password="SuperPassword123")

		# Should access school-a directly without redirect
		response = self.client.get(reverse("kiosk-school", kwargs={"school_slug": "school-a"}))
		self.assertEqual(response.status_code, 200)

		# Should access school-b directly without redirect
		response = self.client.get(reverse("kiosk-school", kwargs={"school_slug": "school-b"}))
		self.assertEqual(response.status_code, 200)

	def test_exclude_votes_from_results(self):
		# Create an invigilator with exclude_votes = True
		test_inv = get_user_model().objects.create_user(username="test_inv", password="Password123")
		test_inv.profile.school_name = "School A"
		test_inv.profile.school_slug = "school-a"
		test_inv.profile.exclude_votes = True
		test_inv.profile.save()

		# Log in as test_inv
		self.client.login(username="test_inv", password="Password123")

		# Start a session
		response = self.client.post(
			reverse("api-start-session"),
			data='{}',
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 201)
		payload = response.json()
		ballot_id = payload["ballot_id"]
		session_token = payload["session_token"]

		# Create a position and candidate under self.election_a
		pos = Position.objects.create(election=self.election_a, name="President", icon="👑", order=1)
		cand = Candidate.objects.create(position=pos, name="Candidate A", order=1)

		# Save selection
		self.client.post(
			reverse("api-save-selection"),
			data={
				"ballot_id": ballot_id,
				"position_id": pos.id,
				"candidate_id": cand.id,
			},
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN=session_token,
		)

		# Submit ballot
		self.client.post(
			reverse("api-submit-ballot"),
			data={"ballot_id": ballot_id},
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN=session_token,
		)

		# Get results page
		# Log in as superuser to view results page
		self.client.login(username="admin_user", password="SuperPassword123")
		response = self.client.get(reverse("results", kwargs={"election_id": self.election_a.id}))
		self.assertEqual(response.status_code, 200)

		# Total submitted should be 0 because it's excluded
		self.assertEqual(response.context["total_submitted"], 0)


class ResultsQueryOptimizationTests(TestCase):
	def setUp(self):
		self.client = Client()
		self.superuser = get_user_model().objects.create_superuser(username="admin_user", password="SuperPassword123")
		self.election = Election.objects.create(
			title="Optimized Results Election",
			school_name="School X",
			school_slug="school-x",
			status=Election.STATUS_OPEN,
			starts_at=timezone.now(),
		)
		# 2 positions
		self.pos_pres = Position.objects.create(election=self.election, name="President", icon="👑", order=1)
		self.pos_vp = Position.objects.create(election=self.election, name="Vice President", icon="🌟", order=2)
		
		# Candidates for President
		self.cand_pres_1 = Candidate.objects.create(position=self.pos_pres, name="Pres A", order=1)
		self.cand_pres_2 = Candidate.objects.create(position=self.pos_pres, name="Pres B", order=2)
		
		# Candidates for Vice President
		self.cand_vp_1 = Candidate.objects.create(position=self.pos_vp, name="VP A", order=1)
		self.cand_vp_2 = Candidate.objects.create(position=self.pos_vp, name="VP B", order=2)

	def test_results_calculation_multiple_positions_and_votes(self):
		# Log in as superuser to view/submit
		self.client.login(username="admin_user", password="SuperPassword123")

		# Ballot 1: Pres A, VP A
		resp1 = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json")
		b1_id = resp1.json()["ballot_id"]
		t1 = resp1.json()["session_token"]
		self.client.post(reverse("api-save-selection"), data={"ballot_id": b1_id, "position_id": self.pos_pres.id, "candidate_id": self.cand_pres_1.id}, content_type="application/json", HTTP_X_BALLOT_TOKEN=t1)
		self.client.post(reverse("api-save-selection"), data={"ballot_id": b1_id, "position_id": self.pos_vp.id, "candidate_id": self.cand_vp_1.id}, content_type="application/json", HTTP_X_BALLOT_TOKEN=t1)
		self.client.post(reverse("api-submit-ballot"), data={"ballot_id": b1_id}, content_type="application/json", HTTP_X_BALLOT_TOKEN=t1)

		# Ballot 2: Pres A, VP B
		resp2 = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json")
		b2_id = resp2.json()["ballot_id"]
		t2 = resp2.json()["session_token"]
		self.client.post(reverse("api-save-selection"), data={"ballot_id": b2_id, "position_id": self.pos_pres.id, "candidate_id": self.cand_pres_1.id}, content_type="application/json", HTTP_X_BALLOT_TOKEN=t2)
		self.client.post(reverse("api-save-selection"), data={"ballot_id": b2_id, "position_id": self.pos_vp.id, "candidate_id": self.cand_vp_2.id}, content_type="application/json", HTTP_X_BALLOT_TOKEN=t2)
		self.client.post(reverse("api-submit-ballot"), data={"ballot_id": b2_id}, content_type="application/json", HTTP_X_BALLOT_TOKEN=t2)

		# Ballot 3: Pres B, VP A
		resp3 = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json")
		b3_id = resp3.json()["ballot_id"]
		t3 = resp3.json()["session_token"]
		self.client.post(reverse("api-save-selection"), data={"ballot_id": b3_id, "position_id": self.pos_pres.id, "candidate_id": self.cand_pres_2.id}, content_type="application/json", HTTP_X_BALLOT_TOKEN=t3)
		self.client.post(reverse("api-save-selection"), data={"ballot_id": b3_id, "position_id": self.pos_vp.id, "candidate_id": self.cand_vp_1.id}, content_type="application/json", HTTP_X_BALLOT_TOKEN=t3)
		self.client.post(reverse("api-submit-ballot"), data={"ballot_id": b3_id}, content_type="application/json", HTTP_X_BALLOT_TOKEN=t3)

		# Fetch results page
		response = self.client.get(reverse("results", kwargs={"election_id": self.election.id}))
		self.assertEqual(response.status_code, 200)

		# Verify total submitted
		self.assertEqual(response.context["total_submitted"], 3)

		# Verify positions data
		positions_data = response.context["positions"]
		self.assertEqual(len(positions_data), 2)

		# President stats: total_votes = 3, Pres A has 2 votes (66.7%), Pres B has 1 vote (33.3%)
		pres_data = positions_data[0]
		self.assertEqual(pres_data["name"], "President")
		self.assertEqual(pres_data["total_votes"], 3)
		
		# Pres A should be the first (sorted descending by votes)
		cands_pres = pres_data["candidates"]
		self.assertEqual(cands_pres[0]["name"], "Pres A")
		self.assertEqual(cands_pres[0]["votes"], 2)
		self.assertEqual(cands_pres[0]["pct"], 66.7)
		self.assertTrue(cands_pres[0]["is_winner"])

		self.assertEqual(cands_pres[1]["name"], "Pres B")
		self.assertEqual(cands_pres[1]["votes"], 1)
		self.assertEqual(cands_pres[1]["pct"], 33.3)
		self.assertFalse(cands_pres[1]["is_winner"])

		# Vice President stats: total_votes = 3, VP A has 2 votes (66.7%), VP B has 1 vote (33.3%)
		vp_data = positions_data[1]
		self.assertEqual(vp_data["name"], "Vice President")
		self.assertEqual(vp_data["total_votes"], 3)
		
		cands_vp = vp_data["candidates"]
		self.assertEqual(cands_vp[0]["name"], "VP A")
		self.assertEqual(cands_vp[0]["votes"], 2)
		self.assertEqual(cands_vp[0]["pct"], 66.7)
		self.assertTrue(cands_vp[0]["is_winner"])

		self.assertEqual(cands_vp[1]["name"], "VP B")
		self.assertEqual(cands_vp[1]["votes"], 1)
		self.assertEqual(cands_vp[1]["pct"], 33.3)
		self.assertFalse(cands_vp[1]["is_winner"])


class BallotVerificationTests(TestCase):
	def setUp(self):
		self.client = Client()
		self.election = Election.objects.create(
			title="Verification Election",
			school_name="School V",
			school_slug="school-v",
			status=Election.STATUS_OPEN,
			starts_at=timezone.now(),
		)
		# Create a submitted ballot
		self.ballot_submitted = Ballot.objects.create(
			election=self.election,
			status=Ballot.STATUS_SUBMITTED,
			receipt_token="valid-token-xyz-123",
			session_token=Ballot.generate_session_token(),
			submitted_at=timezone.now(),
		)
		# Create an active (unsubmitted) ballot
		self.ballot_active = Ballot.objects.create(
			election=self.election,
			status=Ballot.STATUS_STARTED,
			receipt_token="active-token-abc-789",
			session_token=Ballot.generate_session_token(),
		)

	def test_verify_page_loads_with_empty_state(self):
		response = self.client.get(reverse("verify-ballot"))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Verify Your Ballot")
		self.assertNotContains(response, "Ballot Counted & Verified")

	def test_verify_submitted_ballot_token(self):
		response = self.client.get(reverse("verify-ballot"), data={"token": "valid-token-xyz-123"})
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Ballot Counted & Verified")
		self.assertContains(response, "School V")
		self.assertContains(response, "Verification Election")

	def test_verify_invalid_token(self):
		response = self.client.get(reverse("verify-ballot"), data={"token": "nonexistent-token"})
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Verification Failed")
		self.assertContains(response, "Invalid or unsubmitted ballot receipt token.")

	def test_verify_active_but_unsubmitted_token(self):
		# Unsubmitted ballots should not show as verified
		response = self.client.get(reverse("verify-ballot"), data={"token": "active-token-abc-789"})
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Verification Failed")


class VoterRegistrationTests(TestCase):
	def setUp(self):
		self.client = Client()
		self.operator = get_user_model().objects.create_user(username="operator", password="StrongPass123!")
		self.election = Election.objects.create(
			title="Voter Registration Election",
			school_name="School V",
			status=Election.STATUS_OPEN,
			starts_at=timezone.now(),
		)
		self.client.login(username="operator", password="StrongPass123!")

		# Create a test operator whose votes are excluded
		self.test_operator = get_user_model().objects.create_user(username="test_operator", password="StrongPass123!")
		self.test_operator.profile.exclude_votes = True
		self.test_operator.profile.save()

	def test_start_session_requires_student_id_for_non_test_users(self):
		# Non-test user trying to start session without student_id
		response = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json")
		self.assertEqual(response.status_code, 400)
		self.assertIn("Student ID is required to start a voter session.", response.json()["detail"])

	def test_start_session_registers_student_id_hash(self):
		# Non-test user starting session with student_id
		response = self.client.post(
			reverse("api-start-session"),
			data='{"student_id": "ST1023"}',
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 201)
		payload = response.json()
		ballot_id = payload["ballot_id"]
		session_token = payload["session_token"]

		# Submit ballot to trigger voter registration
		submit_resp = self.client.post(
			reverse("api-submit-ballot"),
			data=json.dumps({"ballot_id": ballot_id}),
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN=session_token,
		)
		self.assertEqual(submit_resp.status_code, 200)
		
		# Assert VoterRegistration record exists
		from .models import VoterRegistration
		import hashlib
		expected_hash = hashlib.sha256(f"{self.election.id}:st1023".encode("utf-8")).hexdigest()
		self.assertTrue(VoterRegistration.objects.filter(election=self.election, student_id_hash=expected_hash).exists())

		# Double-voting check: try starting another session with same student ID
		response_dup = self.client.post(
			reverse("api-start-session"),
			data='{"student_id": "ST1023"}',
			content_type="application/json",
		)
		self.assertEqual(response_dup.status_code, 400)
		self.assertIn("This student has already voted in this election.", response_dup.json()["detail"])

	def test_test_users_bypass_turnout_checks(self):
		# Test operator logins
		self.client.login(username="test_operator", password="StrongPass123!")
		
		# Can start session without student_id
		response1 = self.client.post(reverse("api-start-session"), data="{}", content_type="application/json")
		self.assertEqual(response1.status_code, 201)

		# Can start multiple sessions with the same student ID
		response2 = self.client.post(
			reverse("api-start-session"),
			data='{"student_id": "ST_TEST_DUP"}',
			content_type="application/json",
		)
		self.assertEqual(response2.status_code, 201)

		response3 = self.client.post(
			reverse("api-start-session"),
			data='{"student_id": "ST_TEST_DUP"}',
			content_type="application/json",
		)
		self.assertEqual(response3.status_code, 201)

	def test_ballot_secrecy_and_anonymity(self):
		# Verify Ballot does not link to VoterRegistration
		response = self.client.post(
			reverse("api-start-session"),
			data='{"student_id": "ST5555"}',
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 201)
		ballot_id = response.json()["ballot_id"]

		ballot = Ballot.objects.get(id=ballot_id)
		
		# Assert ballot has no direct student reference fields
		for field in ballot._meta.fields:
			self.assertNotEqual(field.name, "student_id")
			self.assertNotEqual(field.name, "student_id_hash")
			self.assertNotEqual(field.name, "voter_registration")


class KioskPresenceAndTurnoutTests(TestCase):
	def setUp(self):
		self.client = Client()
		User = get_user_model()
		
		# Create Superuser
		self.superuser = User.objects.create_superuser(
			username="admin", password="password123"
		)
		
		# Create Operator/Invigilator
		self.operator = User.objects.create_user(
			username="operator1", password="password123"
		)
		self.operator_profile = self.operator.profile
		self.operator_profile.school_name = "Test School"
		self.operator_profile.school_slug = "test-school"
		self.operator_profile.save()
		
		# Create Election
		self.election = Election.objects.create(
			title="School President",
			school_name="Test School",
			school_slug="test-school",
			status=Election.STATUS_OPEN,
		)

	def test_api_kiosk_ping(self):
		self.client.force_login(self.operator)
		response = self.client.post(
			reverse("api-kiosk-ping"),
			data=json.dumps({"school_slug": "test-school"}),
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["status"], "ok")
		
		# Verify KioskPresence was created
		presence = KioskPresence.objects.get(election=self.election, user=self.operator)
		self.assertIsNotNone(presence.last_seen_at)

	def test_portal_active_kiosks(self):
		# Create a presence
		presence = KioskPresence.objects.create(
			election=self.election,
			user=self.operator,
			last_seen_at=timezone.now()
		)
		
		# Login as superuser to view active kiosks portal
		self.client.force_login(self.superuser)
		response = self.client.get(reverse("portal-active-kiosks"))
		self.assertEqual(response.status_code, 200)
		active_kiosks = response.json()["active_kiosks"]
		self.assertEqual(len(active_kiosks), 1)
		self.assertEqual(active_kiosks[0]["username"], "operator1")
		
		# Make presence stale by bypassing auto_now=True using update query
		KioskPresence.objects.filter(id=presence.id).update(
			last_seen_at=timezone.now() - timezone.timedelta(seconds=40)
		)
		
		response = self.client.get(reverse("portal-active-kiosks"))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json()["active_kiosks"]), 0)

	def test_portal_election_turnout(self):
		# Create submitted ballots with unique session/receipt tokens
		b1 = Ballot.objects.create(
			election=self.election,
			status=Ballot.STATUS_SUBMITTED,
			submitted_at=timezone.now(),
			session_token=Ballot.generate_session_token(),
			receipt_token=Ballot.generate_receipt_token(),
		)
		b2 = Ballot.objects.create(
			election=self.election,
			status=Ballot.STATUS_SUBMITTED,
			submitted_at=timezone.now(),
			session_token=Ballot.generate_session_token(),
			receipt_token=Ballot.generate_receipt_token(),
		)
		
		self.client.force_login(self.superuser)
		response = self.client.get(
			reverse("portal-election-turnout", kwargs={"election_id": self.election.id})
		)
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["total_votes"], 2)
		self.assertEqual(len(data["labels"]), 1)
		self.assertEqual(data["counts"][0], 2)


class InvigilatorKioskActivationTests(TestCase):
	def setUp(self):
		self.client = Client()
		User = get_user_model()
		
		# Create Superuser
		self.superuser = User.objects.create_superuser(
			username="admin", password="password123"
		)
		
		# Create Operator/Invigilator
		self.operator = User.objects.create_user(
			username="operator1", password="password123"
		)
		self.operator_profile = self.operator.profile
		self.operator_profile.school_name = "Test School"
		self.operator_profile.school_slug = "test-school"
		self.operator_profile.save()
		
		# Create Election
		self.election = Election.objects.create(
			title="School President",
			school_name="Test School",
			school_slug="test-school",
			status=Election.STATUS_OPEN,
		)

	def test_session_check_idle_by_default(self):
		self.client.force_login(self.operator)
		response = self.client.get(
			reverse("api-kiosk-session-check"),
			{"kiosk_id": "test-kiosk", "school_slug": "test-school"}
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["status"], "idle")

	def test_kiosk_activation_flow(self):
		self.client.force_login(self.operator)
		
		# 1. Activate session for a student on "test-kiosk"
		response = self.client.post(
			reverse("api-invigilator-activate-kiosk"),
			data=json.dumps({
				"student_id": "student123",
				"kiosk_id": "test-kiosk",
				"school_slug": "test-school"
			}),
			content_type="application/json"
		)
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["status"], "activated")
		session_id = data["session_id"]
		
		# 2. Check session from the kiosk side
		response = self.client.get(
			reverse("api-kiosk-session-check"),
			{"kiosk_id": "test-kiosk", "school_slug": "test-school"}
		)
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["status"], "session_ready")
		self.assertEqual(data["session_id"], session_id)
		
		# 3. Start voting session from the kiosk using the kiosk_session_id
		response = self.client.post(
			reverse("api-start-session"),
			data=json.dumps({
				"school_slug": "test-school",
				"kiosk_session_id": session_id,
				"student_id": "__invigilator_activated__"
			}),
			content_type="application/json"
		)
		self.assertEqual(response.status_code, 201)
		data = response.json()
		self.assertIn("ballot_id", data)
		self.assertIn("session_token", data)
		ballot_id = data["ballot_id"]
		session_token = data["session_token"]

		# Submit ballot to complete session and trigger voter registration
		submit_resp = self.client.post(
			reverse("api-submit-ballot"),
			data=json.dumps({"ballot_id": ballot_id}),
			content_type="application/json",
			HTTP_X_BALLOT_TOKEN=session_token,
		)
		self.assertEqual(submit_resp.status_code, 200)
		
		# 4. Try activation for same student again to check double voting prevention
		response = self.client.post(
			reverse("api-invigilator-activate-kiosk"),
			data=json.dumps({
				"student_id": "student123",
				"kiosk_id": "test-kiosk-2",
				"school_slug": "test-school"
			}),
			content_type="application/json"
		)
		# Should fail double-voting check since we marked voter registered on start session
		self.assertEqual(response.status_code, 400)
		self.assertIn("already voted", response.json()["detail"])

	def test_invigilator_dashboard_access(self):
		self.client.force_login(self.operator)
		response = self.client.get(reverse("invigilator-dashboard"))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "School President")


class UserRoleSeparationTests(TestCase):
	def setUp(self):
		self.client = Client()
		User = get_user_model()

		# Create Election
		self.election = Election.objects.create(
			title="Election X",
			school_name="Test School",
			school_slug="test-school",
			status=Election.STATUS_OPEN,
		)

		# Create Invigilator
		self.invigilator = User.objects.create_user(username="invigilator_user", password="password123")
		self.invigilator.profile.school_name = "Test School"
		self.invigilator.profile.school_slug = "test-school"
		self.invigilator.profile.role = "invigilator"
		self.invigilator.profile.save()

		# Create Teacher
		self.teacher = User.objects.create_user(username="teacher_user", password="password123")
		self.teacher.profile.school_name = "Test School"
		self.teacher.profile.school_slug = "test-school"
		self.teacher.profile.role = "teacher"
		self.teacher.profile.save()

	def test_teacher_can_add_student_but_not_activate_kiosk(self):
		self.client.force_login(self.teacher)

		# 1. Try to add a student -> Should succeed
		response = self.client.post(
			reverse("api-invigilator-student-create"),
			data={
				"name": "New Student",
				"student_class": "10",
				"division": "A",
				"student_id": "ST_T_1001",
			}
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["status"], "success")

		# 2. Try to activate a kiosk -> Should be forbidden
		response2 = self.client.post(
			reverse("api-invigilator-activate-kiosk"),
			data=json.dumps({
				"student_id": "ST_T_1001",
				"kiosk_id": "kiosk1",
				"school_slug": "test-school"
			}),
			content_type="application/json"
		)
		self.assertEqual(response2.status_code, 403)
		self.assertIn("Only invigilator accounts can activate kiosks", response2.json()["detail"])

	def test_teacher_can_import_students_from_csv(self):
		self.client.force_login(self.teacher)
		upload = SimpleUploadedFile(
			"students.csv",
			b"Name,Class,Division,Student ID\nStudent One,10,A,ST1001\nStudent Two,9,B,ST1002\n",
			content_type="text/csv",
		)

		response = self.client.post(
			reverse("api-invigilator-students-import"),
			data={"excel_file": upload},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["created"], 2)
		self.assertTrue(self.election.students.filter(student_id="ST1001").exists())
		self.assertTrue(self.election.students.filter(student_id="ST1002").exists())

	def test_teacher_can_download_blank_student_import_csv_template(self):
		self.client.force_login(self.teacher)

		response = self.client.get(
			reverse("api-invigilator-students-import-template"),
			data={"format": "csv"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
		self.assertEqual(response.content.decode("utf-8").strip(), "Name,Class,Division,Student ID")

	def test_invigilator_can_activate_kiosk_but_not_add_student(self):
		self.client.force_login(self.invigilator)

		# 1. Try to add a student -> Should be forbidden
		response = self.client.post(
			reverse("api-invigilator-student-create"),
			data={
				"name": "Another Student",
				"student_class": "10",
				"division": "A",
				"student_id": "ST_I_1001",
			}
		)
		self.assertEqual(response.status_code, 403)
		self.assertIn("Only teacher accounts can add students", response.json()["detail"])

		# Create a student manually for testing kiosk activation
		from .models import Student
		student = Student.objects.create(
			election=self.election,
			name="Manual Student",
			student_class="10",
			division="B",
			student_id="ST_M_1002"
		)

		# 2. Try to activate a kiosk -> Should succeed
		response2 = self.client.post(
			reverse("api-invigilator-activate-kiosk"),
			data=json.dumps({
				"student_id": "ST_M_1002",
				"kiosk_id": "kiosk1",
				"school_slug": "test-school"
			}),
			content_type="application/json"
		)
		self.assertEqual(response2.status_code, 200)
		self.assertEqual(response2.json()["status"], "activated")

	def test_api_invigilator_kiosks_permissions_and_filtering(self):
		# Create an active kiosk presence
		from .models import KioskPresence
		presence = KioskPresence.objects.create(
			election=self.election,
			user=self.invigilator,
			last_seen_at=timezone.now()
		)

		# Create a superuser presence (admin kiosk) - should be excluded
		User = get_user_model()
		superuser_user = User.objects.create_superuser(username="super_admin_kiosk", password="password123")
		KioskPresence.objects.create(
			election=self.election,
			user=superuser_user,
			last_seen_at=timezone.now()
		)

		# 1. Anonymous request should be redirected to login
		self.client.logout()
		response = self.client.get(reverse("api-invigilator-kiosks"))
		self.assertEqual(response.status_code, 302)

		# 2. Teacher should be able to view kiosks (only the non-admin kiosk)
		self.client.force_login(self.teacher)
		response2 = self.client.get(reverse("api-invigilator-kiosks"))
		self.assertEqual(response2.status_code, 200)
		self.assertEqual(len(response2.json()["active_kiosks"]), 1)
		self.assertEqual(response2.json()["active_kiosks"][0]["username"], "invigilator_user")

		# 3. Invigilator should be able to view kiosks
		self.client.force_login(self.invigilator)
		response3 = self.client.get(reverse("api-invigilator-kiosks"))
		self.assertEqual(response3.status_code, 200)
		self.assertEqual(len(response3.json()["active_kiosks"]), 1)

	def test_kiosk_user_crud_and_redirection(self):
		User = get_user_model()
		superuser = User.objects.create_superuser(username="admin_user", password="adminpassword")
		# 1. Superuser creates a kiosk user
		self.client.force_login(superuser)
		create_url = reverse("portal-kiosk-create")
		response = self.client.post(create_url, {
			"username": "kiosk_booth_x",
			"password": "kioskpassword123",
			"full_name": "Booth X",
			"school_select": "test school",
		})
		self.assertEqual(response.status_code, 302)

		# Verify database
		kiosk_user = User.objects.get(username="kiosk_booth_x")
		self.assertEqual(kiosk_user.profile.role, "kiosk")
		self.assertEqual(kiosk_user.profile.school_name, "test school")
		self.assertEqual(kiosk_user.profile.plain_password, "kioskpassword123")

		# 2. Access dashboard as kiosk user -> should redirect to kiosk voting page
		self.client.force_login(kiosk_user)
		dash_url = reverse("invigilator-dashboard")
		response = self.client.get(dash_url)
		self.assertEqual(response.status_code, 302)
		self.assertIn("/vote/test-school/", response.url)

	def test_api_session_status(self):
		from .models import KioskSession
		session = KioskSession.objects.create(
			election=self.election,
			kiosk_id="kiosk1",
			student_id_hash="dummyhash",
			status=KioskSession.STATUS_ACTIVE,
			expires_at=timezone.now() + timezone.timedelta(seconds=90)
		)
		
		# 1. Anonymous request should be redirected to login
		self.client.logout()
		url = reverse("api-session-status", args=[session.id])
		response = self.client.get(url)
		self.assertEqual(response.status_code, 302)

		# 2. Authenticated user should see the session status
		self.client.force_login(self.invigilator)
		response2 = self.client.get(url)
		self.assertEqual(response2.status_code, 200)
		self.assertEqual(response2.json()["status"], "active")

	def test_activate_student_without_id(self):
		self.client.force_login(self.invigilator)
		from .models import Student, KioskSession
		from voting import views
		student = Student.objects.create(
			election=self.election,
			name="No ID Student",
			student_class="10",
			division="B",
			student_id=""
		)
		
		# Try to activate the student using the fallback ID pattern
		response = self.client.post(
			reverse("api-invigilator-activate-kiosk"),
			data=json.dumps({
				"student_id": f"student_id__{student.id}",
				"kiosk_id": "kiosk1",
				"school_slug": "test-school"
			}),
			content_type="application/json"
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["status"], "activated")

		# Check that we can resolve this student from their session hash
		session_id = response.json()["session_id"]
		session = KioskSession.objects.get(id=session_id)
		resolved = views._student_for_hash(self.election, session.student_id_hash)
		self.assertIsNotNone(resolved)
		self.assertEqual(resolved["name"], "No ID Student")


class KioskConcurrencyAndDeviceLockTests(TestCase):
	def setUp(self):
		self.client = Client()
		User = get_user_model()
		
		# Create kiosk user
		self.kiosk_user = User.objects.create_user(
			username="kiosk1", password="password123"
		)
		self.kiosk_profile = self.kiosk_user.profile
		self.kiosk_profile.role = "kiosk"
		self.kiosk_profile.school_slug = "test-school"
		self.kiosk_profile.save()
		
		self.election = Election.objects.create(
			title="School President",
			school_name="Test School",
			school_slug="test-school",
			status=Election.STATUS_OPEN,
		)

	def test_device_id_cookie_and_lockout(self):
		# First login/visit should set a device ID cookie and save it to the profile
		self.client.force_login(self.kiosk_user)
		response = self.client.get(reverse("kiosk-school", kwargs={"school_slug": "test-school"}))
		self.assertEqual(response.status_code, 200)
		self.assertIn("kiosk_device_id", self.client.cookies)
		first_device_id = self.client.cookies["kiosk_device_id"].value
		
		# Profile current_device_id should be updated
		self.kiosk_profile.refresh_from_db()
		self.assertEqual(self.kiosk_profile.current_device_id, first_device_id)
		
		# Subsequent visits with the same cookie should be fine
		response = self.client.get(reverse("kiosk-school", kwargs={"school_slug": "test-school"}))
		self.assertEqual(response.status_code, 200)

		# Make a presence ping to simulate active kiosk
		KioskPresence.objects.update_or_create(
			election=self.election,
			user=self.kiosk_user,
			defaults={"last_seen_at": timezone.now()}
		)

		# Second device visits without a cookie (simulating a new laptop/browser)
		client2 = Client()
		client2.force_login(self.kiosk_user)
		response2 = client2.get(reverse("kiosk-school", kwargs={"school_slug": "test-school"}))
		self.assertEqual(response2.status_code, 200)
		# Should generate a new cookie and show takeover prompt since the first device is active
		self.assertIn("kiosk_device_id", client2.cookies)
		second_device_id = client2.cookies["kiosk_device_id"].value
		self.assertNotEqual(first_device_id, second_device_id)
		
		# In Django template context, show_takeover_prompt is passed as True
		self.assertTrue(response2.context["show_takeover_prompt"])

		# Simulating clicking "Sign Out Other Device" via API
		response_takeover = client2.post(reverse("api-kiosk-takeover"))
		self.assertEqual(response_takeover.status_code, 200)
		
		# profile current_device_id should now be the second device ID
		self.kiosk_profile.refresh_from_db()
		self.assertEqual(self.kiosk_profile.current_device_id, second_device_id)

		# Now the first client tries to ping or check session. Since it has first_device_id cookie, it should return 401
		self.client.cookies["kiosk_device_id"] = first_device_id
		response_ping = self.client.post(
			reverse("api-kiosk-ping"),
			data=json.dumps({"school_slug": "test-school"}),
			content_type="application/json"
		)
		self.assertEqual(response_ping.status_code, 401)
		self.assertEqual(response_ping.json()["status"], "logged_out")


class KioskTimeoutCustomizationTests(TestCase):
	def setUp(self):
		self.client = Client()
		User = get_user_model()
		from .models import Student, Election
		
		# Create Superuser
		self.superuser = User.objects.create_superuser(
			username="admin", password="password123"
		)
		
		# Create Invigilator
		self.invigilator = User.objects.create_user(
			username="invigilator1", password="password123"
		)
		self.invigilator_profile = self.invigilator.profile
		self.invigilator_profile.role = "invigilator"
		self.invigilator_profile.school_slug = "test-school"
		self.invigilator_profile.save()
		
		# Create Election
		self.election = Election.objects.create(
			title="School President",
			school_name="Test School",
			school_slug="test-school",
			status=Election.STATUS_OPEN,
			kiosk_timeout=120,  # 120 seconds instead of default 90
		)
		
		# Create Student
		self.student = Student.objects.create(
			election=self.election,
			name="John Doe",
			student_class="10",
			division="A",
			student_id="12345"
		)

	def test_kiosk_activation_respects_custom_timeout(self):
		self.client.force_login(self.invigilator)
		response = self.client.post(
			reverse("api-invigilator-activate-kiosk"),
			data=json.dumps({
				"student_id": "12345",
				"kiosk_id": "kiosk1",
				"school_slug": "test-school"
			}),
			content_type="application/json"
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["status"], "activated")
		
		# Verify KioskSession has correct expires_at
		session_id = response.json()["session_id"]
		from .models import KioskSession
		session = KioskSession.objects.get(id=session_id)
		duration = (session.expires_at - session.created_at).total_seconds()
		# Should be approximately 120 seconds
		self.assertAlmostEqual(duration, 120, delta=2)

	def test_serialized_election_contains_timeout(self):
		from .views import _serialize_election
		serialized = _serialize_election(self.election)
		self.assertEqual(serialized["kiosk_timeout"], 120)


