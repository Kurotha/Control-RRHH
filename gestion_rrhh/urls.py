from django.contrib import admin
from django.urls import path
from rrhh.views import listar_empleados

urlpatterns = [
    path('admin/', admin.site.urls),
    path('empleados/', listar_empleados, name='listar_empleados'),
    path('', listar_empleados, name='home'),
]
