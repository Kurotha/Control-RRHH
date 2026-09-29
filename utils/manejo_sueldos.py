from decimal import Decimal, InvalidOperation

class Manejo_Sueldos:

    @staticmethod
    def normalizar_montos(monto):
        # Función que detecta montos ingresados tanto como lista o como valores únicos y los normaliza a decimal 
        # para el manejo de datos monetarios
        if isinstance(monto, list):
            return sum(
                Manejo_Sueldos.normalizar_montos(valor)
                for valor in monto
            )
        
        try:
            monto = Decimal(str(monto))

        except (InvalidOperation, ValueError, TypeError):
            raise TypeError(f"El monto '{monto}' no es válido")
        
        if monto < 0:
            raise ValueError("El monto no puede ser negativo")
        return monto

    @staticmethod
    def calcular_sueldo(sueldo_base, bonos, descuentos):
        # función sencilla que toma datos únicos o listas para sumar los sueldos bases con los bonos y descuentos respectivos
        sueldo_base = Manejo_Sueldos.normalizar_montos(sueldo_base)
        bonos = Manejo_Sueldos.normalizar_montos(bonos)
        descuentos = Manejo_Sueldos.normalizar_montos(descuentos)
    
        sueldo = sueldo_base + bonos - descuentos
    
        return sueldo