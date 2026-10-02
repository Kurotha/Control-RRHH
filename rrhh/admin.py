"""
Módulo de administración de Django para la aplicación de Recursos Humanos.

Configura la interfaz del panel de administración, registrando los
modelos principales y definiendo clases personalizadas para controlar
la visualización, búsqueda, filtrado y el registro automático de
auditorías al interactuar con los datos.
"""

from django.contrib import admin
from unfold.admin import ModelAdmin
from django.db.models import OuterRef, Subquery
from .models import (
    Empleado, AuditoriaEmpleado, Departamento, Puesto,
    EmpleadoPuesto, Salario, Asistencia, Permiso, Evaluacion,
)


class EmpleadoAdmin(ModelAdmin):
    """
    Configuración del modelo Empleado en el panel de administración.
    
    Utiliza subconsultas (Subquery y OuterRef) para anotar datos relacionales
    directamente en la consulta SQL. Esto elimina el problema N+1 y permite
    ordenar la tabla haciendo clic en las cabeceras de Puesto y Departamento.
    """
    list_display = (
        'dni',
        'nombre_empleado',
        'obtener_departamento',
        'obtener_puesto',
        'rol',
        'estado_empleado'
    )
    
    list_filter = ('rol', 'estado_empleado')
    search_fields = ('dni', 'nombre_empleado')

    def get_queryset(self, request):
        """
        Sobrescribe la consulta base inyectando anotaciones SQL.
        Permite que PostgreSQL resuelva el historial de puestos en la misma
        petición principal, habilitando el ordenamiento nativo en el panel.
        """
        qs = super().get_queryset(request)
        
        # Definimos la subconsulta para buscar el puesto activo del empleado
        puesto_activo = EmpleadoPuesto.objects.filter(
            dni=OuterRef('pk'),
            es_actual=True
        )
        
        # Anotamos (agregamos columnas virtuales) al queryset principal
        return qs.annotate(
            depto_orden=Subquery(
                puesto_activo.values('id_puesto__nombre_departamento__nombre_departamento')[:1]
            ),
            puesto_orden=Subquery(
                puesto_activo.values('id_puesto__nombre_puesto')[:1]
            )
        )

    # El atributo 'ordering' vincula esta columna visual con la anotación SQL
    @admin.display(description='Departamento', ordering='depto_orden')
    def obtener_departamento(self, obj):
        """Muestra el departamento usando la columna virtual anotada."""
        return obj.depto_orden or "Sin departamento"

    @admin.display(description='Puesto', ordering='puesto_orden')
    def obtener_puesto(self, obj):
        """Muestra el puesto usando la columna virtual anotada."""
        return obj.puesto_orden or "Sin puesto asignado"

    def save_model(self, request, obj, form, change):
        """
        Sobrescribe save_model para registrar la auditoría de cambios.

        Intercepta el guardado del modelo en el administrador de Django
        para crear automáticamente un registro en AuditoriaEmpleado,
        vinculando la acción ('CREACION', 'EDICION', 'DESACTIVACION')
        con el usuario responsable.

        Args:
            request (HttpRequest): La petición HTTP actual.
            obj (Empleado): La instancia del modelo que se está guardando.
            form (ModelForm): El formulario con los datos validados.
            change (bool): True si se está modificando un objeto
                existente, False si es una creación nueva.

        Returns:
            None
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


class AuditoriaEmpleadoAdmin(ModelAdmin):
    """
    Panel de visualización del historial de auditoría de empleados.
    
    Garantiza la inmutabilidad de los registros para cumplir con
    buenas prácticas contables y de recursos humanos. Limita las
    acciones a solo lectura.
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
        """
        Evita la creación manual de registros de auditoría.

        Args:
            request (HttpRequest): La petición HTTP actual.

        Returns:
            bool: Siempre retorna False.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Evita la eliminación de registros de auditoría para
        preservar el historial de forma inmutable.

        Args:
            request (HttpRequest): La petición HTTP actual.
            obj (Model, optional): La instancia específica a eliminar.
                Por defecto es None.

        Returns:
            bool: Siempre retorna False.
        """
        return False


# Registrar los modelos con sus clases de administración correspondientes
admin.site.register(Empleado, EmpleadoAdmin)
admin.site.register(AuditoriaEmpleado, AuditoriaEmpleadoAdmin)
admin.site.register(Departamento, ModelAdmin)
admin.site.register(Puesto, ModelAdmin)
admin.site.register(EmpleadoPuesto, ModelAdmin)
admin.site.register(Salario, ModelAdmin)
admin.site.register(Asistencia, ModelAdmin)
admin.site.register(Permiso, ModelAdmin)
admin.site.register(Evaluacion, ModelAdmin)

# Personalización de títulos del Panel de Administración
admin.site.site_header = "Panel de Control - Gestión de Recursos Humanos"
admin.site.site_title = "Gestión de Empleados"
admin.site.index_title = "Administración de Empleados y Auditoría"