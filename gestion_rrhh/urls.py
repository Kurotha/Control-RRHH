from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from rrhh.views import (
    listar_empleados, login_view, logout_view, dashboard_jefe,
    dashboard_empleado, dashboard_rrhh, exportar_nomina_excel,
)

urlpatterns = [
    path('', RedirectView.as_view(url='login/', permanent=False), name='index'),
    path('admin/', admin.site.urls),
    path('empleados/', listar_empleados, name='listar_empleados'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('jefe/', dashboard_jefe, name='dashboard_jefe'),
    path('rrhh/', dashboard_rrhh, name='dashboard_rrhh'),
    path('empleado/', dashboard_empleado, name='dashboard_empleado'),
    path('exportar-nomina/', exportar_nomina_excel, name='exportar_nomina'),
]
