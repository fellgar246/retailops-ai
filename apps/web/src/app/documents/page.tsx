import { DocumentListPage } from '@/components/documents/DocumentListPage';
import { Suspended } from '@/components/ui/Suspended';

export default function Page() {
  return (
    <Suspended>
      <DocumentListPage />
    </Suspended>
  );
}
