from django.urls import path

from . import portal_views

urlpatterns = [
    path("", portal_views.portal_home, name="portal-home"),
    # Elections
    path("elections/new/", portal_views.portal_election_create, name="portal-election-create"),
    path("elections/<int:election_id>/edit/", portal_views.portal_election_edit, name="portal-election-edit"),
    path("elections/<int:election_id>/delete/", portal_views.portal_election_delete, name="portal-election-delete"),
    # Positions
    path("elections/<int:election_id>/positions/", portal_views.portal_positions, name="portal-positions"),
    path("elections/<int:election_id>/positions/new/", portal_views.portal_position_create, name="portal-position-create"),
    path("positions/<int:position_id>/edit/", portal_views.portal_position_edit, name="portal-position-edit"),
    path("positions/<int:position_id>/delete/", portal_views.portal_position_delete, name="portal-position-delete"),
    path("positions/reorder/", portal_views.portal_positions_reorder, name="portal-positions-reorder"),
    # Candidates
    path("positions/<int:position_id>/candidates/new/", portal_views.portal_candidate_create, name="portal-candidate-create"),
    path("candidates/<int:candidate_id>/edit/", portal_views.portal_candidate_edit, name="portal-candidate-edit"),
    path("candidates/<int:candidate_id>/delete/", portal_views.portal_candidate_delete, name="portal-candidate-delete"),
    # Invigilators
    path("invigilators/", portal_views.portal_invigilators, name="portal-invigilators"),
    path("invigilators/new/", portal_views.portal_invigilator_create, name="portal-invigilator-create"),
    path("invigilators/<int:user_id>/edit/", portal_views.portal_invigilator_edit, name="portal-invigilator-edit"),
    path("invigilators/<int:user_id>/delete/", portal_views.portal_invigilator_delete, name="portal-invigilator-delete"),
    # Teachers
    path("teachers/", portal_views.portal_teachers, name="portal-teachers"),
    path("teachers/new/", portal_views.portal_teacher_create, name="portal-teacher-create"),
    path("teachers/<int:user_id>/edit/", portal_views.portal_teacher_edit, name="portal-teacher-edit"),
    path("teachers/<int:user_id>/delete/", portal_views.portal_teacher_delete, name="portal-teacher-delete"),
    # Kiosk Users
    path("kiosks/", portal_views.portal_kiosks, name="portal-kiosks"),
    path("kiosks/new/", portal_views.portal_kiosk_create, name="portal-kiosk-create"),
    path("kiosks/<int:user_id>/edit/", portal_views.portal_kiosk_edit, name="portal-kiosk-edit"),
    path("kiosks/<int:user_id>/delete/", portal_views.portal_kiosk_delete, name="portal-kiosk-delete"),
    # Students
    path("elections/<int:election_id>/students/", portal_views.portal_students, name="portal-students"),
    path("elections/<int:election_id>/students/new/", portal_views.portal_student_create, name="portal-student-create"),
    path("students/<int:student_id>/edit/", portal_views.portal_student_edit, name="portal-student-edit"),
    path("students/<int:student_id>/delete/", portal_views.portal_student_delete, name="portal-student-delete"),
    path("elections/<int:election_id>/students/import/", portal_views.portal_student_import, name="portal-student-import"),
    path("elections/<int:election_id>/students/import/template/", portal_views.portal_student_import_template, name="portal-student-import-template"),
    path("elections/<int:election_id>/students/api/", portal_views.portal_students_api, name="portal-students-api"),
    # AJAX helpers
    path("elections/<int:election_id>/status/", portal_views.portal_election_status, name="portal-election-status"),
    path("kiosks/active/", portal_views.portal_active_kiosks, name="portal-active-kiosks"),
    path("elections/<int:election_id>/turnout/", portal_views.portal_election_turnout, name="portal-election-turnout"),
]
