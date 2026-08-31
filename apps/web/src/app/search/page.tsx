import { SearchPage } from '@/components/search/SearchPage';
import { Suspended } from '@/components/ui/Suspended';

export default function Page() {
  return (
    <Suspended>
      <SearchPage />
    </Suspended>
  );
}
