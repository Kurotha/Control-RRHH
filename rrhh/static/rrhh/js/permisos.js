document.addEventListener('DOMContentLoaded', () => {
    // Selección de los botones de aprobar/rechazar
    const botonesPermiso = document.querySelectorAll('.btn-permiso');

    botonesPermiso.forEach(boton => {
        boton.addEventListener('click', function() {
            // Extracción de datos del botón tocado
            const id = this.dataset.id;
            const accion = this.dataset.accion;
            const empleado = this.dataset.empleado;
            
            const esAprobar = accion === 'aprobar';

            // Pop-up dinámico
            Swal.fire({
                title: esAprobar ? '¿Aprobar permiso?' : '¿Rechazar permiso?',
                text: esAprobar 
                    ? `¿Confirmas la aprobación de la solicitud de ${empleado}?` 
                    : `¿Deseas rechazar la solicitud de ${empleado}? Esta acción no se puede deshacer.`,
                icon: esAprobar ? 'question' : 'warning',
                showCancelButton: true,
                confirmButtonColor: esAprobar ? '#16a34a' : '#dc2626',
                cancelButtonColor: '#64748b',
                confirmButtonText: esAprobar ? 'Sí, aprobar' : 'Sí, rechazar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    // Si confirma, inyectamos el valor en el input oculto y disparamos el submit
                    document.getElementById(`accion-permiso-${id}`).value = accion;
                    document.getElementById(`form-permiso-${id}`).submit();
                }
            });
        });
    });
});