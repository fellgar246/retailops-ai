import { Suspended } from '@/components/ui/Suspended';
import { SignInPage } from '@/components/auth/SignInPage';

export default function Page() {
  return (
    <Suspended>
      <SignInPage />
    </Suspended>
  );
}
