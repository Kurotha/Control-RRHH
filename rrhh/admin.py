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
from django.db.models.functions import Substr
from .models import (
    Empleado, AuditoriaEmpleado, Departamento, Puesto,
    EmpleadoPuesto, Salario, Asistencia, Permiso, Evaluacion,
)


def _clp(valor):
    """
    Formatea un monto en pesos chilenos para mostrarlo en el admin.

    Redondea a entero (el peso chileno no usa decimales) y usa punto
    como separador de miles. Ejemplo: Decimal('1800000.00') -> '$1.800.000'.
    Si el valor es None devuelve un guion largo.
    """
    if valor is None:
        return "—"
    return "$" + f"{int(round(valor)):,}".replace(",", ".")


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
        'obtener_salario',
        'rol',
        'estado_empleado',
        'fecha_contratacion',
        'obtener_ultimo_salario'
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
            ),
            salario_orden=Subquery(
                puesto_activo.values('id_puesto__salario_base')[:1]
            ),
            ultimo_salario_orden=Subquery(
                Salario.objects.filter(dni=OuterRef('pk'))
                .annotate(anio=Substr('mes_anio', 4, 4), mes=Substr('mes_anio', 1, 2))
                .order_by('-anio', '-mes')
                .values('neto')[:1]
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

    @admin.display(description='Salario base', ordering='salario_orden')
    def obtener_salario(self, obj):
        """Muestra el salario base del puesto activo."""
        return _clp(obj.salario_orden)

    @admin.display(description='Último salario (neto)', ordering='ultimo_salario_orden')
    def obtener_ultimo_salario(self, obj):
        """Muestra el neto del salario más reciente registrado."""
        if obj.ultimo_salario_orden is None:
            return "Sin salarios"
        return _clp(obj.ultimo_salario_orden)

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


class DepartamentoAdmin(ModelAdmin):
    list_display = ('nombre_departamento', 'dni_jefe', 'ver_presupuesto')
    search_fields = ('nombre_departamento', 'dni_jefe__nombre_empleado')

    @admin.display(description='Presupuesto', ordering='presupuesto')
    def ver_presupuesto(self, obj):
        return _clp(obj.presupuesto)


class PuestoAdmin(ModelAdmin):
    list_display = ('nombre_puesto', 'nombre_departamento', 'nivel', 'ver_salario_base')
    search_fields = ('nombre_puesto',)
    list_filter = ('nombre_departamento', 'nivel')

    @admin.display(description='Salario base', ordering='salario_base')
    def ver_salario_base(self, obj):
        return _clp(obj.salario_base)


class EmpleadoPuestoAdmin(ModelAdmin):
    list_display = ('dni', 'id_puesto', 'fecha_inicio_puesto', 'fecha_fin_puesto', 'es_actual')
    search_fields = ('dni__dni', 'dni__nombre_empleado', 'id_puesto__nombre_puesto')
    list_filter = ('es_actual',)


class SalarioAdmin(ModelAdmin):
    list_display = (
        'dni', 'mes_anio', 'ver_salario_base', 'ver_bonificacion',
        'ver_descuentos', 'ver_neto', 'pagado'
    )
    search_fields = ('dni__dni', 'dni__nombre_empleado', 'mes_anio')
    list_filter = ('pagado',)

    @admin.display(description='Salario base', ordering='salario_base')
    def ver_salario_base(self, obj):
        return _clp(obj.salario_base)

    @admin.display(description='Bonificación', ordering='bonificacion')
    def ver_bonificacion(self, obj):
        return _clp(obj.bonificacion)

    @admin.display(description='Descuentos', ordering='descuentos')
    def ver_descuentos(self, obj):
        return _clp(obj.descuentos)

    @admin.display(description='Neto', ordering='neto')
    def ver_neto(self, obj):
        return _clp(obj.neto)


class AsistenciaAdmin(ModelAdmin):
    list_display = ('dni', 'fecha', 'hora_entrada', 'hora_salida', 'minutos_trabajados', 'estado_asistencia')
    search_fields = ('dni__dni', 'dni__nombre_empleado')
    list_filter = ('estado_asistencia', 'fecha')


class PermisoAdmin(ModelAdmin):
    list_display = ('dni', 'tipo', 'fecha_inicio_permiso', 'fecha_fin_permiso', 'dias', 'aprobado')
    search_fields = ('dni__dni', 'dni__nombre_empleado')
    list_filter = ('tipo', 'aprobado')


class EvaluacionAdmin(ModelAdmin):
    list_display = ('dni', 'periodo', 'puntuacion')
    search_fields = ('dni__dni', 'dni__nombre_empleado')
    list_filter = ('periodo', 'puntuacion')


# Registrar los modelos con sus clases de administración correspondientes
admin.site.register(Empleado, EmpleadoAdmin)
admin.site.register(AuditoriaEmpleado, AuditoriaEmpleadoAdmin)
admin.site.register(Departamento, DepartamentoAdmin)
admin.site.register(Puesto, PuestoAdmin)
admin.site.register(EmpleadoPuesto, EmpleadoPuestoAdmin)
admin.site.register(Salario, SalarioAdmin)
admin.site.register(Asistencia, AsistenciaAdmin)
admin.site.register(Permiso, PermisoAdmin)
admin.site.register(Evaluacion, EvaluacionAdmin)

# Personalización de títulos del Panel de Administración
admin.site.site_header = "Panel de Control - Gestión de Recursos Humanos"
admin.site.site_title = "Gestión de Empleados"
admin.site.index_title = "Administración de Empleados y Auditoría"