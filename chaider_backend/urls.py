from django.contrib import admin
from django.urls import path, include
from api import views as views_api
from graphs import views as views_graphs
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static  import static

# Creating Router Object
router = DefaultRouter()

router.register('chaidercsv', views_api.CSVFileModelViewset, basename='chaidercsv')
router.register('visualisation', views_api.CSVFileVariableModelViewset, basename='visualisation')
router.register('graphs', views_graphs.GraphDataModelViewset, basename='graphs')
router.register('users', views_api.UserViewSet, basename='users')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(router.urls)),
    path('auth/', views_api.CustomObtainAuthToken.as_view()),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
