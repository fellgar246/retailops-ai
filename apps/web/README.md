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

The browser calls this application's own origin. A server-side route attaches
the session credential from an httpOnly cookie and forwards the request to
`API_ORIGIN`, so no page script holds a token and the image is not built for one
environment. Pages:

- Overview — forecast, document, reconciliation and review counts
- Revisiones — queue and decision workspace
- Pronósticos — run list and weekly series
- Documentos de proveedor — findings and extracted rows
- Conciliaciones — three-way match exceptions
- Evaluación de IA — acceptance, override and decided cases
- Auditoría — append-only review history
- Configuración — local reviewer identity

Loading, empty, error and stale states are first-class. A refresh keeps the
last payload on screen. Status, severity and confidence stay in separate
badges. Deterministic facts, AI proposals and human decisions are labelled
as such. The decision workspace stacks below 1200 px so 1280 px at 200 % zoom
stays usable.
