import { LogoutButton } from "@/components/auth/logout-button";
import { requireAdminAccess } from "@/lib/auth/guard";
import { appConfig } from "@/lib/config";

export default async function AdminPage() {
  await requireAdminAccess();
  return (
    <div className="flex flex-1 flex-col bg-zinc-50 dark:bg-black">
      <header className="border-b border-zinc-200 bg-white px-6 py-4 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between">
          <p className="text-sm font-medium">{appConfig.name}</p>
          <LogoutButton />
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
        <p className="text-sm font-medium tracking-wide text-zinc-500 uppercase">Platform admin</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Administration</h1>
        <p className="mt-4 text-zinc-600 dark:text-zinc-400">
          Controlled administrative access. Assign this role with the service role
          (`app_metadata.role` and `public.users.role`); it is not available as self-serve signup.
        </p>
      </main>
    </div>
  );
}
