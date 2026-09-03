from django.contrib import admin
from .models import Empleado, AuditoriaEmpleado


class AuditoriaEmpleadoInline(admin.TabularInline):
    """
    Permite visualizar el historial de auditoría directamente en la ficha
    de edición del empleado en Django Admin.
    """
    model = AuditoriaEmpleado
    extra = 0
    can_delete = False
    verbose_name = "Auditoría de Empleado"
    verbose_name_plural = "Historial de Auditorías de este Empleado"
    readonly_fields = (
        'accion_realizada',
        'detalles_cambio',
        'usuario_modificador',
        'fecha_modificacion'
    )

    def has_add_permission(self, request, obj=None):
        """El historial es solo lectura, no se permite añadir manualmente."""
        return False


class EmpleadoAdmin(admin.ModelAdmin):
    """
    Configuración del modelo Empleado en el panel de administración.
    Incluye campos de búsqueda, filtros y captura automática de auditoría al guardar.
    """
    list_display = ('nombre_completo', 'puesto', 'salario', 'estado_laboral')
    list_filter = ('estado_laboral', 'puesto')
    search_fields = ('nombre_completo', 'puesto')
    inlines = [AuditoriaEmpleadoInline]

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
                empleado=obj,
                usuario_modificador=request.user,
                accion_realizada='CREACION',
                detalles_cambio=f"Registro creado con puesto '{obj.puesto}' y salario ${obj.salario} USD."
            )
            return

        # Caso 2: Modificación de un empleado existente (change es True)
        cambios = []
        accion = 'EDICION'

        # Verifica si cambió el salario
        if 'salario' in form.changed_data:
            salario_anterior = form.initial.get('salario')
            cambios.append(f"Salario modificado de ${salario_anterior} a ${obj.salario} USD")

        # Verifica si cambió el puesto
        if 'puesto' in form.changed_data:
            puesto_anterior = form.initial.get('puesto')
            cambios.append(f"Puesto modificado de '{puesto_anterior}' a '{obj.puesto}'")

        # Verifica si cambió el nombre completo
        if 'nombre_completo' in form.changed_data:
            nombre_anterior = form.initial.get('nombre_completo')
            cambios.append(f"Nombre modificado de '{nombre_anterior}' a '{obj.nombre_completo}'")

        # Verifica si cambió el estado laboral (activo / inactivo)
        if 'estado_laboral' in form.changed_data:
            if not obj.estado_laboral:
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
                empleado=obj,
                usuario_modificador=request.user,
                accion_realizada=accion,
                detalles_cambio=detalles_texto
            )


class AuditoriaEmpleadoAdmin(admin.ModelAdmin):
    """
    Panel de visualización del historial de auditoría de empleados.
    Garantiza la inmutabilidad de los registros para cumplir con buenas prácticas contables y de RRHH.
    """
    list_display = (
        'empleado',
        'accion_realizada',
        'detalles_cambio',
        'usuario_modificador',
        'fecha_modificacion'
    )
    list_filter = ('accion_realizada', 'fecha_modificacion')
    search_fields = ('empleado__nombre_completo', 'detalles_cambio')
    readonly_fields = (
        'empleado',
        'usuario_modificador',
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

# Personalización de títulos del Panel de Administración
admin.site.site_header = "Panel de Control - Gestión de Recursos Humanos"
admin.site.site_title = "Gestión de Empleados"
admin.site.index_title = "Administración de Empleados y Auditoría"



