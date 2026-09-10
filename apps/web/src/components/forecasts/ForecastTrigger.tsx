'use client';

import { useState } from 'react';

import { TriggerPanel } from '@/components/jobs/TriggerPanel';
import { startForecast } from '@/lib/api';

export function ForecastTrigger({ onSettled }: { onSettled?: () => void }) {
  const [horizon, setHorizon] = useState(4);

  return (
    <TriggerPanel
      description="Evalúa las líneas base sobre el histórico de ventas ya cargado."
      onSettled={onSettled}
      resultHref={(job) =>
        job.result?.forecast_run_id ? `/forecasts/${String(job.result.forecast_run_id)}` : undefined
      }
      resultLabel="Ver ejecución"
      start={() => startForecast({ horizon })}
      submitLabel="Evaluar"
      title="Evaluar la demanda"
    >
      <div className="field">
        <label htmlFor="fc-horizon">Horizonte (semanas)</label>
        <input
          id="fc-horizon"
          max={26}
          min={1}
          onChange={(event) => setHorizon(Number(event.target.value))}
          type="number"
          value={horizon}
        />
      </div>
    </TriggerPanel>
  );
}
