document.addEventListener('DOMContentLoaded', () => {
    const botonesAsistencia = document.querySelectorAll('.btn-asistencia');
    const formAsistencia = document.getElementById('form-asistencia');
    const inputAccion = document.getElementById('accion-asistencia');

    botonesAsistencia.forEach(boton => {
        boton.addEventListener('click', function() {
            // Lectura de estado desde los atributos data- de HTML5
            const tipo = this.dataset.tipo;
            const horaRegistrada = this.dataset.hora;
            const tieneEntrada = this.dataset.tieneEntrada;

            // 1. Validaciones preventivas
            if (tipo === 'entrada' && horaRegistrada) {
                mostrarAlertaInfo('Entrada ya registrada', `Ya marcaste tu entrada hoy a las ${horaRegistrada} hrs.`);
                return;
            }

            if (tipo === 'salida') {
                if (tieneEntrada === 'false') {
                    mostrarAlertaError('Acción no permitida', 'Debes marcar tu entrada antes de poder registrar tu salida.');
                    return;
                }
                if (horaRegistrada) {
                    mostrarAlertaInfo('Salida ya registrada', `Ya marcaste tu salida hoy a las ${horaRegistrada} hrs.`);
                    return;
                }
            }

            // 2. Pop-up de confirmación de acción
            Swal.fire({
                title: `¿Registrar ${tipo}?`,
                text: `Se guardará tu ${tipo} con la hora actual del servidor.`,
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: tipo === 'entrada' ? '#16a34a' : '#7c3aed',
                cancelButtonColor: '#64748b',
                confirmButtonText: 'Sí, registrar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    inputAccion.value = `marcar_${tipo}`;
                    formAsistencia.submit();
                }
            });
        });
    });

    // Funciones auxiliares (DRY)
    function mostrarAlertaInfo(titulo, texto) {
        Swal.fire({ icon: 'info', title: titulo, text: texto, confirmButtonColor: '#7c3aed' });
    }

    function mostrarAlertaError(titulo, texto) {
        Swal.fire({ icon: 'warning', title: titulo, text: texto, confirmButtonColor: '#7c3aed' });
    }
});