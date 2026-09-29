from django.contrib import admin
from django.urls import path
from rrhh.views import listar_empleados, login_view, logout_view, dashboard_jefe, dashboard_empleado

urlpatterns = [
    path('admin/', admin.site.urls),
    path('empleados/', listar_empleados, name='listar_empleados'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('jefe/', dashboard_jefe, name='dashboard_jefe'),
    path('empleado/', dashboard_empleado, name='dashboard_empleado'),
]
