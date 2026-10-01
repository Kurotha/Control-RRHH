"""
Módulo para la conversión de divisas mediante la API de mindicador.cl.

Implementa un sistema de consulta con caché en memoria utilizando las
herramientas nativas de Django para optimizar los tiempos de respuesta
y prevenir bloqueos del servidor por latencia de red.
"""

from datetime import datetime, timedelta

import requests
from django.core.cache import cache


class Conversor:
    """
    Clase utilitaria para manejar la conversión de moneda (CLP a USD).

    Provee métodos estáticos y de clase para obtener tasas de cambio
    históricas o actuales, integrando tolerancia a fallos (fail-fast)
    y respaldo de datos temporales en memoria caché.
    """

    @staticmethod
    def dolar_dia(fecha) -> float:
        """
        Obtiene el valor del dólar consultando la caché o la API externa.

        Convierte la fecha ingresada a formato de texto y verifica si
        existe un registro válido en la memoria caché de Django. Si no hay
        aciertos, realiza hasta dos peticiones HTTP a la API con un tiempo
        máximo de espera de 2 segundos. Si la fecha es inhábil o la red
        falla, retrocede un día en el calendario de forma iterativa.

        Args:
            fecha (str | datetime.date | datetime.datetime): La fecha a
                consultar. Acepta formato de texto 'DD-MM-YYYY' o un
                objeto nativo de fecha de Python.

        Returns:
            float: El valor de conversión del dólar para el día consultado.
                En caso de fallo total o desconexión externa, devuelve
                980.0 como tasa predeterminada de respaldo.
        """
        if isinstance(fecha, str):
            fecha_objeto = datetime.strptime(fecha, "%d-%m-%Y")
        elif hasattr(fecha, 'date'):
            fecha_objeto = datetime(fecha.year, fecha.month, fecha.day)
        else:
            fecha_objeto = fecha

        fecha_str = fecha_objeto.strftime("%d-%m-%Y")
        cache_key = f"tasa_dolar_{fecha_str}"

        tasa_guardada = cache.get(cache_key)
        if tasa_guardada:
            return tasa_guardada

        data = None
        intentos = 0

        while data is None and intentos < 2:
            fecha_consulta = fecha_objeto.strftime('%d-%m-%Y')
            url = f"https://mindicador.cl/api/dolar/{fecha_consulta}"

            try:
                response = requests.get(url, timeout=2)
                response.raise_for_status()
                data = response.json()

                if data.get("serie"):
                    valor = float(data["serie"][0]["valor"])
                    cache.set(cache_key, valor, 86400)
                    return valor
                else:
                    fecha_objeto -= timedelta(days=1)
                    data = None

            except Exception as e:
                print(f"Falla API para {fecha_consulta}: {e}")
                fecha_objeto -= timedelta(days=1)
                data = None
                intentos += 1

        return 980.0

    @classmethod
    def convertir_pesos_a_dolares(cls, valor_pesos, fecha) -> float:
        """
        Convierte un monto monetario de pesos chilenos (CLP) a dólares (USD).

        Delega la obtención de la tasa de cambio al método interno
        dolar_dia y realiza la división aritmética, aplicando un redondeo
        a dos posiciones decimales. Incorpora validación estructural para
        prevenir interrupciones de ejecución por tipos inválidos.

        Args:
            valor_pesos (float | int | str): El monto a convertir en pesos.
            fecha (str | datetime.date | datetime.datetime): La fecha
                exacta de la transacción para aplicar la tasa
                histórica correspondiente.

        Returns:
            float: El valor equivalente en dólares. Si los parámetros
                son nulos o el formato monetario no puede ser procesado,
                devuelve 0.0.
        """
        if valor_pesos is None:
            return 0.0

        try:
            pesos = float(valor_pesos)
            tasa_dolar = cls.dolar_dia(fecha)
            return round(pesos / tasa_dolar, 2)
        except (ValueError, TypeError):
            return 0.0