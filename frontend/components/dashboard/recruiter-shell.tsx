"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { LogoutButton } from "@/components/auth/logout-button";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { appConfig } from "@/lib/config";
import { COMPANY_NAV, isDashboardNavActive } from "@/lib/dashboard/nav";
import { cn } from "@/lib/utils";

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1">
      {COMPANY_NAV.map((item) => {
        const active = isDashboardNavActive(item.href, pathname);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={cn(
              "rounded-lg px-3 py-2 text-sm",
              active
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function RecruiterShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex min-h-full flex-1 bg-zinc-50 dark:bg-black">
      <aside className="hidden w-64 shrink-0 overflow-y-auto border-r border-zinc-200 bg-white p-4 md:flex md:flex-col dark:border-zinc-800 dark:bg-zinc-950">
        <Link href="/dashboard" className="mb-6 px-3 text-sm font-semibold">
          {appConfig.name}
        </Link>
        <p className="mb-3 px-3 text-xs font-medium tracking-wide text-zinc-500 uppercase">Company</p>
        <NavLinks />
        <div className="mt-auto pt-6">
          <LogoutButton />
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-4 py-3 md:hidden dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-sm font-semibold">{appConfig.name}</p>
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger render={<Button variant="outline" size="sm" />}>Menu</SheetTrigger>
            <SheetContent side="left" className="p-0">
              <SheetHeader>
                <SheetTitle>Company</SheetTitle>
              </SheetHeader>
              <div className="px-3 pb-6">
                <NavLinks onNavigate={() => setOpen(false)} />
                <div className="mt-6">
                  <LogoutButton />
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
