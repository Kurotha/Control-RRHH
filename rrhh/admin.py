from django.contrib import admin
from .models import Empleado, AuditoriaEmpleado

# Registrar los modelos para que sean accesibles desde la interfaz de administración
admin.site.register(Empleado)
admin.site.register(AuditoriaEmpleado)

