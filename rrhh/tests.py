from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Empleado, AuditoriaEmpleado


class EmpleadoModelTest(TestCase):
    """Pruebas para el modelo Empleado y sus especificaciones de rúbrica."""

    def setUp(self):
        # Crear empleados con distintos salarios para probar ordenamiento
        self.emp1 = Empleado.objects.create(
            nombre_completo="Ana Lopez",
            puesto="Desarrolladora Python",
            salario=3000.0,
            estado_laboral=True
        )
        self.emp2 = Empleado.objects.create(
            nombre_completo="Carlos Ruiz",
            puesto="Gerente Técnico",
            salario=5000.0,
            estado_laboral=True
        )
        self.emp3 = Empleado.objects.create(
            nombre_completo="Beatriz Soto",
            puesto="Contadora",
            salario=2500.0,
            estado_laboral=False
        )

    def test_str_representation(self):
        """Verifica que el método __str__ retorne el nombre completo."""
        self.assertEqual(str(self.emp1), "Ana Lopez")

    def test_ordering_by_salary_descending(self):
        """Verifica que los empleados se ordenen de mayor a menor salario (Meta ordering)."""
        empleados = list(Empleado.objects.all())
        # El primero debe ser Carlos (5000), luego Ana (3000), luego Beatriz (2500)
        self.assertEqual(empleados[0], self.emp2)
        self.assertEqual(empleados[1], self.emp1)
        self.assertEqual(empleados[2], self.emp3)


class EmpleadoViewTest(TestCase):
    """Pruebas para la vista de listado de empleados y cálculo de nómina."""

    def setUp(self):
        self.client = Client()
        # Empleado activo
        Empleado.objects.create(
            nombre_completo="Mariana Gomez",
            puesto="Diseñadora UI",
            salario=2000.0,
            estado_laboral=True
        )
        # Empleado inactivo (no debe sumarse a total_nomina)
        Empleado.objects.create(
            nombre_completo="Roberto Diaz",
            puesto="Analista QA",
            salario=1500.0,
            estado_laboral=False
        )

    def test_view_status_and_template(self):
        """Verifica código HTTP 200 y uso de template correcto."""
        response = self.client.get(reverse('listar_empleados'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'empleados.html')

    def test_nomina_calculation(self):
        """Verifica que la nómina total sume únicamente empleados activos."""
        response = self.client.get(reverse('listar_empleados'))
        # Solo Mariana está activa (2000.0)
        self.assertEqual(response.context['total_nomina'], 2000.0)

    def test_template_classes(self):
        """Verifica que en el HTML aparezcan las clases para texto activo e inactivo."""
        response = self.client.get(reverse('listar_empleados'))
        contenido = response.content.decode('utf-8')
        self.assertIn('empleado-activo', contenido)
        self.assertIn('empleado-inactivo', contenido)


class AuditoriaEmpleadoAdminTest(TestCase):
    """Pruebas para la funcionalidad de auditoría automática en Django Admin."""

    def setUp(self):
        # Crear superusuario para operar en el admin
        self.admin_user = User.objects.create_superuser(
            username='admin_rrhh',
            email='admin@rrhh.com',
            password='Password123'
        )
        self.client = Client()
        self.client.login(username='admin_rrhh', password='Password123')

        # Crear empleado base
        self.empleado = Empleado.objects.create(
            nombre_completo="Pedro Morales",
            puesto="Soporte TI",
            salario=1800.0,
            estado_laboral=True
        )

    def test_creacion_empleado_genera_auditoria(self):
        """Crear un empleado a través del admin debe generar un registro de auditoría de CREACION."""
        url_add = reverse('admin:rrhh_empleado_add')
        data = {
            'nombre_completo': 'Lucia Fernandez',
            'puesto': 'Scrum Master',
            'salario': '3200.0',
            'estado_laboral': 'on',
            'auditoriaempleado_set-TOTAL_FORMS': '0',
            'auditoriaempleado_set-INITIAL_FORMS': '0',
            'auditoriaempleado_set-MIN_NUM_FORMS': '0',
            'auditoriaempleado_set-MAX_NUM_FORMS': '1000',
        }
        response = self.client.post(url_add, data, follow=True)
        self.assertEqual(response.status_code, 200)

        lucia = Empleado.objects.get(nombre_completo='Lucia Fernandez')
        auditoria = AuditoriaEmpleado.objects.filter(empleado=lucia).first()

        self.assertIsNotNone(auditoria)
        self.assertEqual(auditoria.accion_realizada, 'CREACION')
        self.assertEqual(auditoria.usuario_modificador, self.admin_user)
        self.assertIn('3200', auditoria.detalles_cambio)

    def test_modificacion_salario_genera_auditoria_edicion(self):
        """Modificar el salario a través del admin debe registrar la diferencia en la auditoría."""
        url_change = reverse('admin:rrhh_empleado_change', args=[self.empleado.pk])
        data = {
            'nombre_completo': self.empleado.nombre_completo,
            'puesto': self.empleado.puesto,
            'salario': '2400.0',  # Aumento de 1800 a 2400
            'estado_laboral': 'on',
            'auditoriaempleado_set-TOTAL_FORMS': '0',
            'auditoriaempleado_set-INITIAL_FORMS': '0',
            'auditoriaempleado_set-MIN_NUM_FORMS': '0',
            'auditoriaempleado_set-MAX_NUM_FORMS': '1000',
        }
        response = self.client.post(url_change, data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Refrescamos de BD
        self.empleado.refresh_from_db()
        self.assertEqual(self.empleado.salario, 2400.0)

        auditoria = AuditoriaEmpleado.objects.filter(
            empleado=self.empleado,
            accion_realizada='EDICION'
        ).latest('fecha_modificacion')

        self.assertIsNotNone(auditoria)
        self.assertEqual(auditoria.usuario_modificador, self.admin_user)
        self.assertIn('1800', auditoria.detalles_cambio)
        self.assertIn('2400', auditoria.detalles_cambio)

    def test_desactivacion_empleado_genera_auditoria_desactivacion(self):
        """Desactivar a un empleado (estado_laboral=False) debe categorizarse como DESACTIVACION."""
        url_change = reverse('admin:rrhh_empleado_change', args=[self.empleado.pk])
        data = {
            'nombre_completo': self.empleado.nombre_completo,
            'puesto': self.empleado.puesto,
            'salario': str(self.empleado.salario),
            # Sin 'estado_laboral' para desmarcar el checkbox (False)
            'auditoriaempleado_set-TOTAL_FORMS': '0',
            'auditoriaempleado_set-INITIAL_FORMS': '0',
            'auditoriaempleado_set-MIN_NUM_FORMS': '0',
            'auditoriaempleado_set-MAX_NUM_FORMS': '1000',
        }
        response = self.client.post(url_change, data, follow=True)
        self.assertEqual(response.status_code, 200)

        self.empleado.refresh_from_db()
        self.assertFalse(self.empleado.estado_laboral)

        auditoria = AuditoriaEmpleado.objects.filter(
            empleado=self.empleado,
            accion_realizada='DESACTIVACION'
        ).latest('fecha_modificacion')

        self.assertIsNotNone(auditoria)
        self.assertEqual(auditoria.usuario_modificador, self.admin_user)
        self.assertIn('desactivado', auditoria.detalles_cambio.lower())

