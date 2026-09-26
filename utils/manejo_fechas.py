import requests
import numpy as np
from datetime import datetime

class Manejo_fechas:
    @staticmethod
    def normalizar_fecha(fecha):
        # función que normaliza las fechas ingresadas en formato día, mes, año, horas y minutos
        if isinstance(fecha, str):
            return datetime.strptime(fecha, "%d-%m-%Y %H:%M")
        elif isinstance(fecha, datetime):
            return fecha
        raise TypeError(f"fecha debe ser str o datetime, no {type(fecha).__name__}")
    
    @staticmethod
    def feriados(fecha):   
        # función que toma una fecha, extrae el año de esta y junto a la librería request consigue 
        # una lista de los feriados de ese año en un formato adaptado para NumPy     
        fecha = Manejo_fechas.normalizar_fecha(fecha)

        data = None
        intentos = 0
        anio = fecha.year

        while data is None and intentos < 3:
            url = f"https://apis.digital.gob.cl/fl/feriados/{anio}"

            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                data = response.json()

                return np.array([feriado["fecha"] for feriado in data],dtype="datetime64[D]")
            
            except Exception as e:
                print(f"No se encontraron datos para el año: {anio}. Error: {e}")
                data = None
                intentos += 1
        return np.array([], dtype="datetime64[D]")

    @staticmethod
    def contar_dias_habiles(dias_trabajados,feriado):
        # función que recibe una lista de días trabajados y una lista de feriados, cuenta los días que han sido hábiles 
        # y devuelve la suma de estos días
        trabajados = np.array(dias_trabajados, dtype="datetime64[D]")
        dias_habiles = np.is_busday(trabajados,holidays=feriado)

        return np.sum(dias_habiles)