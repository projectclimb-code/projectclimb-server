from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from climber.views import ClientProxyView



schema_view = get_schema_view(
   openapi.Info(
      title="Climber API",
      default_version='v1',
      description="API for the Climber application",
      # terms_of_service="https://www.google.com/policies/terms/", # Optional
      # contact=openapi.Contact(email="contact@climber.local"),    # Optional
      # license=openapi.License(name="BSD License"),               # Optional
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')), # Django Allauth authentication URLs
    re_path(r'^(?P<path>client/.*)$', ClientProxyView.as_view()),
    path('', include('climber.urls')), # Include climber app URLs at the root
    # Swagger UI paths
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
