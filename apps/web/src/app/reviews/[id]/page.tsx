import { ReviewDecisionPage } from '@/components/reviews/ReviewDecisionPage';
import { Suspended } from '@/components/ui/Suspended';

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspended>
      <ReviewDecisionPage id={Number(id)} />
    </Suspended>
  );
}
