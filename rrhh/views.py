"""
Módulo de vistas para la aplicación de Recursos Humanos en Django.

Maneja la lógica de presentación y el flujo de datos entre los modelos
y las plantillas (templates). Incluye vistas para listar empleados con
cálculo de nómina en divisas, gestión de autenticación (login/logout),
y los paneles de control (dashboards) diferenciados para perfiles con
roles de 'Jefe', 'RRHH' y 'Empleado'.
"""

from datetime import date, datetime
from django.db.models import Prefetch

import numpy as np
import openpyxl
import calendar

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from utils.convertidor import Conversor
from utils.manejo_fechas import Manejo_fechas
from .models import (
    Empleado, Permiso, Asistencia, Salario, Evaluacion,
    Departamento, EmpleadoPuesto,
)


@login_required
def listar_empleados(request):
    """
    Vista que consulta la lista de empleados, obtiene el tipo de cambio
    actual del dólar y calcula los salarios y la nómina total en USD.

    Implementa optimización de consultas (N+1) cargando el historial
    de puestos y la información salarial en memoria (RAM) mediante
    prefetch_related y select_related, reduciendo el tiempo de carga a milisegundos.

    Args:
        request (HttpRequest): Objeto con la petición web.

    Returns:
        HttpResponse: Respuesta renderizada con la plantilla 'empleados.html'.
        HttpResponseRedirect: Redirige a 'login' si el usuario no es RRHH.
    """
    if not hasattr(request.user, 'empleado') or request.user.empleado.rol != 'RRHH':
        return redirect('login')

    # Optimización: Extraemos todos los empleados y sus puestos en 2 consultas masivas
    empleados = list(Empleado.objects.prefetch_related(
        Prefetch(
            'historial_puestos',
            queryset=EmpleadoPuesto.objects.select_related('id_puesto').order_by('-fecha_inicio_puesto'),
            to_attr='puestos_cacheados'  # Guardamos el resultado en la RAM
        )
    ))

    tasa_dolar = Conversor.dolar_dia(timezone.now())

    total_nomina = 0.0
    for emp in empleados:
        # Resolvemos el puesto iterando en la RAM (Python), sin golpear la Base de Datos (SQL)
        puestos = emp.puestos_cacheados
        puesto_actual = next((p for p in puestos if p.es_actual), None) or (puestos[0] if puestos else None)
        
        salario_base = puesto_actual.id_puesto.salario_base if puesto_actual else 0

        emp.salario_usd = round(float(salario_base) / tasa_dolar, 2)
        emp.nombre_puesto_actual = (
            puesto_actual.id_puesto.nombre_puesto if puesto_actual else 'Sin puesto'
        )
        if emp.estado_empleado:
            total_nomina += emp.salario_usd

    # Ordena de mayor a menor salario
    empleados.sort(key=lambda e: e.salario_usd, reverse=True)

    return render(request, 'empleados.html', {
        'empleados': empleados,
        'total_nomina': total_nomina,
        'tasa_dolar': tasa_dolar,
    })


def login_view(request):
    """
    Gestiona el inicio de sesión de los usuarios.

    Procesa las peticiones POST con RUT y contraseña. Si la autenticación
    es exitosa, redirige al usuario al panel de control que corresponda
    según su rol (Jefe, RRHH o Empleado).

    Args:
        request (HttpRequest): Objeto con la petición web y datos del formulario.

    Returns:
        HttpResponseRedirect: Redirige al dashboard correspondiente si las
            credenciales son válidas.
        HttpResponse: Renderiza 'login.html' (con error en caso de fallo,
            o vacío si la petición es GET).
    """
    if request.method == 'POST':
        rut = request.POST.get('rut')
        password = request.POST.get('password')
        usuario = authenticate(request, username=rut, password=password)

        if usuario is not None:
            login(request, usuario)

            # Manejo de errores (Try/except + mensajes claros)
            try:
                # Intenta resolver la relación OneToOneField
                if usuario.empleado.rol == 'JEFE':
                    return redirect('dashboard_jefe')
                if usuario.empleado.rol == 'RRHH':
                    return redirect('dashboard_rrhh')
                return redirect('dashboard_empleado')

            except ObjectDoesNotExist:
                # Captura el error si el usuario no existe en la tabla Empleados
                if usuario.is_staff or usuario.is_superuser:
                    return redirect('admin:index')

                # Manejo de borde: usuario sin privilegios y sin perfil
                return render(
                    request,
                    'login.html',
                    {'error': 'Cuenta sin perfil de empleado asociado.'}
                )

        # Mensaje claro en caso de credenciales inválidas
        return render(
            request,
            'login.html',
            {'error': 'RUT o contraseña incorrectos. Intenta nuevamente.'}
        )

    return render(request, 'login.html')


def logout_view(request):
    """
    Finaliza la sesión del usuario autenticado.

    Args:
        request (HttpRequest): Objeto con la petición web.

    Returns:
        HttpResponseRedirect: Redirige a la vista de login.
    """
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
    """
    Devuelve la evaluación si existe y pertenece a alguien del equipo.

    Args:
        pk (int | str): Llave primaria de la evaluación a buscar.
        equipo (QuerySet): Conjunto de empleados bajo el cargo del jefe.

    Returns:
        Evaluacion | None: Objeto Evaluación si se encuentra y cumple las
            condiciones; de lo contrario, None.
    """
    try:
        return Evaluacion.objects.filter(pk=pk, dni__in=equipo).select_related('dni').first()
    except (TypeError, ValueError):  # id inválido en la URL
        return None


@login_required
def dashboard_jefe(request):
    """
    Controlador central del panel para usuarios con rol de Jefe.

    Centraliza la lógica para gestionar el equipo a su cargo, aprobar o
    rechazar solicitudes de permisos, revisar asistencia, ver nóminas
    y administrar el sistema de evaluaciones del equipo (crear y editar).

    Args:
        request (HttpRequest): Objeto con la petición web y datos de sesión.

    Returns:
        HttpResponseRedirect: Redirige tras procesar formularios (POST) o si
            el usuario no tiene los permisos del rol adecuado.
        HttpResponse: Plantilla 'dashboard_jefe.html' con el contexto
            dinámico según la sección elegida por el jefe.
    """
    empleado = getattr(request.user, 'empleado', None)
    if empleado is None or empleado.rol != 'JEFE':
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


# ---------------------------------------------------------------------------
# Dashboard de RRHH
# ---------------------------------------------------------------------------

SECCIONES_RRHH = [
    ('departamentos', 'Departamentos'),
    ('permisos', 'Próximos permisos'),
    ('evaluaciones', 'Evaluaciones pendientes'),
]


@login_required
def dashboard_rrhh(request):
    """
    Panel de control para usuarios con rol de RRHH.

    Muestra la información de toda la empresa agrupada por departamento:
    jefe del área, empleados activos con su sueldo, próximos permisos y
    empleados con evaluación pendiente en el período actual.

    Args:
        request (HttpRequest): Objeto con la petición web y datos de sesión.

    Returns:
        HttpResponseRedirect: Redirige a 'login' si el usuario no es RRHH.
        HttpResponse: Plantilla 'dashboard_rrhh.html' con el contexto
            de la sección elegida.
    """
    empleado = getattr(request.user, 'empleado', None)
    if empleado is None or empleado.rol != 'RRHH':
        return redirect('login')

    seccion = request.GET.get('seccion', 'departamentos')
    if seccion not in dict(SECCIONES_RRHH):
        seccion = 'departamentos'

    contexto = {'secciones': SECCIONES_RRHH, 'seccion': seccion}

    if seccion == 'departamentos':
        # --- NUEVA LÓGICA: Días hábiles del mes actual ---
        hoy = timezone.localdate()
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        
        # Generar todos los días del mes actual
        dias_del_mes = [date(hoy.year, hoy.month, d) for d in range(1, ultimo_dia + 1)]
        
        # Obtener feriados del año actual usando tu utilidad
        feriados_api = Manejo_fechas.feriados(hoy)
        
        # Contar días hábiles usando tu propio método estático
        dias_habiles_mes = Manejo_fechas.contar_dias_habiles(dias_del_mes, feriados_api)
        contexto['dias_habiles_mes'] = int(dias_habiles_mes)
        
        # --- LÓGICA EXISTENTE DE DEPARTAMENTOS ---
        departamentos = []
        total_empleados_empresa = 0
        
        for depto in Departamento.objects.select_related('dni_jefe'):
            asignaciones = EmpleadoPuesto.objects.filter(
                es_actual=True,
                dni__estado_empleado=True,
                id_puesto__nombre_departamento=depto,
            ).select_related('dni', 'id_puesto')

            filas = [
                {
                    'empleado': a.dni,
                    'puesto': a.id_puesto.nombre_puesto,
                    'salario': a.id_puesto.salario_base,
                }
                for a in asignaciones
            ]
            
            total_empleados_empresa += len(filas)
            
            departamentos.append({
                'depto': depto,
                'filas': filas,
                'cantidad': len(filas),
                'total': sum(f['salario'] for f in filas),
            })
            
        contexto['departamentos'] = departamentos
        contexto['total_empleados_empresa'] = total_empleados_empresa

    elif seccion == 'permisos':
        # Departamento actual de cada empleado (por su puesto vigente)
        depto_de = {
            a.dni_id: a.id_puesto.nombre_departamento_id
            for a in EmpleadoPuesto.objects.filter(es_actual=True).select_related('id_puesto')
        }
        # Permisos que aún no terminaron, del más próximo al más lejano
        permisos = Permiso.objects.filter(
            fecha_fin_permiso__gte=timezone.localdate(),
        ).select_related('dni').order_by('fecha_inicio_permiso')

        grupos = {}
        for p in permisos:
            nombre = depto_de.get(p.dni_id, 'Sin departamento')
            grupos.setdefault(nombre, []).append(p)
        contexto['permisos_por_depto'] = sorted(grupos.items())

    elif seccion == 'evaluaciones':
        hoy = timezone.localdate()
        periodo = f"{hoy.year}-S{1 if hoy.month <= 6 else 2}"
        evaluados = set(
            Evaluacion.objects.filter(periodo=periodo).values_list('dni_id', flat=True)
        )
        # Empleados activos sin evaluación en el período, agrupados por departamento
        grupos = {}
        for a in EmpleadoPuesto.objects.filter(
            es_actual=True, dni__estado_empleado=True,
        ).select_related('dni', 'id_puesto'):
            if a.dni_id not in evaluados:
                grupos.setdefault(a.id_puesto.nombre_departamento_id, []).append(a.dni)
        contexto['periodo'] = periodo
        contexto['pendientes_por_depto'] = sorted(grupos.items())

    return render(request, 'dashboard_rrhh.html', contexto)


# ---------------------------------------------------------------------------
# Dashboard del empleado
# ---------------------------------------------------------------------------

@login_required
def dashboard_empleado(request):
    """
    Gestiona la vista del panel de control para un empleado autenticado.

    Esta función valida el rol del usuario para asegurar el acceso correcto.
    A través del método POST, procesa la creación de nuevas solicitudes de
    permisos laborales y el marcaje de entrada y salida. A través del método
    GET, consulta la base de datos para renderizar el historial del empleado,
    filtrando la carga de datos de forma dinámica según la pestaña (sección)
    seleccionada en la URL.

    Args:
        request (HttpRequest): El objeto que contiene la petición HTTP.

    Returns:
        HttpResponseRedirect: Redirige a 'login' si el rol es incorrecto,
            o recarga la página tras procesar el formulario POST.
        HttpResponse: La plantilla renderizada 'dashboard_empleado.html'
            con el diccionario de contexto de datos correspondiente.
    """
    empleado = getattr(request.user, 'empleado', None)

    # Seguridad: Restringir acceso exclusivamente al rol de empleado.
    if empleado is None or empleado.rol != 'EMPLEADO':
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

    # Marcar asistencia: entrada o salida del día (CRUD: Create / Update).
    if request.method == 'POST' and request.POST.get('accion') in ('marcar_entrada', 'marcar_salida'):
        ahora = timezone.localtime()
        hoy = ahora.date()
        hora = ahora.time().replace(second=0, microsecond=0)
        registro = Asistencia.objects.filter(dni=empleado, fecha=hoy).first()

        if request.POST.get('accion') == 'marcar_entrada':
            if registro:
                messages.error(request, 'Ya marcaste tu entrada hoy.')
            else:
                Asistencia.objects.create(
                    dni=empleado, fecha=hoy,
                    hora_entrada=hora, estado_asistencia='Presente',
                )
                messages.success(request, f'Entrada registrada a las {hora:%H:%M}.')
        else:
            if registro is None:
                messages.error(request, 'Primero debes marcar tu entrada.')
            elif registro.hora_salida:
                messages.error(request, 'Ya marcaste tu salida hoy.')
            elif hora <= registro.hora_entrada:
                messages.error(request, 'La salida debe ser posterior a la entrada.')
            else:
                registro.hora_salida = hora
                registro.save()  # el modelo calcula solo los minutos trabajados
                messages.success(request, f'Salida registrada a las {hora:%H:%M}.')

        return redirect(f"{reverse('dashboard_empleado')}?seccion=asistencia")

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
        # Historial completo, del más reciente al más antiguo (orden definido en el modelo)
        contexto['historial_puestos'] = empleado.historial_puestos.select_related(
            'id_puesto__nombre_departamento'
        )

    elif seccion == 'permisos':
        contexto['permisos'] = empleado.permisos.all()

    elif seccion == 'asistencia':
        # Limitar la consulta a los últimos 30 registros para rendimiento.
        contexto['asistencias'] = empleado.asistencias.all()[:30]
        # Registro de hoy, para saber qué botón habilitar
        contexto['asistencia_hoy'] = empleado.asistencias.filter(
            fecha=timezone.localdate()
        ).first()

    elif seccion == 'sueldos':
        contexto['sueldos'] = empleado.salarios.all()

    elif seccion == 'evaluaciones':
        contexto['evaluaciones'] = empleado.evaluaciones.all()

    return render(request, 'dashboard_empleado.html', contexto)


@login_required
def exportar_nomina_excel(request):
    """
    Genera y descarga un reporte en formato Excel con la nómina de empleados.

    Consulta la base de datos para extraer el historial de salarios de todos
    los empleados, incluyendo bonificaciones, descuentos, el sueldo neto y
    el estado de pago. Retorna el archivo como una respuesta HTTP directa
    para su descarga.

    Args:
        request (HttpRequest): El objeto que contiene la petición HTTP.

    Returns:
        HttpResponse: Respuesta HTTP con el archivo .xlsx adjunto y los
            encabezados correspondientes para forzar su descarga.
        HttpResponseRedirect: Redirección al login si el usuario no es RRHH.
    """
    # Seguridad: RRHH descarga toda la empresa; el Jefe, solo su equipo.
    empleado = getattr(request.user, 'empleado', None)
    if empleado is None or empleado.rol not in ('RRHH', 'JEFE'):
        return redirect('login')

    # Crear el libro de trabajo y la hoja activa.
    workbook = openpyxl.Workbook()
    hoja = workbook.active
    hoja.title = 'Reporte de Nómina'

    # Definir los encabezados de las columnas del reporte.
    encabezados = [
        'RUT', 'Nombre Empleado', 'Mes/Año', 'Sueldo Base',
        'Bonificación', 'Descuentos', 'Sueldo Neto', 'Estado de Pago'
    ]
    hoja.append(encabezados)

    # Extraer los datos optimizando la consulta con select_related.
    salarios = Salario.objects.select_related('dni').order_by(
        '-mes_anio', 'dni__nombre_empleado'
    )

    # El jefe solo descarga los sueldos de su propio equipo.
    if empleado.rol == 'JEFE':
        equipo = Empleado.objects.filter(
            estado_empleado=True,
            historial_puestos__es_actual=True,
            historial_puestos__id_puesto__nombre_departamento__in=empleado.departamentos_dirigidos.all(),
        ).exclude(pk=empleado.pk).distinct()
        salarios = salarios.filter(dni__in=equipo)

    # Llenar las filas iterando sobre los registros de salarios.
    for salario in salarios:
        estado_pago = "Pagado" if salario.pagado else "Pendiente"
        hoja.append([
            salario.dni.dni,
            salario.dni.nombre_empleado,
            salario.mes_anio,
            float(salario.salario_base),
            float(salario.bonificacion),
            float(salario.descuentos),
            float(salario.neto),
            estado_pago
        ])

    # Configurar la respuesta HTTP para forzar la descarga del archivo.
    fecha_actual = datetime.now().strftime('%Y%m%d')
    nombre_archivo = f"Reporte_Nomina_{fecha_actual}.xlsx"

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

    # Guardar la estructura de Excel directamente en la respuesta HTTP.
    workbook.save(response)

    return response


def csrf_fallo(request, reason=''):
    """
    Se ejecuta cuando falla la verificación CSRF: formulario viejo, o la sesión
    cambió porque se abrió otra cuenta en el mismo navegador.
    En vez del error 403, muestra el login con un mensaje claro.

    Args:
        request (HttpRequest): Objeto con la petición web.
        reason (str): Motivo del fallo que entrega Django.

    Returns:
        HttpResponse: Renderiza 'login.html' con un mensaje de error.
    """
    return render(request, 'login.html', {
        'error': 'Tu sesión cambió o venció. Ingresa nuevamente.'
    })