import { AuthForm } from "@/components/auth/auth-form";

export default function Page() {
  return (
    <main className="flex flex-1 items-center justify-center bg-zinc-50 px-6 py-16 dark:bg-black">
      <AuthForm intent="recruiter" mode="login" />
    </main>
  );
}
