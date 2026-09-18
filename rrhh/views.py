from django.shortcuts import render
from django.utils import timezone
from .models import Empleado
from utils.convertidor import Conversor

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
        emp.salario_usd = round(float(emp.salario) / tasa_dolar, 2)
        if emp.estado_laboral:
            total_nomina += emp.salario_usd

    # Renderiza la plantilla HTML enviando el contexto con la lista de empleados, nómina total y tasa
    return render(request, 'empleados.html', {
        'empleados': empleados,
        'total_nomina': total_nomina,
        'tasa_dolar': tasa_dolar
    })
