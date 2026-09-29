from django.contrib import admin
from .models import (
    Empleado, AuditoriaEmpleado, Departamento, Puesto,
    EmpleadoPuesto, Salario, Asistencia, Permiso, Evaluacion,
)


class EmpleadoAdmin(admin.ModelAdmin):
    """
    Configuración del modelo Empleado en el panel de administración.
    Incluye campos de búsqueda, filtros y captura automática de auditoría al guardar.
    """
    list_display = ('nombre_empleado', 'estado_empleado')
    list_filter = ('estado_empleado',)
    search_fields = ('nombre_empleado',)

    def save_model(self, request, obj, form, change):
        """
        Sobrescribe el método save_model para interceptar los cambios y registrar
        automáticamente la auditoría en la base de datos con el usuario responsable.
        """
        # Caso 1: Creación de un nuevo empleado (change es False)
        if not change:
            # Guarda primero el nuevo registro en la base de datos
            super().save_model(request, obj, form, change)

            # Crea el registro de auditoría con la acción CREACION
            AuditoriaEmpleado.objects.create(
                usuario_nombre=request.user.username,
                tabla='Empleado',
                afectado=obj.nombre_empleado,
                accion_realizada='CREACION',
                detalles_cambio="Registro de empleado creado."
            )
            return

        # Caso 2: Modificación de un empleado existente (change es True)
        cambios = []
        accion = 'EDICION'

        # Verifica si cambió el nombre completo
        if 'nombre_empleado' in form.changed_data:
            nombre_anterior = form.initial.get('nombre_empleado')
            cambios.append(f"Nombre modificado de '{nombre_anterior}' a '{obj.nombre_empleado}'")

        # Verifica si cambió el estado laboral (activo / inactivo)
        if 'estado_empleado' in form.changed_data:
            if not obj.estado_empleado:
                accion = 'DESACTIVACION'
                cambios.append("Empleado desactivado de la empresa (estado: Inactivo)")
            else:
                cambios.append("Empleado reactivado en la empresa (estado: Activo)")

        # Guarda los cambios del empleado en la base de datos
        super().save_model(request, obj, form, change)

        # Si hubo al menos un campo modificado, registra la auditoría
        if cambios:
            detalles_texto = "; ".join(cambios)
            AuditoriaEmpleado.objects.create(
                usuario_nombre=request.user.username,
                tabla='Empleado',
                afectado=obj.nombre_empleado,
                accion_realizada=accion,
                detalles_cambio=detalles_texto
            )


class AuditoriaEmpleadoAdmin(admin.ModelAdmin):
    """
    Panel de visualización del historial de auditoría de empleados.
    Garantiza la inmutabilidad de los registros para cumplir con buenas prácticas contables y de RRHH.
    """
    list_display = (
        'usuario_nombre',
        'tabla',
        'afectado',
        'accion_realizada',
        'detalles_cambio',
        'fecha_modificacion'
    )
    list_filter = ('accion_realizada', 'fecha_modificacion')
    search_fields = ('usuario_nombre', 'afectado', 'detalles_cambio')
    readonly_fields = (
        'usuario_nombre',
        'tabla',
        'afectado',
        'accion_realizada',
        'detalles_cambio',
        'fecha_modificacion'
    )

    def has_add_permission(self, request):
        """Evita la creación manual de registros de auditoría."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Evita la eliminación de registros para preservar el historial de auditoría."""
        return False


# Registrar los modelos con sus clases de administración correspondientes
admin.site.register(Empleado, EmpleadoAdmin)
admin.site.register(AuditoriaEmpleado, AuditoriaEmpleadoAdmin)
admin.site.register(Departamento)
admin.site.register(Puesto)
admin.site.register(EmpleadoPuesto)
admin.site.register(Salario)
admin.site.register(Asistencia)
admin.site.register(Permiso)
admin.site.register(Evaluacion)

# Personalización de títulos del Panel de Administración
admin.site.site_header = "Panel de Control - Gestión de Recursos Humanos"
admin.site.site_title = "Gestión de Empleados"
admin.site.index_title = "Administración de Empleados y Auditoría"