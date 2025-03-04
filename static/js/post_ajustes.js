document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('ajusteForm');
   
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
       
        // Deshabilitar el botón de submit para evitar doble envío
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.innerHTML = 'Procesando...';
       
        // Validaciones iniciales
        const excelFile = document.getElementById('excelFile').files[0];
        const fecha = document.getElementById('fecha').value;
        const numero = document.getElementById('numero').value;
        const bodega = document.getElementById('bodega').value;
        const observaciones = document.getElementById('observaciones').value;
       
        // Validar archivo
        if (!excelFile) {
            showError('Por favor seleccione un archivo Excel');
            resetSubmitButton();
            return;
        }
       
        // Validar extensión del archivo
        if (!excelFile.name.match(/\.(xlsx|xls)$/)) {
            showError('El archivo debe ser Excel (.xlsx o .xls)');
            resetSubmitButton();
            return;
        }
       
        // Validar otros campos requeridos
        if (!fecha || !numero || !bodega) {
            showError('Por favor complete todos los campos requeridos');
            resetSubmitButton();
            return;
        }
       
        try {
            // Mostrar indicador de carga para preview
            showLoading('Procesando archivo Excel...');
           
            // Obtener preview de los datos
            const previewFormData = new FormData();
            previewFormData.append('file', excelFile);
           
            const previewResponse = await fetch('/api/preview-excel', {
                method: 'POST',
                body: previewFormData
            });
           
            const previewResult = await previewResponse.json();
            hideLoading();
           
            if (!previewResult.success) {
                throw new Error(previewResult.error);
            }
           
            // Mostrar modal de confirmación con los datos
            const result = await Swal.fire({
                title: 'Confirmar Ajustes',
                html: `
                    <div class="table-container">
                        <table class="adjustments-table">
                            <thead>
                                <tr>
                                    <th class="modal">#</th>
                                    <th class="modal1">Ítem</th>
                                    <th>Ajuste</th>
                                    <th>Costo promedio</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${previewResult.preview_data.map((adj, index) => `
                                    <tr>
                                        <td>${index+1}</td>
                                        <td class="modal1"><span>${adj.item}</span></td>
                                        <td>${adj.ajuste}</td>
                                        <td>${adj.costo}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, procesar',
                cancelButtonText: 'Cancelar',
                confirmButtonColor: '#000000',
                cancelButtonColor: '#000000',
                width: '900px',
                customClass: {
                    popup: 'custom-popup', // Estilo personalizado para el popup (fondo)
                    title: 'custom-title',  // Estilo personalizado para el título
                    content: 'custom-content', // Estilo personalizado para el contenido
                }
            });
 
            if (result.isConfirmed) {
                showLoading('Procesando ajuste de inventario...');
               
                const formData = new FormData();
                formData.append('file', excelFile);
                formData.append('fecha', fecha);
                formData.append('numero', numero);
                formData.append('bodega', bodega);
                formData.append('observaciones', observaciones);
               
                const response = await fetch('/api/inventory-adjustments', {
                    method: 'POST',
                    body: formData
                });
               
                const apiResult = await response.json();
                hideLoading();
               
                if (apiResult.success) {
                    await Swal.fire({
                        icon: 'success',
                        title: 'Éxito',
                        text: 'Ajustes de inventario guardados exitosamente',
                        timer: 2000
                    });
                    setTimeout(() => {
                        location.reload();
                    }, 2000);
                } else {
                    throw new Error(apiResult.error || 'Error desconocido al procesar el ajuste');
                }
            }
           
        } catch (error) {
            hideLoading();
            showError('Error al procesar el ajuste: ' + error.message);
        } finally {
            resetSubmitButton();
        }
    });
   
    // Mantener funciones auxiliares existentes
    function resetSubmitButton() {
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = false;
        submitButton.innerHTML = 'Enviar';
    }
   
    function showLoading(message) {
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loadingIndicator';
        loadingDiv.innerHTML = `
            <div class="loading-spinner"></div>
            <p>${message}</p>
        `;
        document.body.appendChild(loadingDiv);
    }
   
    function hideLoading() {
        const loadingDiv = document.getElementById('loadingIndicator');
        if (loadingDiv) {
            loadingDiv.remove();
        }
    }
   
    function showError(message) {
        const errorDiv = document.getElementById('errorMessages') || createMessageDiv('errorMessages');
        errorDiv.innerHTML = `<div class="alert alert-danger">${message}</div>`;
        errorDiv.scrollIntoView({ behavior: 'smooth' });
    }
   
    function createMessageDiv(id) {
        const div = document.createElement('div');
        div.id = id;
        form.insertBefore(div, form.firstChild);
        return div;
    }
});
 
document.getElementById('excelFile').addEventListener('change', function(e) {
    const fileName = e.target.files[0]?.name;
    if (fileName) {
        document.getElementById('uploadMessage').style.display = 'none';
        document.getElementById('fileSelected').style.display = 'block';
        document.getElementById('fileName').textContent = fileName;
    } else {
        document.getElementById('uploadMessage').style.display = 'block';
        document.getElementById('fileSelected').style.display = 'none';
    }
});
 
// Mantener estilos existentes
const style = document.createElement('style');
style.textContent = `
    #loadingIndicator {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        z-index: 9999;
    }
   
    .loading-spinner {
        width: 50px;
        height: 50px;
        border: 5px solid #f3f3f3;
        border-top: 5px solid #3498db;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
   
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
   
    #loadingIndicator p {
        color: white;
        margin-top: 10px;
    }
 
    .table-container {
        max-height: 340px;
        overflow-y: auto;
        margin: 10px 0;
    }
   
    .adjustments-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 10px;
    font-size: 0.875rem;
}
 
.modal1 {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 200px;
    padding: 8px;
    position: relative;
}
 
.adjustments-table td.modal1 {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 200px;
    padding: 8px;
}
 
.adjustments-table th,
.adjustments-table td {
    border: 1px solid #ddd;
    padding: 6px;
    text-align: left;
}
   
    .adjustments-table tr:nth-child(even) {
        background-color: #f9f9f9;
    }
`;
document.head.appendChild(style);