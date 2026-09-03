from django.shortcuts import render
from .models import Empleado

def listar_empleados(request):
    """
    Vista que consulta la lista completa de empleados desde la base de datos
    y calcula el gasto total mensual en nómina de los empleados activos.
    """
    # Consulta todos los empleados de la base de datos (ordenados de mayor a menor salario por el modelo)
    empleados = Empleado.objects.all()
    
    # Bucle simple para calcular el gasto total mensual en nómina de empleados activos
    total_nomina = 0
    for emp in empleados:
        if emp.estado_laboral:
            total_nomina += emp.salario

    # Renderiza la plantilla HTML enviando el contexto con la lista de empleados y la nómina total
    return render(request, 'empleados.html', {
        'empleados': empleados,
        'total_nomina': total_nomina
    })
