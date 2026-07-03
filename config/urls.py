from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve
from voting import views as voting_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', voting_views.logout_view, name='logout'),
    path('portal/', include('voting.portal_urls')),
    path('', include('voting.urls')),
]

# Serve uploaded media files (works in both development and production)
# Note: In production on Render, the filesystem is ephemeral unless a persistent disk volume is attached.
# However, this pattern allows files uploaded via the admin/portal panels to be served correctly while the service is running.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

