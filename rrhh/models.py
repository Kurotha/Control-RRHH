from django.db import models
from django.contrib.auth.models import User

class Empleado(models.Model):
    nombre_completo = models.CharField(max_length=50)
    puesto = models.CharField(max_length=50)
    salario = models.DecimalField(max_digits=10, decimal_places=2)
    estado_laboral = models.BooleanField(default=True)
    
    def __str__(self):
        return self.nombre_completo
    
    class Meta:
        # Ordena los resultados por "salario" en orden descendente "-"
        ordering = ['-salario']
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"

class AuditoriaEmpleado(models.Model):
    ACCIONES = [
        ('CREACION', 'Creación de registro'),
        ('EDICION', 'Edición de datos'),
        ('DESACTIVACION', 'Desactivación de usuario'),
    ]

    empleado = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True)
    usuario_modificador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    accion_realizada = models.CharField(max_length=20, choices=ACCIONES)
    detalles_cambio = models.TextField(help_text="Describe qué cambió (ej: Salario de 1000 a 1200)")
    fecha_modificacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.accion_realizada} - {self.fecha_modificacion.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-fecha_modificacion']
        verbose_name = "Auditoría de Empleado"
        verbose_name_plural = "Auditorías de Empleados"
