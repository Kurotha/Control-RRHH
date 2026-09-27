from datetime import date, datetime
from decimal import Decimal

from openpyxl import load_workbook
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from rrhh.models import (
    Empleado, Departamento, Puesto, EmpleadoPuesto,
    Salario, Asistencia, Permiso, Evaluacion,
)

GENEROS = {
    'Femenino': 'FEMENINO',
    'Masculino': 'MASCULINO',
    'Otro': 'OTRO',
    'Prefiero no decirlo': 'NO_DECIR',
}


def texto(v):
    return '' if v is None else str(v).strip()


def a_fecha(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if v in (None, ''):
        return None
    return datetime.strptime(str(v).strip(), '%d-%m-%Y').date()


def a_hora(v):
    if v in (None, ''):
        return None
    return v.time() if isinstance(v, datetime) else v


def a_decimal(v):
    return Decimal(str(v)) if v not in (None, '') else Decimal('0')


def si_no(v):
    """Sí -> True, No -> False, vacío -> None (pendiente)."""
    v = texto(v).lower()
    if v in ('sí', 'si'):
        return True
    if v == 'no':
        return False
    if v == '':
        return None
    raise ValueError(f"se esperaba 'Sí', 'No' o vacío, y llegó '{v}'")


def guardar(modelo, claves, valores):
    """Crea el registro, o lo actualiza si ya existe (así no se duplica al ejecutar dos veces)."""
    try:
        obj = modelo.objects.get(**claves)
        for campo, valor in valores.items():
            setattr(obj, campo, valor)
    except modelo.DoesNotExist:
        obj = modelo(**claves, **valores)
    obj.full_clean(validate_unique=False)  # aplica las validaciones del modelo
    obj.save()


class Command(BaseCommand):
    help = 'Carga las tablas de RRHH desde Excel a la base de datos'

    def leer_hoja(self, wb, nombre, columnas):
        if nombre not in wb.sheetnames:
            raise CommandError(f"Falta la hoja '{nombre}' en el Excel.")
        filas = list(wb[nombre].iter_rows(values_only=True))
        cabecera = [texto(c) for c in filas[0]]
        faltan = [c for c in columnas if c not in cabecera]
        if faltan:
            raise CommandError(f"En la hoja '{nombre}' faltan las columnas: {', '.join(faltan)}")
        resultado = []
        for n, fila in enumerate(filas[1:], start=2):
            if all(c is None or texto(c) == '' for c in fila):
                continue  # ignora filas vacías
            resultado.append((n, dict(zip(cabecera, fila))))
        return resultado

    def cargar(self, wb, hoja, columnas, funcion):
        contador = 0
        for n, f in self.leer_hoja(wb, hoja, columnas):
            try:
                funcion(f)
            except Exception as e:
                raise CommandError(f"Hoja '{hoja}', fila {n}: {e}")
            contador += 1
        self.stdout.write(f"  {hoja}: {contador} registros")

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando la lectura de datos crudos...")
        ruta_archivo = 'data/raw_data.xlsx'

        try:
            wb = load_workbook(ruta_archivo, data_only=True)
        except FileNotFoundError:
            raise CommandError(f"No se encontró el archivo {ruta_archivo}")

        try:
            # Todo o nada: si algo falla, no se guarda nada a medias
            with transaction.atomic():
                self.cargar(wb, 'Empleado',
                            ['dni', 'nombre_empleado', 'email', 'fecha_nacimiento', 'genero', 'genero_otro',
                             'telefono', 'direccion', 'fecha_contratacion', 'estado_empleado'],
                            self.empleado)
                self.cargar(wb, 'Departamento',
                            ['nombre_departamento', 'descripcion', 'dni_jefe', 'presupuesto'],
                            self.departamento)
                self.cargar(wb, 'Puesto',
                            ['id_puesto', 'nombre_puesto', 'nombre_departamento', 'nivel', 'salario_base'],
                            self.puesto)
                self.cargar(wb, 'EmpleadoPuesto',
                            ['dni', 'id_puesto', 'fecha_inicio_puesto', 'fecha_fin_puesto', 'es_actual'],
                            self.empleado_puesto)
                self.cargar(wb, 'Salario',
                            ['dni', 'mes_anio', 'salario_base', 'bonificacion', 'descuentos', 'pagado'],
                            self.salario)
                self.cargar(wb, 'Asistencia',
                            ['dni', 'fecha', 'hora_entrada', 'hora_salida', 'estado_asistencia'],
                            self.asistencia)
                self.cargar(wb, 'Permiso',
                            ['dni', 'tipo', 'fecha_inicio_permiso', 'fecha_fin_permiso', 'aprobado'],
                            self.permiso)
                self.cargar(wb, 'Evaluacion',
                            ['dni', 'periodo', 'puntuacion', 'feedback'],
                            self.evaluacion)

                # Los puestos se cargaron con id fijo: se ajusta el contador para que
                # los puestos nuevos que se creen después no choquen con esos ids.
                with connection.cursor() as cursor:
                    for sql in connection.ops.sequence_reset_sql(no_style(), [Puesto]):
                        cursor.execute(sql)

            self.stdout.write(self.style.SUCCESS("Éxito: todos los datos fueron guardados."))
        except CommandError:
            raise
        except Exception as e:
            raise CommandError(f"Error de ingesta: {e}")

    # ---- una función por hoja ----

    def empleado(self, f):
        estado = texto(f['estado_empleado'])
        if estado not in ('Activo', 'Inactivo'):
            raise ValueError(f"estado_empleado debe ser 'Activo' o 'Inactivo', y llegó '{estado}'")
        genero = texto(f['genero'])
        if genero not in GENEROS:
            raise ValueError(f"genero no reconocido: '{genero}'")
        guardar(Empleado, {'dni': texto(f['dni'])}, {
            'nombre_empleado': texto(f['nombre_empleado']),
            'email': texto(f['email']),
            'fecha_nacimiento': a_fecha(f['fecha_nacimiento']),
            'genero': GENEROS[genero],
            'genero_otro': texto(f['genero_otro']),
            'telefono': texto(f['telefono']),
            'direccion': texto(f['direccion']),
            'fecha_contratacion': a_fecha(f['fecha_contratacion']),
            'estado_empleado': estado == 'Activo',
        })

    def departamento(self, f):
        guardar(Departamento, {'nombre_departamento': texto(f['nombre_departamento'])}, {
            'descripcion': texto(f['descripcion']),
            'dni_jefe_id': texto(f['dni_jefe']) or None,
            'presupuesto': a_decimal(f['presupuesto']),
        })

    def puesto(self, f):
        guardar(Puesto, {'id_puesto': int(f['id_puesto'])}, {
            'nombre_puesto': texto(f['nombre_puesto']),
            'nombre_departamento_id': texto(f['nombre_departamento']),
            'nivel': texto(f['nivel']),
            'salario_base': a_decimal(f['salario_base']),
        })

    def empleado_puesto(self, f):
        es_actual = si_no(f['es_actual'])
        if es_actual is None:
            raise ValueError("es_actual no puede ir vacío")
        guardar(EmpleadoPuesto, {
            'dni_id': texto(f['dni']),
            'id_puesto_id': int(f['id_puesto']),
            'fecha_inicio_puesto': a_fecha(f['fecha_inicio_puesto']),
        }, {
            'fecha_fin_puesto': a_fecha(f['fecha_fin_puesto']),
            'es_actual': es_actual,
        })

    def salario(self, f):
        pagado = si_no(f['pagado'])
        guardar(Salario, {'dni_id': texto(f['dni']), 'mes_anio': texto(f['mes_anio'])}, {
            'salario_base': a_decimal(f['salario_base']),
            'bonificacion': a_decimal(f['bonificacion']),
            'descuentos': a_decimal(f['descuentos']),
            'pagado': bool(pagado),
        })  # el neto lo calcula el modelo al guardar

    def asistencia(self, f):
        guardar(Asistencia, {'dni_id': texto(f['dni']), 'fecha': a_fecha(f['fecha'])}, {
            'hora_entrada': a_hora(f['hora_entrada']),
            'hora_salida': a_hora(f['hora_salida']),
            'estado_asistencia': texto(f['estado_asistencia']),
        })  # los minutos trabajados los calcula el modelo al guardar

    def permiso(self, f):
        guardar(Permiso, {
            'dni_id': texto(f['dni']),
            'fecha_inicio_permiso': a_fecha(f['fecha_inicio_permiso']),
            'fecha_fin_permiso': a_fecha(f['fecha_fin_permiso']),
        }, {
            'tipo': texto(f['tipo']),
            'aprobado': si_no(f['aprobado']),
        })  # los días los calcula el modelo al guardar

    def evaluacion(self, f):
        guardar(Evaluacion, {'dni_id': texto(f['dni']), 'periodo': texto(f['periodo'])}, {
            'puntuacion': int(f['puntuacion']),
            'feedback': texto(f['feedback']),
        })