"""
Módulo para el manejo y cálculo de sueldos.

Provee la clase Manejo_Sueldos que permite normalizar montos
monetarios a formato Decimal y calcular el sueldo líquido
considerando el sueldo base, bonificaciones y descuentos.
"""

from decimal import Decimal, InvalidOperation


class Manejo_Sueldos:
    """
    Clase utilitaria para operaciones y cálculos monetarios.

    Incluye métodos estáticos para normalizar valores a Decimal
    (soportando tanto valores únicos como listas de montos) y para 
    calcular el salario final de un empleado.
    """

    @staticmethod
    def normalizar_montos(monto):
        """
        Normaliza uno o varios montos a tipo Decimal.

        Detecta montos ingresados como valores únicos (int, float, str)
        o como listas de valores y los convierte a objetos Decimal para
        un manejo preciso de datos monetarios. Si es una lista, aplica 
        recursividad y retorna la suma de sus elementos normalizados.

        Args:
            monto (int | float | str | Decimal | list): El monto o lista
                de montos que se desea normalizar.

        Returns:
            Decimal: El monto total normalizado. Si se ingresó una lista,
                retorna la suma de todos los montos ya normalizados.

        Raises:
            TypeError: Si el monto ingresado no puede convertirse a Decimal.
            ValueError: Si el monto ingresado es negativo.
        """
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
        """
        Calcula el sueldo final de un empleado.

        Toma el sueldo base, los bonos y los descuentos (que pueden ser
        valores únicos o listas), los normaliza a formato Decimal 
        utilizando el método `normalizar_montos`, y calcula el resultado 
        final sumando el base con los bonos y restando los descuentos.

        Args:
            sueldo_base (int | float | str | Decimal | list): El monto
                correspondiente al sueldo base del empleado.
            bonos (int | float | str | Decimal | list): El monto o la
                lista de montos correspondientes a bonificaciones extra.
            descuentos (int | float | str | Decimal | list): El monto o
                la lista de montos correspondientes a descuentos legales.

        Returns:
            Decimal: El sueldo final calculado (base + bonos - descuentos).
        """
        sueldo_base = Manejo_Sueldos.normalizar_montos(sueldo_base)
        bonos = Manejo_Sueldos.normalizar_montos(bonos)
        descuentos = Manejo_Sueldos.normalizar_montos(descuentos)
    
        sueldo = sueldo_base + bonos - descuentos
    
        return sueldo