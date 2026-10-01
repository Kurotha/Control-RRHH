# Control RRHH

Sistema web de gestión de recursos humanos hecho con Django. Proyecto de la asignatura Programación Back End (TI3V41), INACAP.

Integrantes: Carmen Quezada, Marllecelly Parra, Juan Carlos Parra, Kevin Garcés, Jennifer Pérez.

## Qué hace

Administra empleados, departamentos, puestos, sueldos, asistencia, permisos y evaluaciones de desempeño. Cada usuario inicia sesión con su RUT (sin puntos, con guion, por ejemplo 12345678-9) y ve el panel que corresponde a su rol:

- Empleado: ve sus datos, historial de puestos, sueldos y evaluaciones. Solicita permisos y marca entrada y salida.
- Jefe: ve a su equipo, aprueba o rechaza permisos, revisa asistencia, consulta sueldos, descarga el Excel de nómina de su equipo y gestiona evaluaciones.
- RRHH: ve toda la empresa por departamento, próximos permisos, evaluaciones pendientes, sueldos en dólares y descarga el Excel de nómina completo.

Crear, editar y eliminar registros se hace desde el admin de Django (/admin/). Los cambios sobre empleados quedan en una tabla de auditoría que no se puede editar ni borrar.

## Tecnologías

Python 3.12, Django 4.2, PostgreSQL, openpyxl, numpy, requests y python-dotenv.

## Modelo de datos

```mermaid
erDiagram
    USER |o--o| EMPLEADO : "usuario"
    EMPLEADO |o--o{ DEPARTAMENTO : "dirige"
    DEPARTAMENTO ||--o{ PUESTO : "tiene"
    EMPLEADO ||--o{ EMPLEADOPUESTO : "historial"
    PUESTO ||--o{ EMPLEADOPUESTO : "asignaciones"
    EMPLEADO ||--o{ SALARIO : "recibe"
    EMPLEADO ||--o{ ASISTENCIA : "registra"
    EMPLEADO ||--o{ PERMISO : "solicita"
    EMPLEADO ||--o{ EVALUACION : "recibe"

    USER {
        int id PK
        string username
    }
    EMPLEADO {
        string dni PK
        string nombre_empleado
        string email
        date fecha_nacimiento
        string genero
        string telefono
        string direccion
        date fecha_contratacion
        boolean estado_empleado
        string rol
        int usuario FK
    }
    DEPARTAMENTO {
        string nombre_departamento PK
        text descripcion
        decimal presupuesto
        string dni_jefe FK
    }
    PUESTO {
        int id_puesto PK
        string nombre_puesto
        string nivel
        decimal salario_base
        string nombre_departamento FK
    }
    EMPLEADOPUESTO {
        int id PK
        string dni FK
        int id_puesto FK
        date fecha_inicio_puesto
        date fecha_fin_puesto
        boolean es_actual
    }
    SALARIO {
        int id PK
        string dni FK
        string mes_anio
        decimal salario_base
        decimal bonificacion
        decimal descuentos
        decimal neto
        boolean pagado
    }
    ASISTENCIA {
        int id PK
        string dni FK
        date fecha
        time hora_entrada
        time hora_salida
        int minutos_trabajados
        string estado_asistencia
    }
    PERMISO {
        int id PK
        string dni FK
        string tipo
        date fecha_inicio_permiso
        date fecha_fin_permiso
        int dias
        boolean aprobado
    }
    EVALUACION {
        int id PK
        string dni FK
        string periodo
        int puntuacion
        text feedback
    }
    AUDITORIAEMPLEADO {
        int id PK
        string usuario_nombre
        string tabla
        string afectado
        string accion_realizada
        text detalles_cambio
        datetime fecha_modificacion
    }
```

Resumen de las tablas:

- Empleado: datos personales y rol (JEFE, RRHH o EMPLEADO). Se enlaza uno a uno con el usuario de Django, que es el que permite iniciar sesión. La clave primaria es el RUT.
- Departamento: áreas de la empresa, con presupuesto y un empleado como jefe.
- Puesto: cargos de un departamento, con nivel y salario base. No puede repetirse el nombre dentro del mismo departamento.
- EmpleadoPuesto: historial de puestos de cada empleado. Es la tabla intermedia de la relación muchos a muchos entre Empleado y Puesto.
- Salario: un registro por empleado y mes (formato MM-AAAA). El neto se calcula solo al guardar: base más bonificación menos descuentos.
- Asistencia: un registro por empleado y día. Los minutos trabajados se calculan solos al guardar.
- Permiso: solicitudes de ausencia, pendientes, aprobadas o rechazadas. Los días se calculan solos, contando solo días hábiles (sin fines de semana ni feriados).
- Evaluacion: una por empleado y semestre (formato AAAA-S1 o AAAA-S2), con puntuación de 1 a 5.
- AuditoriaEmpleado: registro de cambios hechos desde el admin. Solo permite crear registros, no editarlos ni borrarlos.

## Instalación

Se necesita Python 3.12 y Git. El proyecto usa una base PostgreSQL en línea compartida por el equipo.

1. Clonar el repositorio.

```
git clone https://github.com/Kurotha/Control-RRHH.git
cd Control-RRHH
```

2. Crear y activar un entorno virtual.

En Windows:

```
python -m venv venv
venv\Scripts\activate
```

En Linux o macOS:

```
python3 -m venv venv
source venv/bin/activate
```

3. Instalar las dependencias.

```
pip install -r requirements.txt
```

4. Crear el archivo .env en la raíz del proyecto (junto a manage.py). No está en el repositorio por seguridad: las credenciales se entregan por separado.

5. Levantar el servidor.

```
python manage.py runserver
```

La aplicación queda en http://127.0.0.1:8000/login/ y el admin en http://127.0.0.1:8000/admin/.

## Estructura

```
gestion_rrhh/   configuración del proyecto (settings, urls)
rrhh/           aplicación principal (modelos, vistas, admin, plantillas)
utils/          cálculo de fechas y feriados, sueldos y conversión de moneda
templates/      plantillas del admin personalizado
static/         estilos del admin personalizado
data/           datos de ejemplo en Excel
```

## Seguridad

Control de acceso por rol en cada vista, protección CSRF en los formularios, validación de datos en los modelos, consultas con el ORM de Django y claves fuera del código, en el archivo .env.

## Servicios externos

- mindicador.cl: valor del dólar, para mostrar sueldos en USD. El valor de cada fecha se guarda en la caché de Django durante 24 horas; si la API no responde se usa un valor de respaldo.
- boostr.cl: feriados de Chile, para contar días hábiles en los permisos.
