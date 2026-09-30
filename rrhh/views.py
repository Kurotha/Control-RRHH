from django.shortcuts import render
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse
from django.core.exceptions import ValidationError
from .models import Empleado, Permiso, Asistencia, Salario, Evaluacion
from utils.convertidor import Conversor
from datetime import date, datetime

def listar_empleados(request):
    """
    Vista que consulta la lista de empleados, obtiene el tipo de cambio
    actual del dólar y calcula los salarios y la nómina total en USD.
    """
    # Consulta todos los empleados de la base de datos (ordenados por el modelo)
    empleados = Empleado.objects.all()
    
    # Obtenemos la tasa de cambio del dólar una sola vez para no saturar la API
    tasa_dolar = Conversor.dolar_dia(timezone.now())
    
    # Calculamos el salario en USD para cada empleado y el total de la nómina
    total_nomina = 0.0
    for emp in empleados:
        puesto_actual = emp.historial_puestos.filter(es_actual=True).first()
        salario_base = puesto_actual.id_puesto.salario_base if puesto_actual else 0

        emp.salario_usd = round(float(salario_base) / tasa_dolar, 2)
        if emp.estado_empleado:
            total_nomina += emp.salario_usd

    # Renderiza la plantilla HTML enviando el contexto con la lista de empleados, nómina total y tasa
    return render(request, 'empleados.html', {
        'empleados': empleados,
        'total_nomina': total_nomina,
        'tasa_dolar': tasa_dolar
    })

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def login_view(request):
    if request.method == 'POST':
        rut = request.POST.get('rut')
        password = request.POST.get('password')
        user = authenticate(request, username=rut, password=password)

        if user is not None:
            login(request, user)
            if user.empleado.rol == 'JEFE':
                return redirect('dashboard_jefe')
            return redirect('dashboard_empleado')

        return render(request, 'login.html', {'error': 'RUT o contraseña incorrectos'})

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


SECCIONES_JEFE = [
    ('equipo', 'Equipo'),
    ('permisos', 'Permisos'),
    ('asistencia', 'Asistencia'),
    ('sueldos', 'Sueldos'),
    ('evaluaciones', 'Evaluaciones'),
]


def evaluacion_del_equipo(pk, equipo):
    """Devuelve la evaluación si existe y es de alguien del equipo; si no, None."""
    try:
        return Evaluacion.objects.filter(pk=pk, dni__in=equipo).select_related('dni').first()
    except (TypeError, ValueError):  # id inválido en la URL
        return None


@login_required
def dashboard_jefe(request):
    empleado = request.user.empleado
    if empleado.rol != 'JEFE':
        return redirect('login')

    departamentos = empleado.departamentos_dirigidos.all()
    equipo = Empleado.objects.filter(
        estado_empleado=True,
        historial_puestos__es_actual=True,
        historial_puestos__id_puesto__nombre_departamento__in=departamentos,
    ).exclude(pk=empleado.pk).distinct()

    # Sección elegida en el menú (por defecto, equipo)
    seccion = request.GET.get('seccion', 'equipo')
    if seccion not in dict(SECCIONES_JEFE):
        seccion = 'equipo'
    vista = request.GET.get('vista', 'nueva')  # pestaña dentro de Evaluaciones
    if vista not in ('nueva', 'historial', 'editar'):
        vista = 'nueva'
    datos_form = {}  # para no perder lo escrito si el formulario falla

    if request.method == 'POST':
        accion = request.POST.get('accion')

        # Botones Aprobar / Rechazar permiso
        if accion in ('aprobar', 'rechazar'):
            actualizados = Permiso.objects.filter(
                pk=request.POST.get('permiso_id'),
                dni__in=equipo,
                aprobado__isnull=True,
            ).update(aprobado=(accion == 'aprobar'))
            if actualizados and accion == 'aprobar':
                messages.success(request, 'Permiso aprobado con éxito.')
            elif actualizados:
                messages.success(request, 'Permiso rechazado con éxito.')
            else:
                messages.error(request, 'No se pudo actualizar el permiso.')
            return redirect(reverse('dashboard_jefe') + '?seccion=permisos')

        # Guardar cambios de una evaluación existente
        if accion == 'actualizar':
            evaluacion = evaluacion_del_equipo(request.POST.get('evaluacion_id'), equipo)
            if evaluacion is None:
                messages.error(request, 'Esa evaluación no existe o no es de tu equipo.')
                return redirect(reverse('dashboard_jefe') + '?seccion=evaluaciones&vista=historial')
            try:
                feedback = request.POST.get('feedback', '').strip()
                puntuacion = int(request.POST.get('puntuacion'))
                if not feedback:
                    raise ValidationError('El feedback no puede estar vacío.')
                evaluacion.puntuacion = puntuacion
                evaluacion.feedback = feedback
                evaluacion.full_clean()
                evaluacion.save()
            except (TypeError, ValueError):
                messages.error(request, 'La puntuación debe ser un número del 1 al 5.')
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
            else:
                messages.success(request, 'Evaluación actualizada con éxito.')
                return redirect(reverse('dashboard_jefe') + '?seccion=evaluaciones&vista=historial')
            # Si hubo error, vuelve al formulario de esa misma evaluación
            return redirect(
                reverse('dashboard_jefe') + f'?seccion=evaluaciones&vista=editar&id={evaluacion.pk}'
            )

        # Formulario de nueva evaluación
        if accion == 'evaluar':
            seccion = 'evaluaciones'
            try:
                evaluado = equipo.get(pk=request.POST.get('dni'))
                periodo = request.POST.get('periodo', '').strip().upper()
                feedback = request.POST.get('feedback', '').strip()
                puntuacion = int(request.POST.get('puntuacion'))

                if not feedback:
                    raise ValidationError('El feedback no puede estar vacío.')
                if Evaluacion.objects.filter(dni=evaluado, periodo=periodo).exists():
                    raise ValidationError(
                        f'{evaluado.nombre_empleado} ya tiene una evaluación en el período {periodo}.'
                    )

                evaluacion = Evaluacion(
                    dni=evaluado, periodo=periodo,
                    puntuacion=puntuacion, feedback=feedback,
                )
                evaluacion.full_clean()  # aplica las validaciones del modelo
                evaluacion.save()
            except Empleado.DoesNotExist:
                messages.error(request, 'Debes elegir un empleado de tu equipo.')
                datos_form = request.POST
            except (TypeError, ValueError):
                messages.error(request, 'La puntuación debe ser un número del 1 al 5.')
                datos_form = request.POST
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
                datos_form = request.POST
            else:
                messages.success(request, 'Evaluación creada con éxito.')
                return redirect(reverse('dashboard_jefe') + '?seccion=evaluaciones&vista=historial')

    contexto = {
        'secciones': SECCIONES_JEFE,
        'seccion': seccion,
        'equipo': equipo,
        'datos_form': datos_form,
        'vista': vista,
    }

    if seccion == 'permisos':
        contexto['permisos_pendientes'] = Permiso.objects.filter(
            dni__in=equipo, aprobado__isnull=True,
        ).select_related('dni')

    elif seccion == 'asistencia':
        import numpy as np
        from utils.manejo_fechas import Manejo_fechas

        # Día elegido en el calendario; si no viene o es inválido, hoy
        try:
            dia = date.fromisoformat(request.GET.get('fecha', ''))
        except ValueError:
            dia = timezone.localdate()

        registros = {
            a.dni_id: a
            for a in Asistencia.objects.filter(dni__in=equipo, fecha=dia)
        }

        # Qué significa "sin registro" ese día
        feriados_fallo = False
        if dia.weekday() >= 5:  # 5 = sábado, 6 = domingo
            sin_registro = 'Fin de semana'
        else:
            feriados = Manejo_fechas.feriados(datetime(dia.year, 1, 1))
            feriados_fallo = len(feriados) == 0  # la API no respondió
            if np.datetime64(dia) in feriados:
                sin_registro = 'Feriado'
            else:
                sin_registro = 'Ausente'

        contexto['dia'] = dia
        contexto['sin_registro'] = sin_registro
        contexto['feriados_fallo'] = feriados_fallo
        contexto['asistencias'] = [
            {'empleado': e, 'registro': registros.get(e.pk)} for e in equipo
        ]

    elif seccion == 'sueldos':
        # mes_anio es texto "MM-AAAA": ordenarlo como texto daría el orden incorrecto
        # ("12-2025" quedaría después de "09-2026"), así que se compara (año, mes) como números.
        sueldos = []
        for e in equipo.prefetch_related('salarios'):
            ultimo = max(
                e.salarios.all(),
                key=lambda s: (int(s.mes_anio[3:]), int(s.mes_anio[:2])),
                default=None,
            )
            sueldos.append({'empleado': e, 'salario': ultimo})
        contexto['sueldos'] = sueldos

    elif seccion == 'evaluaciones' and vista == 'historial':
        contexto['evaluaciones'] = Evaluacion.objects.filter(
            dni__in=equipo,
        ).select_related('dni').order_by('-periodo', 'dni__nombre_empleado')

    elif seccion == 'evaluaciones' and vista == 'editar':
        evaluacion = evaluacion_del_equipo(request.GET.get('id'), equipo)
        if evaluacion is None:
            messages.error(request, 'Esa evaluación no existe o no es de tu equipo.')
            return redirect(reverse('dashboard_jefe') + '?seccion=evaluaciones&vista=historial')
        contexto['evaluacion'] = evaluacion

    return render(request, 'dashboard_jefe.html', contexto)

@login_required
def dashboard_empleado(request):
    """
    Gestiona la vista del panel de control para un empleado autenticado.

    Esta función valida el rol del usuario para asegurar el acceso correcto.
    A través del método POST, procesa la creación de nuevas solicitudes de
    permisos laborales. A través del método GET, consulta la base de datos
    para renderizar el historial del empleado, filtrando la carga de datos
    de forma dinámica según la pestaña (sección) seleccionada en la URL.

    Args:
        request (HttpRequest): El objeto que contiene la petición HTTP.

    Returns:
        HttpResponseRedirect: Redirige a 'login' si el rol es incorrecto, 
            o recarga la página de permisos tras procesar el formulario POST.
        HttpResponse: La plantilla renderizada 'dashboard_empleado.html' 
            con el diccionario de contexto de datos correspondiente.
    """
    empleado = request.user.empleado

    # Seguridad: Restringir acceso exclusivamente al rol de empleado.
    if empleado.rol != 'EMPLEADO':
        return redirect('login')

    seccion = request.GET.get('seccion', 'info')

    # Procesamiento de creación de solicitudes de permisos (CRUD: Create).
    if request.method == 'POST' and request.POST.get('accion') == 'solicitar':
        try:
            nuevo_permiso = Permiso(
                dni=empleado,
                tipo=request.POST.get('tipo'),
                fecha_inicio_permiso=request.POST.get('fecha_inicio'),
                fecha_fin_permiso=request.POST.get('fecha_fin')
            )
            # full_clean() ejecuta las validaciones definidas en models.py.
            nuevo_permiso.full_clean()
            nuevo_permiso.save()

            messages.success(
                request,
                "Solicitud de permiso enviada correctamente. "
                "Esperando aprobación."
            )
        except ValidationError as error:
            mensajes_error = ' '.join(error.messages)
            messages.error(
                request, 
                f"Error en la solicitud: {mensajes_error}"
            )

        # Redirección limpia mediante PRG (Post/Redirect/Get) pattern.
        url_redireccion = f"{reverse('dashboard_empleado')}?seccion=permisos"
        return redirect(url_redireccion)

    # Preparación del diccionario de contexto base para la plantilla.
    contexto = {
        'empleado': empleado,
        'seccion': seccion,
    }

    # Carga de datos diferida (Lazy loading) según la navegación (CRUD: Read).
    if seccion == 'info' or not seccion:
        contexto['puesto_actual'] = empleado.historial_puestos.filter(
            es_actual=True
        ).first()

    elif seccion == 'permisos':
        contexto['permisos'] = empleado.permisos.all()

    elif seccion == 'asistencia':
        # Limitar la consulta a los últimos 30 registros para rendimiento.
        contexto['asistencias'] = empleado.asistencias.all()[:30]

    elif seccion == 'sueldos':
        contexto['sueldos'] = empleado.salarios.all()

    elif seccion == 'evaluaciones':
        contexto['evaluaciones'] = empleado.evaluaciones.all()

    return render(request, 'dashboard_empleado.html', contexto)