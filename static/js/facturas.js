document.addEventListener('DOMContentLoaded', function() {
    // Referencias a elementos del DOM
    const applyFiltersBtn = document.getElementById('applyFilters');
    const clearFiltersBtn = document.getElementById('clearFilters');
    const refreshInvoicesBtn = document.getElementById('refreshInvoices');
    const prevPageBtn = document.getElementById('prevPage');
    const nextPageBtn = document.getElementById('nextPage');
    const toggleFiltersBtn = document.getElementById('toggleFilters');
    const filtersContainer = document.getElementById('filtersContainer');
    
    // Variables globales
    let currentPage = 0;
    let pageSize = 30;
    let totalInvoices = 0;
    
    // Mostrar/ocultar filtros
    toggleFiltersBtn.addEventListener('click', function() {
        filtersContainer.style.display = filtersContainer.style.display === 'none' || filtersContainer.style.display === '' ? 'block' : 'none';
    });
    
    // Cargar facturas
    async function loadInvoices() {
        try {
            showLoading();
            
            // Obtener valores de los filtros
            const status = document.getElementById('status').value;
            const date = document.getElementById('date').value;
            const dueDate = document.getElementById('dueDate').value;
            const clientName = document.getElementById('client_name').value;
            const clientIdentification = document.getElementById('client_identification').value;
            const orderField = document.getElementById('order_field').value;
            const orderDirection = document.getElementById('order_direction').value;
            pageSize = parseInt(document.getElementById('limit').value) || 30;
            
            // Construir URL con parámetros
            let url = '/api/facturas?metadata=true&expand=client,items,warehouse';
            url += `&start=${currentPage * pageSize}`;
            url += `&limit=${pageSize}`;
            url += `&order_field=${orderField}`;
            url += `&order_direction=${orderDirection}`;
            
            if (status) url += `&status=${status}`;
            if (date) url += `&date=${date}`;
            if (dueDate) url += `&dueDate=${dueDate}`;
            if (clientName) url += `&client_name=${encodeURIComponent(clientName)}`;
            if (clientIdentification) url += `&client_identification=${encodeURIComponent(clientIdentification)}`;
            
            // Realizar la petición
            const response = await fetch(url);
            const result = await response.json();
            
            if (result.success) {
                // Para depuración - ver la estructura real de los datos
                console.log("Datos de facturas:", result.data);
                
                // Actualizar la tabla
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
    
    // Renderizar la tabla de facturas
    function renderInvoicesTable(invoices) {
        const invoicesTable = document.getElementById('invoicesTable');
        invoicesTable.innerHTML = '';
        
        if (!invoices || invoices.length === 0) {
            invoicesTable.innerHTML = `
                <tr>
                    <td colspan="10" class="text-center p-4">
                        <i class="bi bi-exclamation-circle me-2"></i>
                        No se encontraron facturas con los filtros aplicados
                    </td>
                </tr>
            `;
            return;
        }
        
        // Para la primera factura, mostrar su estructura para depuración
        if (invoices.length > 0) {
            console.log("Estructura de la primera factura:", JSON.stringify(invoices[0], null, 2));
        }
        
        invoices.forEach(invoice => {
            // Determinar clase para el estado
            let statusClass = 'badge-status ';
            switch (invoice.status) {
                case 'open': statusClass += 'badge-open'; break;
                case 'closed': statusClass += 'badge-closed'; break;
                case 'draft': statusClass += 'badge-draft'; break;
                case 'void': statusClass += 'badge-void'; break;
            }
            
            // Mapear nombres de estados a español
            let statusText = {
                'open': 'Abierta',
                'closed': 'Cerrada',
                'draft': 'Borrador',
                'void': 'Anulada'
            }[invoice.status] || invoice.status;
            
            // Formatear fechas
            const formatDate = dateStr => {
                if (!dateStr) return '';
                const date = new Date(dateStr);
                return date.toLocaleDateString('es-ES');
            };
            
            // Formatear valores monetarios
            const formatCurrency = value => {
                if (value === undefined || value === null) return '';
                return new Intl.NumberFormat('es-CO', {
                    style: 'currency',
                    currency: invoice.currency || 'COP',
                    minimumFractionDigits: 0
                }).format(value);
            };
            
            // Extraer información de bodega de manera segura
            let warehouseName = 'Principal';
            if (invoice.warehouse) {
                warehouseName = invoice.warehouse.name || invoice.warehouse.id || 'Principal';
            }
            
            // Extraer información del cliente
            let clientInfo = '';
            if (invoice.client) {
                clientInfo = invoice.client.name || '';
                
                // Añadir identificación si está disponible
                if (invoice.client.identificationObject) {
                    const idType = invoice.client.identificationObject.type || '';
                    const idNumber = invoice.client.identificationObject.number || '';
                    if (idType && idNumber) {
                        clientInfo += ` (${idType}: ${idNumber})`;
                    }
                }
            }
            
            // Extraer información del primer ítem (si existe)
            let firstItemInfo = '';
            if (invoice.items && invoice.items.length > 0) {
                const firstItem = invoice.items[0];
                firstItemInfo = firstItem.name || '';
                if (firstItem.description) {
                    firstItemInfo += ` - ${firstItem.description}`;
                }
            }
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${invoice.numberTemplate?.fullNumber || invoice.id}</td>
                <td>${formatDate(invoice.date)}</td>
                <td>${formatDate(invoice.dueDate)}</td>
                <td>${clientInfo}</td>
                <td>${warehouseName}</td>
                <td>${firstItemInfo}</td>
                <td><span class="badge ${statusClass}">${statusText}</span></td>
                <td>${formatCurrency(invoice.total)}</td>
                <td>${formatCurrency(invoice.balance)}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary view-invoice" data-id="${invoice.id}">
                        <i class="bi bi-eye"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-success download-invoice" data-id="${invoice.id}">
                        <i class="bi bi-download"></i>
                    </button>
                </td>
            `;
            
            invoicesTable.appendChild(row);
        });
        
        // Agregar eventos a los botones de acciones
        document.querySelectorAll('.view-invoice').forEach(btn => {
            btn.addEventListener('click', () => {
                const invoiceId = btn.getAttribute('data-id');
                viewInvoiceDetails(invoiceId);
            });
        });
        
        document.querySelectorAll('.download-invoice').forEach(btn => {
            btn.addEventListener('click', () => {
                const invoiceId = btn.getAttribute('data-id');
                downloadInvoice(invoiceId);
            });
        });
    }
    
    // Ver detalles de factura
    async function viewInvoiceDetails(invoiceId) {
        try {
            showLoading();
            
            // Obtener detalles de la factura
            const response = await fetch(`/api/facturas?id=${invoiceId}&expand=client,items,warehouse`);
            const result = await response.json();
            
            if (result.success && result.data) {
                const invoice = Array.isArray(result.data) ? result.data[0] : result.data;
                
                console.log("Detalles de factura:", JSON.stringify(invoice, null, 2));
                
                // Crear HTML para los productos
                let productsHtml = '';
                if (invoice.items && invoice.items.length > 0) {
                    productsHtml = '<table class="table table-sm mt-3">';
                    productsHtml += '<thead><tr><th>Código</th><th>Producto</th><th>Descripción</th><th>Cantidad</th><th>Precio</th><th>Total</th></tr></thead>';
                    productsHtml += '<tbody>';
                    
                    invoice.items.forEach(item => {
                        // Extraer el código del producto de manera segura
                        const itemCode = item.id || '';
                        
                        productsHtml += `<tr>
                            <td>${itemCode}</td>
                            <td>${item.name || ''}</td>
                            <td>${item.description || ''}</td>
                            <td>${item.quantity || 0}</td>
                            <td>${new Intl.NumberFormat('es-CO', {
                                style: 'currency',
                                currency: invoice.currency || 'COP'
                            }).format(item.price || 0)}</td>
                            <td>${new Intl.NumberFormat('es-CO', {
                                style: 'currency',
                                currency: invoice.currency || 'COP'
                            }).format((item.price * item.quantity) || 0)}</td>
                        </tr>`;
                    });
                    
                    productsHtml += '</tbody></table>';
                } else {
                    productsHtml = '<p class="text-muted">No hay productos en esta factura.</p>';
                }
                
                // Extraer información de bodega de manera segura
                let warehouseInfo = 'Principal';
                if (invoice.warehouse) {
                    warehouseInfo = `${invoice.warehouse.name || 'Sin nombre'} (ID: ${invoice.warehouse.id || 'N/A'})`;
                }
                
                // Extraer información del cliente
                let clientInfo = '';
                if (invoice.client) {
                    clientInfo = invoice.client.name || '';
                    
                    // Añadir identificación si está disponible
                    if (invoice.client.identificationObject) {
                        const idType = invoice.client.identificationObject.type || '';
                        const idNumber = invoice.client.identificationObject.number || '';
                        if (idType || idNumber) {
                            clientInfo += `<br>Identificación: ${idType} ${idNumber}`;
                        }
                    }
                }
                
                // Mostrar modal con detalles
                Swal.fire({
                    title: `Factura ${invoice.numberTemplate?.fullNumber || invoice.id}`,
                    html: `
                        <div class="text-start">
                            <p><strong>Cliente:</strong> ${clientInfo}</p>
                            <p><strong>Fecha:</strong> ${new Date(invoice.date).toLocaleDateString('es-ES')}</p>
                            <p><strong>Bodega:</strong> ${warehouseInfo}</p>
                            <p><strong>Estado:</strong> ${
                                {
                                    'open': 'Abierta',
                                    'closed': 'Cerrada',
                                    'draft': 'Borrador',
                                    'void': 'Anulada'
                                }[invoice.status] || invoice.status
                            }</p>
                            <hr>
                            <h5>Productos</h5>
                            ${productsHtml}
                            <hr>
                            <div class="text-end">
                                <p><strong>Subtotal:</strong> ${new Intl.NumberFormat('es-CO', {
                                    style: 'currency',
                                    currency: invoice.currency || 'COP'
                                }).format(invoice.subtotal || 0)}</p>
                                <p><strong>Impuestos:</strong> ${new Intl.NumberFormat('es-CO', {
                                    style: 'currency',
                                    currency: invoice.currency || 'COP'
                                }).format(invoice.totalTaxes || 0)}</p>
                                <p><strong>Total:</strong> ${new Intl.NumberFormat('es-CO', {
                                    style: 'currency',
                                    currency: invoice.currency || 'COP'
                                }).format(invoice.total || 0)}</p>
                            </div>
                        </div>
                    `,
                    width: '800px',
                    confirmButtonText: 'Cerrar'
                });
            } else {
                showError('Error al obtener detalles de la factura: ' + (result.error || 'Error desconocido'));
            }
        } catch (error) {
            showError('Error: ' + error.message);
        } finally {
            hideLoading();
        }
    }
    
    // Descargar factura
    async function downloadInvoice(invoiceId) {
        try {
            showLoading();
            
            // Construir URL para descargar la factura
            const url = `/api/facturas?id=${invoiceId}&download=true`;
            
            // Realizar la petición
            const response = await fetch(url);
            const result = await response.json();
            
            if (result.success && result.data) {
                // Abrir la URL del PDF en una nueva pestaña
                window.open(result.data, '_blank');
            } else {
                showError('Error al descargar la factura: ' + (result.error || 'Error desconocido'));
            }
        } catch (error) {
            showError('Error: ' + error.message);
        } finally {
            hideLoading();
        }
    }
    
    // Actualizar paginación
    function updatePagination() {
        const startItem = currentPage * pageSize + 1;
        const endItem = Math.min((currentPage + 1) * pageSize, totalInvoices);
        
        document.getElementById('pageInfo').textContent = `Mostrando ${startItem}-${endItem} de ${totalInvoices}`;
        
        // Habilitar/deshabilitar botones de paginación
        prevPageBtn.disabled = currentPage === 0;
        nextPageBtn.disabled = endItem >= totalInvoices;
    }
    
    // Mostrar mensaje de error
    function showError(message) {
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: message,
            confirmButtonColor: '#3085d6'
        });
    }
    
    // Mostrar/ocultar indicador de carga
    function showLoading() {
        document.getElementById('loading').style.display = 'flex';
    }
    
    function hideLoading() {
        document.getElementById('loading').style.display = 'none';
    }
});