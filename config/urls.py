from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import index

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='index'),
    path('accounts/', include('accounts.urls')),
    path('leitner/', include('leitner.urls')),
    path('shop/', include('shop.urls')),
    path('scheduler/', include('scheduler.urls')),
    path('api/', include('core.urls')),
    path('api/', include(('scheduler.urls', 'scheduler_api'), namespace='scheduler_api')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
