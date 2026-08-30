import { ApiHealthIndicator } from '@/components/ApiHealthIndicator';

export default function HomePage() {
  return (
    <main className="page">
      <section className="card">
        <p className="card__eyebrow">Block 0 · Foundation</p>
        <h1 className="card__title">RetailOps AI</h1>
        <p className="card__description">
          Local development environment is up. Retail functionality arrives in later blocks.
        </p>
        <ApiHealthIndicator />
      </section>
    </main>
  );
}
