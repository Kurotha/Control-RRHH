from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.contrib.auth.models import User


class Empleado(models.Model):
    GENEROS = [
        ('FEMENINO', 'Femenino'),
        ('MASCULINO', 'Masculino'),
        ('OTRO', 'Otro'),
        ('NO_DECIR', 'Prefiero no decirlo'),
    ]

    dni = models.CharField(max_length=12, primary_key=True)
    nombre_empleado = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    fecha_nacimiento = models.DateField()
    genero = models.CharField(max_length=10, choices=GENEROS)
    genero_otro = models.CharField(max_length=50, blank=True)  # opcional, para especificar si elige "Otro"
    telefono = models.CharField(max_length=20)
    direccion = models.CharField(max_length=150)
    fecha_contratacion = models.DateField()
    estado_empleado = models.BooleanField(default=True)  # True = Activo, False = Inactivo
    usuario = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='empleado',
    )
    rol = models.CharField(
        max_length=10,
        choices=[('JEFE', 'Jefe'), ('EMPLEADO', 'Empleado')],
        default='EMPLEADO',
    )
    
    def __str__(self):
        return f"{self.nombre_empleado} ({self.dni})"

    class Meta:
        ordering = ['nombre_empleado']
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"


class Departamento(models.Model):
    nombre_departamento = models.CharField(max_length=80, primary_key=True)
    descripcion = models.TextField()
    # Si se elimina al jefe, el departamento sigue existiendo y queda sin jefe
    dni_jefe = models.ForeignKey(
        Empleado, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='dni_jefe', related_name='departamentos_dirigidos',
    )
    presupuesto = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.nombre_departamento

    class Meta:
        ordering = ['nombre_departamento']
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"


class Puesto(models.Model):
    id_puesto = models.AutoField(primary_key=True)
    nombre_puesto = models.CharField(max_length=80)
    nombre_departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT,
        db_column='nombre_departamento', related_name='puestos',
    )
    nivel = models.CharField(max_length=50)
    salario_base = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.nombre_puesto} - {self.nombre_departamento_id}"

    class Meta:
        ordering = ['nombre_departamento', 'nombre_puesto']
        constraints = [
            models.UniqueConstraint(
                fields=['nombre_puesto', 'nombre_departamento'],
                name='puesto_unico_por_departamento',
            ),
        ]
        verbose_name = "Puesto"
        verbose_name_plural = "Puestos"


class EmpleadoPuesto(models.Model):
    # Si se elimina el empleado, se elimina su historial. Un puesto ocupado no se puede eliminar.
    dni = models.ForeignKey(
        Empleado, on_delete=models.CASCADE,
        db_column='dni', related_name='historial_puestos',
    )
    id_puesto = models.ForeignKey(
        Puesto, on_delete=models.PROTECT,
        db_column='id_puesto', related_name='asignaciones',
    )
    fecha_inicio_puesto = models.DateField()
    fecha_fin_puesto = models.DateField(null=True, blank=True)  # vacía mientras es el puesto actual
    es_actual = models.BooleanField(default=True)

    def clean(self):
        if self.fecha_fin_puesto and self.fecha_fin_puesto < self.fecha_inicio_puesto:
            raise ValidationError("La fecha de fin no puede ser anterior a la fecha de inicio.")

    def __str__(self):
        return f"{self.dni_id} - {self.id_puesto}"

    class Meta:
        ordering = ['-fecha_inicio_puesto']
        constraints = [
            models.UniqueConstraint(
                fields=['dni', 'id_puesto', 'fecha_inicio_puesto'],
                name='empleadopuesto_unico',
            ),
        ]
        verbose_name = "Puesto de Empleado"
        verbose_name_plural = "Historial de Puestos"


class Salario(models.Model):
    dni = models.ForeignKey(
        Empleado, on_delete=models.CASCADE,
        db_column='dni', related_name='salarios',
    )
    mes_anio = models.CharField(
        max_length=7,
        validators=[RegexValidator(r'^(0[1-9]|1[0-2])-\d{4}$', "Usa el formato MM-AAAA, por ejemplo 09-2026.")],
    )
    salario_base = models.DecimalField(max_digits=10, decimal_places=2)
    bonificacion = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descuentos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    neto = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0)
    pagado = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Nómina automática: base + bonificación - descuentos = neto
        self.neto = self.salario_base + self.bonificacion - self.descuentos
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dni_id} - {self.mes_anio}"

    class Meta:
        ordering = ['-mes_anio']
        constraints = [
            models.UniqueConstraint(fields=['dni', 'mes_anio'], name='salario_unico_por_mes'),
        ]
        verbose_name = "Salario"
        verbose_name_plural = "Salarios"


class Asistencia(models.Model):
    dni = models.ForeignKey(
        Empleado, on_delete=models.CASCADE,
        db_column='dni', related_name='asistencias',
    )
    fecha = models.DateField()
    hora_entrada = models.TimeField(null=True, blank=True)
    hora_salida = models.TimeField(null=True, blank=True)
    minutos_trabajados = models.PositiveIntegerField(editable=False, default=0)
    estado_asistencia = models.CharField(max_length=50)

    def clean(self):
        if self.hora_entrada and self.hora_salida and self.hora_salida <= self.hora_entrada:
            raise ValidationError("La hora de salida debe ser posterior a la hora de entrada.")

    def save(self, *args, **kwargs):
        # Calcula los minutos trabajados a partir de la entrada y la salida
        if self.hora_entrada and self.hora_salida:
            entrada = datetime.combine(self.fecha, self.hora_entrada)
            salida = datetime.combine(self.fecha, self.hora_salida)
            self.minutos_trabajados = max(int((salida - entrada).total_seconds() // 60), 0)
        else:
            self.minutos_trabajados = 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dni_id} - {self.fecha}"

    class Meta:
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(fields=['dni', 'fecha'], name='asistencia_unica_por_dia'),
        ]
        verbose_name = "Asistencia"
        verbose_name_plural = "Asistencias"


class Permiso(models.Model):
    dni = models.ForeignKey(
        Empleado, on_delete=models.CASCADE,
        db_column='dni', related_name='permisos',
    )
    tipo = models.CharField(max_length=50)
    fecha_inicio_permiso = models.DateField()
    fecha_fin_permiso = models.DateField()
    dias = models.PositiveIntegerField(editable=False, default=0)
    # Vacío = pendiente, True = aprobado, False = rechazado
    aprobado = models.BooleanField(null=True, blank=True, default=None)

    def clean(self):
        if (self.fecha_inicio_permiso and self.fecha_fin_permiso
                and self.fecha_fin_permiso < self.fecha_inicio_permiso):
            raise ValidationError("La fecha de fin no puede ser anterior a la fecha de inicio.")

    def save(self, *args, **kwargs):
        # Cuenta los días hábiles (sin fines de semana ni feriados) con las funciones de manejo_fechas.
        # Los imports van aquí dentro para que el proyecto no falle si numpy aún no está instalado.
        import numpy as np
        from utils.manejo_fechas import Manejo_fechas

        dias_del_permiso = []
        dia = self.fecha_inicio_permiso
        while dia <= self.fecha_fin_permiso:
            dias_del_permiso.append(dia)
            dia += timedelta(days=1)

        # Trae los feriados de cada año que toca el permiso
        feriados = np.array([], dtype="datetime64[D]")
        for anio in range(self.fecha_inicio_permiso.year, self.fecha_fin_permiso.year + 1):
            feriados_anio = Manejo_fechas.feriados(datetime(anio, 1, 1))
            feriados = np.concatenate([feriados, feriados_anio])

        self.dias = int(Manejo_fechas.contar_dias_habiles(dias_del_permiso, feriados))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dni_id} - {self.tipo} ({self.fecha_inicio_permiso})"

    class Meta:
        ordering = ['-fecha_inicio_permiso']
        constraints = [
            models.UniqueConstraint(
                fields=['dni', 'fecha_inicio_permiso', 'fecha_fin_permiso'],
                name='permiso_unico',
            ),
        ]
        verbose_name = "Permiso"
        verbose_name_plural = "Permisos"


class Evaluacion(models.Model):
    dni = models.ForeignKey(
        Empleado, on_delete=models.CASCADE,
        db_column='dni', related_name='evaluaciones',
    )
    periodo = models.CharField(
        max_length=7,
        validators=[RegexValidator(r'^\d{4}-S[12]$', "Usa el formato AAAA-S1 o AAAA-S2, por ejemplo 2026-S1.")],
    )
    puntuacion = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    feedback = models.TextField()

    def __str__(self):
        return f"{self.dni_id} - {self.periodo}: {self.puntuacion}/5"

    class Meta:
        ordering = ['-periodo']
        constraints = [
            models.UniqueConstraint(fields=['dni', 'periodo'], name='evaluacion_unica_por_periodo'),
        ]
        verbose_name = "Evaluación"
        verbose_name_plural = "Evaluaciones"


class AuditoriaEmpleado(models.Model):
    ACCIONES = [
        ('CREACION', 'Creación de registro'),
        ('EDICION', 'Edición de datos'),
        ('DESACTIVACION', 'Desactivación de usuario'),
        ('ELIMINACION', 'Eliminación de registro'),
    ]

    usuario_nombre = models.CharField(max_length=150)   # cuenta que hizo el cambio
    tabla = models.CharField(max_length=50)             # en qué tabla fue
    afectado = models.CharField(max_length=150)         # de quién o de qué fue el cambio
    accion_realizada = models.CharField(max_length=20, choices=ACCIONES)
    detalles_cambio = models.TextField(help_text="Describe qué cambió (ej: Salario de 1000 a 1200)")
    fecha_modificacion = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # La auditoría no se edita: solo se puede crear un registro nuevo
        if self.pk is not None:
            raise ValidationError("Los registros de auditoría no se pueden editar.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los registros de auditoría no se pueden eliminar.")

    def __str__(self):
        return f"{self.accion_realizada} - {self.tabla} - {self.fecha_modificacion:%Y-%m-%d}"

    class Meta:
        ordering = ['-fecha_modificacion']
        verbose_name = "Auditoría"
        verbose_name_plural = "Auditorías"