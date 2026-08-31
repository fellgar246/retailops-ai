# RetailOps AI — Web

Operations console for the local RetailOps stack.

```bash
npm install
npm run dev          # http://localhost:3000
npm test
npm run lint
npm run typecheck
npm run build
```

The shell reads the API configured by `NEXT_PUBLIC_API_BASE_URL`. Pages:

- Overview — forecast, document, reconciliation and review counts
- Revisiones — queue and decision workspace
- Pronósticos — run list and weekly series
- Documentos de proveedor — findings and extracted rows
- Conciliaciones — three-way match exceptions
- Evaluación de IA — acceptance, override and decided cases
- Auditoría — append-only review history
- Configuración — local reviewer identity

Loading, empty and error states are first-class. Status, severity and
confidence stay in separate badges. Deterministic facts, AI proposals and
human decisions are labelled as such.
