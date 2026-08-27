document.addEventListener('DOMContentLoaded', () => {
  const _csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const uploadForm = document.getElementById('receipt-upload-form');
  if (uploadForm) {
    uploadForm.addEventListener('submit', async (event) => {
      event.preventDefault();

      const formData = new FormData(uploadForm);
      const submitButton = uploadForm.querySelector('button[type="submit"]');
      const statusEl = document.getElementById('receipt-status');

      if (submitButton) {
        submitButton.disabled = true;
      }

      if (statusEl) {
        statusEl.textContent = 'Analizando factura...';
        statusEl.className = 'alert alert-info mt-3';
      }

      try {
        const response = await fetch('/receipts/parse', {
          method: 'POST',
          headers: {
            'X-CSRFToken': _csrfToken
          },
          body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || 'No se pudo analizar la factura');
        }

        renderReceiptResult(data);
      } catch (error) {
        if (statusEl) {
          statusEl.textContent = error.message;
          statusEl.className = 'alert alert-danger mt-3';
        }
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
        }
      }
    });
  }

  const resultEl = document.getElementById('receipt-result');
  if (resultEl && resultEl.dataset.receiptResult) {
    try {
      renderReceiptResult(JSON.parse(resultEl.dataset.receiptResult));
    } catch (error) {
      console.error('Receipt parse error:', error);
    }
  }
});

function renderReceiptResult(data) {
  const container = document.getElementById('receipt-review-container');
  if (!container) {
    return;
  }

  const categories = readJsonArray(container.dataset.categories);
  const paymentMethods = readJsonArray(container.dataset.paymentMethods);

  const fields = [
    ['Monto', data.total ?? data.amount],
    ['Moneda', data.currency || 'GTQ'],
    ['Comercio', data.merchant],
    ['Fecha', data.date || data.expense_date],
    ['Descripción', data.description || data.descripcion],
    ['Categoría', data.category],
    ['Método de pago', data.payment_method],
    ['Confianza', data.confidence],
  ].filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '');

  const categoryOptions = categories.length
    ? categories
        .map(
          (category) =>
            `<option value="${escapeAttribute(category)}" ${category === (data.category || '') ? 'selected' : ''}>${escapeHtml(category)}</option>`
        )
        .join('')
    : '<option value="">Sin categoría</option>';

  const paymentMethodOptions = paymentMethods.length
    ? paymentMethods
        .map(
          (method) =>
            `<option value="${escapeAttribute(method)}" ${method === (data.payment_method || '') ? 'selected' : ''}>${escapeHtml(method)}</option>`
        )
        .join('')
    : '<option value="">Sin método</option>';

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

  container.innerHTML = `
    <div class="card shadow-sm">
      <div class="card-body">
        <h4>Factura analizada</h4>
        <div class="row g-3 mb-3">
          ${fields
            .map(
              ([label, value]) => `
                <div class="col-md-6">
                  <div class="border rounded p-3 h-100">
                    <small class="text-muted d-block">${escapeHtml(label)}</small>
                    <strong>${escapeHtml(String(value))}</strong>
                  </div>
                </div>
              `
            )
            .join('')}
        </div>

        <form method="post" action="/receipts/confirm" class="mt-3">
          <input type="hidden" name="csrf_token" value="${escapeAttribute(csrfToken)}">
          <input type="hidden" name="uploaded_filename" value="${escapeAttribute(data.file || '')}">
          <input type="hidden" name="confidence" value="${escapeAttribute(data.confidence ?? '')}">

          <div class="row g-3">
            <div class="col-md-4">
              <label class="form-label">Tipo</label>
              <select name="transaction_type" class="form-select">
                <option value="expense" ${ (data.transaction_type || 'expense') === 'expense' ? 'selected' : '' }>Egreso</option>
                <option value="income" ${ (data.transaction_type || '') === 'income' ? 'selected' : '' }>Ingreso</option>
              </select>
            </div>
            <div class="col-md-4">
              <label class="form-label">Monto (Q)</label>
              <input type="number" step="0.01" class="form-control" name="total" value="${escapeAttribute(String(data.total ?? data.amount ?? ''))}">
            </div>
            <div class="col-md-4">
              <label class="form-label">Moneda</label>
              <input class="form-control" name="currency" value="${escapeAttribute(data.currency || 'GTQ')}">
            </div>

            <div class="col-md-6">
              <label class="form-label">Comercio</label>
              <input class="form-control" name="merchant" value="${escapeAttribute(data.merchant || '')}">
            </div>
            <div class="col-md-6">
              <label class="form-label">Fecha</label>
              <input type="date" class="form-control" name="expense_date" value="${escapeAttribute(data.expense_date || data.date || '')}">
            </div>
            <div class="col-12">
              <label class="form-label">Descripción</label>
              <input class="form-control" name="description" value="${escapeAttribute(data.description || data.descripcion || '')}">
            </div>
            <div class="col-md-6">
              <label class="form-label">Número de factura</label>
              <input class="form-control" name="invoice_number" value="${escapeAttribute(data.invoice_number || '')}">
            </div>
          </div>

          <div class="mb-3 mt-3">
            <label class="form-label">Categoría</label>
            <select name="category" class="form-select">
              ${categoryOptions}
            </select>
          </div>

          <div class="mb-3">
            <label class="form-label">Método de pago</label>
            <select name="payment_method" class="form-select">
              ${paymentMethodOptions}
            </select>
          </div>

          <div class="d-flex gap-2 mt-3">
            <button type="submit" class="btn btn-success">Confirmar</button>
            <a class="btn btn-secondary" href="/expenses/new">Editar</a>
            <a href="/receipts/upload" class="btn btn-link">Cancelar</a>
          </div>
        </form>
      </div>
    </div>
  `;
}

function readJsonArray(value) {
  try {
    const parsed = JSON.parse(value || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[char]));
}

function escapeAttribute(value) {
  return escapeHtml(value);
}
