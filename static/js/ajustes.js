// Establecer la fecha actual por defecto
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('fecha').value = new Date().toISOString().split('T')[0];
});

// Función para mostrar errores
function showError(message) {
    console.error(message);
    alert(message);
}

// Cargar los ajustes de inventario
function cargarAjustes() {
    fetch('/api/consultas?tipo=consecutive')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const numeroInput = document.getElementById('numero');
                
                // Establecer el siguiente número consecutivo
                numeroInput.value = data.next_consecutive;

                // Actualizar el total de ajustes
                document.getElementById('totalAjustes').textContent = `Total de ajustes: ${data.total}`;
            } else {
                showError('Error al obtener los ajustes: ' + data.error);
            }
        })
        .catch(error => {
            showError('Error al conectar con el servidor: ' + error);
        });
}

// Cargar las bodegas
function cargarBodegas() {
    fetch('/api/consultas?tipo=warehouses')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const bodegaSelect = document.getElementById('bodega');
                bodegaSelect.innerHTML = ''; // Limpiar opciones existentes
                
                data.warehouses.forEach(warehouse => {
                    const option = document.createElement('option');
                    option.value = warehouse.id;
                    option.textContent = warehouse.name;
                    bodegaSelect.appendChild(option);
                });
            } else {
                showError('Error al obtener las bodegas: ' + data.error);
            }
        })
        .catch(error => {
            showError('Error al cargar las bodegas: ' + error);
        });
}

// Inicializar la carga de datos
document.addEventListener('DOMContentLoaded', function() {
    cargarAjustes();
    cargarBodegas();
});

// Manejar el envío del formulario
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('ajusteForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = {
            numeracion: document.getElementById('numeracion').value,
            fecha: document.getElementById('fecha').value,
            numero: document.getElementById('numero').value,
            bodega: document.getElementById('bodega').value,
            observaciones: document.getElementById('observaciones').value
        };

        console.log('Datos del formulario:', formData);
        // Aquí puedes agregar la lógica para enviar los datos
    });
});