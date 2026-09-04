import requests
from datetime import datetime, timedelta

class Conversor:
    @staticmethod
    def dolar_dia(fecha) -> float:
        # Convertimos a objeto datetime si viene como string, o nos aseguramos de que sea datetime
        if isinstance(fecha, str):
            fecha_objeto = datetime.strptime(fecha, "%d-%m-%Y")
        elif hasattr(fecha, 'date'):
            fecha_objeto = datetime(fecha.year, fecha.month, fecha.day)
        else:
            fecha_objeto = fecha

        data = None
        intentos = 0 #Respaldo para evitar un bucle infinito si la API se cae por completo
        
        while data is None and intentos < 10:
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
                    # Si el dia de ingreso no hay datos, revisará el dia anterior hasta encontrar datos
                    fecha_objeto -= timedelta(days=1)
                    data = None
            except Exception as e:
                print(f"No se encontraron datos para la fecha: {fecha_str}. Error: {e}")
                fecha_objeto -= timedelta(days=1)
                data = None
                intentos += 1
                
        return 940.0  # Valor de respaldo por si falla la red tras 10 intentos

    @classmethod
    def convertir_pesos_a_dolares(cls, valor_pesos, fecha) -> float:
        """
        Usa la función inteligente 'dolar_dia' para convertir el valor ingresado.
        """
        if valor_pesos is None:
            return 0.0
            
        try:
            pesos = float(valor_pesos)
            # Llamamos a tu lógica con ciclo descendente
            tasa_dolar = cls.dolar_dia(fecha)
            
            return round(pesos / tasa_dolar, 2)
        except (ValueError, TypeError):
            return 0.0