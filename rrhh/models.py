from django.db import models

class Empleado(models.Model):
    nombre_completo = models.CharField(max_length=50)
    puesto = models.CharField(max_length=50)
    salario = models.FloatField()
    estado_laboral = models.BooleanField(default=True)
    
    def __str__(self):
        return self.nombre_completo