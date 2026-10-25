export function DashboardShell({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <div>
        <p className="text-sm font-medium tracking-wide text-zinc-500 uppercase">{eyebrow}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{title}</h1>
      </div>
      {children}
    </div>
  );
}
