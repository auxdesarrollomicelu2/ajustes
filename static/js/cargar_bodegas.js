document.addEventListener('DOMContentLoaded', function() {
    // Referencias a elementos del DOM
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    const warehouseSelect = document.getElementById('warehouse');
    const searchButton = document.getElementById('searchButton');
    
    // Inicializar la carga de bodegas cuando se carga la página
    loadWarehouses();
    
    // Cargar las bodegas disponibles
    async function loadWarehouses() {
        try {
            showLoading();
            
            // Realizar la petición a la API
            const response = await fetch('/api/consultas?tipo=warehouses');
            const result = await response.json();
            
            if (result.success && result.warehouses) {
                // Limpiar opciones existentes
                warehouseSelect.innerHTML = '<option value="">Todas las bodegas</option>';
                
                // Añadir las opciones de bodegas
                result.warehouses.forEach(warehouse => {
                    const option = document.createElement('option');
                    option.value = warehouse.id;
                    option.textContent = warehouse.name;
                    warehouseSelect.appendChild(option);
                });
            } else {
                console.error('Error al cargar las bodegas:', result.error || 'Error desconocido');
            }
        } catch (error) {
            console.error('Error al cargar las bodegas:', error);
        } finally {
            hideLoading();
        }
    }
    
    // Añadir evento al botón de búsqueda
    searchButton.addEventListener('click', function() {
        loadFilteredInvoices();
    });
    
    // Función para cargar facturas con filtros aplicados
    async function loadFilteredInvoices() {
        try {
            showLoading();
            
            // Obtener los valores de los filtros
            const startDate = startDateInput.value;
            const endDate = endDateInput.value;
            const warehouseId = warehouseSelect.value;
            
            // Construir la URL con los parámetros
            let url = '/api/facturas?metadata=true&expand=client,items,warehouse';
            url += `&start=${currentPage * pageSize}`;
            url += `&limit=${pageSize}`;
            
            // Añadir los filtros si están presentes
            if (startDate) url += `&startDate=${startDate}`;
            if (endDate) url += `&endDate=${endDate}`;
            if (warehouseId) url += `&warehouseId=${warehouseId}`;
            
            // Realizar la petición
            const response = await fetch(url);
            const result = await response.json();
            
            if (result.success) {
                // Actualizar la tabla con los resultados
                renderInvoicesTable(result.data);
                
                // Actualizar el contador
                totalInvoices = result.metadata.total || 0;
                document.getElementById('totalInvoices').textContent = totalInvoices;
                
                // Actualizar la paginación
                updatePagination();
            } else {
                showError('Error al cargar las facturas: ' + (result.error || 'Error desconocido'));
            }
        } catch (error) {
            showError('Error: ' + error.message);
        } finally {
            hideLoading();
        }
    }
    
    // Modificar la función de carga inicial para incluir los filtros
    // (asegúrate de reemplazar o modificar la función loadInvoices existente)
    async function loadInvoices() {
        try {
            showLoading();
            
            // Incluir también los filtros de fecha y bodega
            const startDate = startDateInput.value;
            const endDate = endDateInput.value;
            const warehouseId = warehouseSelect.value;
            
            // Resto del código existente...
            let url = '/api/facturas?metadata=true&expand=client,items,warehouse';
            // ...
            
            // Añadir los filtros si están presentes
            if (startDate) url += `&startDate=${startDate}`;
            if (endDate) url += `&endDate=${endDate}`;
            if (warehouseId) url += `&warehouseId=${warehouseId}`;
            
            // El resto de la función original...
        } catch (error) {
            // Manejo de errores existente...
        } finally {
            hideLoading();
        }
    }
    
    // Configurar tecla Enter en los campos de fecha para realizar la búsqueda
    startDateInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            loadFilteredInvoices();
        }
    });
    
    endDateInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            loadFilteredInvoices();
        }
    });
});