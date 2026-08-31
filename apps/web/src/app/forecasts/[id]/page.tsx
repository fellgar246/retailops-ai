import { ForecastDetailPage } from '@/components/forecasts/ForecastDetailPage';

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ForecastDetailPage id={Number(id)} />;
}
