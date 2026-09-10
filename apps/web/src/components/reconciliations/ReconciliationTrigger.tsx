'use client';

import { useState } from 'react';

import { TriggerPanel } from '@/components/jobs/TriggerPanel';
import { startReconciliation } from '@/lib/api';

export function ReconciliationTrigger({ onSettled }: { onSettled?: () => void }) {
  const [supplier, setSupplier] = useState('');
  const [invoice, setInvoice] = useState('');

  return (
    <TriggerPanel
      description="Cotejo a tres vías entre pedido, recepción y factura. Se ejecuta en segundo plano."
      onSettled={onSettled}
      resultHref={(job) =>
        job.result?.reconciliation_run_id
          ? `/reconciliations/${String(job.result.reconciliation_run_id)}`
          : undefined
      }
      resultLabel="Ver conciliación"
      start={() => startReconciliation({ supplier: supplier.trim(), invoice: invoice.trim() })}
      submitLabel="Conciliar"
      title="Conciliar una factura"
    >
      <div className="field">
        <label htmlFor="rec-supplier">Proveedor</label>
        <input
          id="rec-supplier"
          onChange={(event) => setSupplier(event.target.value)}
          placeholder="SUP-BEVCO"
          required
          value={supplier}
        />
      </div>
      <div className="field">
        <label htmlFor="rec-invoice">Factura</label>
        <input
          id="rec-invoice"
          onChange={(event) => setInvoice(event.target.value)}
          placeholder="INV-1001"
          required
          value={invoice}
        />
      </div>
    </TriggerPanel>
  );
}
