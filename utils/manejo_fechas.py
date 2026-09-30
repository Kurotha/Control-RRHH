"""
Módulo para el manejo y cálculo de fechas, feriados y días hábiles.

Provee la clase ManejoFechas que permite normalizar fechas, consultar 
feriados mediante una API externa, contar días hábiles y calcular 
diferencias en minutos.
"""

import requests
import numpy as np
from datetime import datetime


class ManejoFechas:
    """
    Clase utilitaria para operaciones y cálculos con fechas.
    
    Maneja la normalización de formatos, consulta y caché de feriados,
    y cálculos de tiempo (días hábiles y minutos).
    """

    # Se inicializa caché de datos en sistema para validar si ya se ha
    # usado antes la función de feriados para ese año.
    _cache_feriados = {}

    @staticmethod
    def normalizar_fecha(fecha) -> datetime:
        """
        Normaliza las fechas ingresadas al formato datetime.
        
        Args:
            fecha (str | datetime): La fecha a normalizar. Si es string,
                debe tener el formato 'DD-MM-YYYY HH:MM'.
                
        Returns:
            datetime: Objeto datetime normalizado.
            
        Raises:
            TypeError: Si la fecha no es de tipo str o datetime.
        """
        if isinstance(fecha, str):
            return datetime.strptime(fecha, "%d-%m-%Y %H:%M")
        elif isinstance(fecha, datetime):
            return fecha
        raise TypeError(
            f"fecha debe ser str o datetime, no {type(fecha).__name__}"
        )

    @staticmethod
    def feriados(fecha) -> np.ndarray:
        """
        Obtiene una lista de feriados para el año de la fecha indicada.
        
        Extrae el año de la fecha proporcionada y consulta la API de
        boostr.cl para obtener los feriados. Almacena los resultados 
        en caché para optimizar futuras consultas del mismo año.
        
        Args:
            fecha (str | datetime): Fecha para extraer el año a consultar.
            
        Returns:
            np.ndarray: Arreglo de NumPy con los feriados del año en
                formato 'datetime64[D]'. Si falla, retorna arreglo vacío.
        """
        fecha_norm = ManejoFechas.normalizar_fecha(fecha)
        anio = fecha_norm.year

        if anio in ManejoFechas._cache_feriados:
            return ManejoFechas._cache_feriados[anio]

        data = None
        intentos = 0

        while intentos < 3:
            url = f"https://api.boostr.cl/holidays/{anio}.json"

            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                data = response.json()["data"]

                feriados_anio = np.array(
                    [feriado["date"] for feriado in data], 
                    dtype="datetime64[D]"
                )
                ManejoFechas._cache_feriados[anio] = feriados_anio
                return feriados_anio

            except Exception as e:
                print(f"No se encontraron datos para {anio}. Error: {e}")
                data = None
                intentos += 1
                
        return np.array([], dtype="datetime64[D]")

    @staticmethod
    def contar_dias_habiles(dias_trabajados, feriado) -> int:
        """
        Cuenta la cantidad de días hábiles en una lista de días.
        
        Compara un conjunto de días trabajados contra una lista de 
        feriados (y fines de semana) para determinar cuántos de 
        esos días son efectivamente hábiles.
        
        Args:
            dias_trabajados (list): Lista de fechas trabajadas.
            feriado (np.ndarray): Arreglo de fechas feriadas.
            
        Returns:
            int: El número total de días hábiles encontrados.
        """
        trabajados = np.array(dias_trabajados, dtype="datetime64[D]")
        dias_habiles = np.is_busday(trabajados, holidays=feriado)

        return np.sum(dias_habiles)

    @staticmethod
    def contar_minutos(fecha_inicio, fecha_fin) -> float:
        """
        Calcula la cantidad de minutos transcurridos entre dos fechas.
        
        Args:
            fecha_inicio (str | datetime): Fecha y hora de inicio.
            fecha_fin (str | datetime): Fecha y hora de término.
            
        Returns:
            float: Cantidad de minutos entre ambas fechas.
            
        Raises:
            ValueError: Si la fecha de término es anterior a la de inicio.
        """
        inicio = ManejoFechas.normalizar_fecha(fecha_inicio)
        fin = ManejoFechas.normalizar_fecha(fecha_fin)

        if fin < inicio:
            raise ValueError(
                "La fecha de término no puede ser anterior a la de inicio."
            )

        diferencia = fin - inicio
        return diferencia.total_seconds() / 60