from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.http import FileResponse, HttpResponseNotFound
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from ingestion.views import (IngestionBatchViewSet, EmissionsRecordViewSet,
                             UploadView, dashboard_stats, health_check)
import os

router = DefaultRouter()
router.register(r'batches', IngestionBatchViewSet, basename='batch')
router.register(r'records', EmissionsRecordViewSet, basename='record')


def frontend_index(request):
    index_path = settings.FRONTEND_BUILD / 'index.html'
    if index_path.exists():
        return FileResponse(open(index_path, 'rb'), content_type='text/html')
    return HttpResponseNotFound("Frontend not built. Run: cd frontend && npm run build")


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/upload/', UploadView.as_view(), name='upload'),
    path('api/dashboard/', dashboard_stats, name='dashboard'),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('health/', health_check, name='health'),
    # Catch-all: serve React for any non-API route
    re_path(r'^(?!api/|admin/|health/).*$', frontend_index),
]
