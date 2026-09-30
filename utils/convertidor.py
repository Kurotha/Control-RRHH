"""
Módulo para la conversión de divisas mediante la API de mindicador.cl.

Provee herramientas para consultar el valor histórico del dólar en Chile
y convertir montos de pesos chilenos (CLP) a dólares (USD) según la
tasa de cambio de una fecha específica.
"""

import requests
from datetime import datetime, timedelta


class Conversor:
    """
    Clase utilitaria para manejar la conversión de moneda (CLP a USD).
    
    Permite consultar la tasa de cambio mediante una API externa,
    manejando días sin datos (fines de semana, feriados) retrocediendo
    en el calendario, e incluye un mecanismo de reintentos ante fallas.
    """

    @staticmethod
    def dolar_dia(fecha) -> float:
        """
        Obtiene el valor del dólar en Chile para una fecha específica.

        Convierte la fecha ingresada y consulta la API de mindicador.cl.
        Si no hay datos para el día especificado, busca retrospectivamente
        en el día anterior. Si la conexión falla, reintenta hasta 3 veces
        antes de devolver un valor predeterminado de respaldo.

        Args:
            fecha (str | datetime | date): La fecha a consultar. Puede
                ser un string con formato 'DD-MM-YYYY' o un objeto
                proveniente del módulo datetime.

        Returns:
            float: El valor del dólar en la fecha indicada o la fecha
                hábil anterior. En caso de fallas de red tras 3
                intentos, devuelve 940.0 como valor de rescate.
        """
        # Convertimos a objeto datetime si viene como string,
        # o nos aseguramos de que sea un objeto datetime válido.
        if isinstance(fecha, str):
            fecha_objeto = datetime.strptime(fecha, "%d-%m-%Y")
        elif hasattr(fecha, 'date'):
            fecha_objeto = datetime(fecha.year, fecha.month, fecha.day)
        else:
            fecha_objeto = fecha

        data = None
        # Respaldo para evitar bucle infinito si la API se cae por completo.
        intentos = 0
        
        while data is None and intentos < 3:
            fecha_str = fecha_objeto.strftime("%d-%m-%Y")
            url = f"https://mindicador.cl/api/dolar/{fecha_str}"
            
            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                data = response.json()
                
                if data["serie"]:
                    valor = data["serie"][0]["valor"]
                    return float(valor)
                else:
                    # Si el día de ingreso no hay datos, revisará
                    # el día anterior hasta encontrar datos válidos.
                    fecha_objeto -= timedelta(days=1)
                    data = None
                    
            except Exception as e:
                print(f"No se encontraron datos para la fecha: {fecha_str}. "
                      f"Error: {e}")
                fecha_objeto -= timedelta(days=1)
                data = None
                intentos += 1
                
        return 940.0  # Valor de respaldo por si falla la red tras 3 intentos

    @classmethod
    def convertir_pesos_a_dolares(cls, valor_pesos, fecha) -> float:
        """
        Convierte un monto de pesos chilenos a dólares.

        Utiliza el método inteligente `dolar_dia` para obtener la tasa de
        cambio correspondiente a la fecha ingresada y realiza la división.
        Si ocurren errores de tipo o valor, devuelve 0.0 de forma segura.

        Args:
            valor_pesos (float | int | str): El monto monetario en pesos
                chilenos que se desea convertir.
            fecha (str | datetime | date): La fecha asociada a la
                transacción para aplicar la tasa de cambio correcta.

        Returns:
            float: El monto equivalente en dólares, redondeado a
                dos decimales. Si el valor ingresado es nulo o 
                inválido, retorna 0.0.
        """
        if valor_pesos is None:
            return 0.0
            
        try:
            pesos = float(valor_pesos)
            # Llamamos a la lógica interna con ciclo descendente
            tasa_dolar = cls.dolar_dia(fecha)
            
            return round(pesos / tasa_dolar, 2)
        except (ValueError, TypeError):
            return 0.0