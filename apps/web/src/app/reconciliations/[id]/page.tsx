import { ReconciliationDetailPage } from '@/components/reconciliations/ReconciliationDetailPage';

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReconciliationDetailPage id={Number(id)} />;
}
