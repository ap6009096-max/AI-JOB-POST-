import Link from "next/link";

import { ShaderHero } from "@/components/brand/shader-hero";
import { buttonVariants } from "@/components/ui/button";
import { appConfig } from "@/lib/config";
import { cn } from "@/lib/utils";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col bg-zinc-50 dark:bg-black">
      <ShaderHero
        className="min-h-[70vh] rounded-none border-0"
        shader="lines"
        eyebrow={appConfig.name}
        title={appConfig.name}
        subtitle={appConfig.tagline}
        actions={
          <>
            <Link href="/login/candidate" className={cn(buttonVariants(), "inline-flex")}>
              Candidate dashboard
            </Link>
            <Link href="/login/company" className={cn(buttonVariants({ variant: "outline" }), "inline-flex border-white/30 bg-white/10 text-white hover:bg-white/20")}>
              Company dashboard
            </Link>
          </>
        }
      >
        <p className="mt-8 max-w-2xl text-sm text-zinc-200/80">
          Candidates build one standing professional profile. Recruiters publish jobs, then rank
          registered talent or search the internet — two separate discovery tracks.
        </p>
      </ShaderHero>
    </div>
  );
}
