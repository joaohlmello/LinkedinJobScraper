/**
 * Script para gerenciar a seleção de lotes e resolver os problemas 
 * com checkboxes sendo desmarcados automaticamente
 */

// Módulo para gerenciar a seleção de lotes
window.batchSelector = (function() {
    
    /**
     * Cria um elemento DOM para um lote de URLs processado
     * 
     * @param {Object} batch - Objeto com informações do lote
     * @returns {HTMLElement} - Elemento DOM para o lote
     */
    function createBatchItem(batch) {
        const batchItem = document.createElement('div');
        batchItem.className = 'list-group-item d-flex justify-content-between align-items-center';
        
        // Verificar se o lote tem erro
        let statusClass = batch.has_error ? 'text-danger' : 'text-success';
        let statusIcon = batch.has_error ? 'bi-x-circle' : 'bi-check-circle';
        
        // Criar a data formatada se estiver disponível
        let dateInfo = '';
        if (batch.created_at) {
            try {
                const date = new Date(batch.created_at);
                dateInfo = `<small class="text-muted ms-2">${date.toLocaleString()}</small>`;
            } catch (e) {
                console.error('Erro ao formatar data:', e);
            }
        }
        
        batchItem.innerHTML = `
            <div>
                <input type="checkbox" class="batch-checkbox me-2" 
                       data-batch-index="${batch.batch_index}" 
                       ${batch.has_error ? 'disabled' : ''}>
                <span class="${statusClass}"><i class="bi ${statusIcon}"></i></span>
                Lote ${batch.batch_index + 1} (${batch.urls_count} URLs)
                ${dateInfo}
            </div>
            <div>
                <a href="/export/csv?batch_index=${batch.batch_index}" 
                   class="btn btn-sm btn-outline-success" 
                   ${batch.has_error ? 'disabled' : ''}>
                    <i class="bi bi-download"></i> CSV
                </a>
            </div>
        `;
        
        // Adicionar listener específico para evitar problemas de propagação
        const checkbox = batchItem.querySelector('.batch-checkbox');
        if (checkbox) {
            checkbox.addEventListener('change', function(e) {
                // Evitar propagação para impedir que o evento seja capturado por outros handlers
                e.stopPropagation();
            });
        }
        
        return batchItem;
    }
    
    /**
     * Exporta os lotes selecionados em formato CSV
     */
    function exportSelectedBatches() {
        // Obter todos os checkboxes marcados
        const selectedCheckboxes = document.querySelectorAll('.batch-checkbox:checked:not(:disabled)');
        
        if (selectedCheckboxes.length === 0) {
            alert('Selecione pelo menos um lote para exportar.');
            return;
        }
        
        // Coletar os índices dos lotes selecionados
        const selectedIndices = Array.from(selectedCheckboxes).map(checkbox => 
            checkbox.getAttribute('data-batch-index')
        );
        
        // Redirecionar para a rota de exportação com os índices como parâmetros
        window.location.href = `/export/csv?batch_indices=${selectedIndices.join(',')}`;
    }
    
    /**
     * Alterna a seleção de todos os checkboxes
     */
    function toggleAllCheckboxes() {
        const selectAllButton = document.getElementById('select-all-batches');
        
        // Obter todos os checkboxes não desabilitados
        const checkboxes = document.querySelectorAll('.batch-checkbox:not(:disabled)');
        
        // Verificar se todos estão marcados
        const allChecked = Array.from(checkboxes).every(checkbox => checkbox.checked);
        
        // Marcar/desmarcar todos
        checkboxes.forEach(checkbox => {
            checkbox.checked = !allChecked;
        });
        
        // Atualizar texto do botão
        if (selectAllButton) {
            selectAllButton.innerHTML = allChecked ? 
                '<i class="bi bi-check-all"></i> Selecionar todos' : 
                '<i class="bi bi-x-lg"></i> Desmarcar todos';
        }
    }
    
    // Exportar funções públicas
    return {
        createBatchItem: createBatchItem,
        exportSelectedBatches: exportSelectedBatches,
        toggleAllCheckboxes: toggleAllCheckboxes
    };
})();