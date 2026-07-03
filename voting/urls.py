from django.urls import path

from . import views


urlpatterns = [
    # School-specific kiosk (primary URL for multi-school support)
    path("vote/<slug:school_slug>/", views.kiosk_page, name="kiosk-school"),
    # Legacy fallback kiosk (serves any active election)
    path("", views.kiosk_page, name="kiosk"),
    path("results/<int:election_id>/", views.results_page, name="results"),
    path("verify/", views.verify_ballot_page, name="verify-ballot"),
    path("api/elections/current/", views.api_current_election, name="api-current-election"),
    path("api/kiosk/current-election/", views.api_current_election, name="api-kiosk-current-election"),
    path("api/kiosk/start-session/", views.api_start_session, name="api-start-session"),
    path("api/kiosk/save-selection/", views.api_save_selection, name="api-save-selection"),
    path("api/kiosk/submit/", views.api_submit_ballot, name="api-submit-ballot"),
    path("api/kiosk/ping/", views.api_kiosk_ping, name="api-kiosk-ping"),
    path("api/kiosk/session-check/", views.api_kiosk_session_check, name="api-kiosk-session-check"),
    path("api/kiosk/session-complete/", views.api_kiosk_session_complete, name="api-kiosk-session-complete"),
    path("api/invigilator/activate-kiosk/", views.api_invigilator_activate_kiosk, name="api-invigilator-activate-kiosk"),
    path("api/elections/<int:election_id>/publish/", views.api_publish_results, name="api-publish-results"),
    path("api/admin/users/", views.api_list_invigilators, name="api-list-invigilators"),
    path("api/admin/users/<int:user_id>/lock/", views.api_toggle_user_lock, name="api-toggle-user-lock"),
    path("invigilator/", views.invigilator_dashboard, name="invigilator-dashboard"),
    path("api/invigilator/kiosks/", views.api_invigilator_kiosks, name="api-invigilator-kiosks"),
    path("api/invigilator/students/", views.api_invigilator_students, name="api-invigilator-students"),
    path("api/invigilator/students/create/", views.api_invigilator_student_create, name="api-invigilator-student-create"),
    path("api/invigilator/students/import/", views.api_invigilator_students_import, name="api-invigilator-students-import"),
    path("api/invigilator/students/import/template/", views.api_invigilator_students_import_template, name="api-invigilator-students-import-template"),
    path("api/session/<int:session_id>/status/", views.api_session_status, name="api-session-status"),
]
