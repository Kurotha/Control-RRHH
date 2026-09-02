from openpyxl import load_workbook
from django.core.management.base import BaseCommand
from rrhh.models import Empleado

class Command(BaseCommand):
    help = 'Carga de empleados desde Excel a db'

    def handle(self, *args, **kwargs):
        print("Iniciando la lectura de datos crudos...")
        ruta_archivo = 'data/raw_data.xlsx'

        try:
            workbook = load_workbook(ruta_archivo)
            sheet = workbook.active
            empleados_a_crear = [] 

            for row in sheet.iter_rows(min_row=2, values_only=True):
                # Validación simple para ignorar filas vacías
                if row[0] and row[1] and row[2] and row[3]:
                    # Lógica de negocio: Solo 'Activo/a' retorna True
                    es_activo = (row[3] == 'Activo/a')
                    
                    nuevo_empleado = Empleado(
                        nombre_completo=row[0],
                        puesto=row[1],
                        salario=row[2],
                        estado_laboral=es_activo
                    )
                    empleados_a_crear.append(nuevo_empleado)

            Empleado.objects.bulk_create(empleados_a_crear)
            print(f"Éxito: {len(empleados_a_crear)} empleados guardados.")

        except FileNotFoundError:
            print(f"Error: No se encontró el archivo {ruta_archivo}")
        except Exception as e:
            print(f"Error de ingesta: {e}")


