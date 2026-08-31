import { ReviewQueuePage } from '@/components/reviews/ReviewQueuePage';
import { Suspended } from '@/components/ui/Suspended';

export default function Page() {
  return (
    <Suspended>
      <ReviewQueuePage />
    </Suspended>
  );
}
