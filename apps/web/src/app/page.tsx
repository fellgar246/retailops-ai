import { ApiHealthIndicator } from '@/components/ApiHealthIndicator';

export default function HomePage() {
  return (
    <main className="page">
      <section className="card">
        <p className="card__eyebrow">Foundation</p>
        <h1 className="card__title">RetailOps AI</h1>
        <p className="card__description">
          Local development environment is up. The retail catalog and sales history are
          persisted; the operations screens are not built yet.
        </p>
        <ApiHealthIndicator />
      </section>
    </main>
  );
}
