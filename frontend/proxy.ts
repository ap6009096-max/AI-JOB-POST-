import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import {
  canAccessPath,
  defaultHome,
  loginPathForPathname,
  redirectForDenied,
  roleFromClaims,
} from "@/lib/auth/access";
import { shouldRedirectSignedInFromAuth } from "@/lib/auth/intents";
import { isSupabaseConfigured } from "@/lib/config";

export async function proxy(request: NextRequest) {
  if (!isSupabaseConfigured()) {
    return NextResponse.next({ request });
  }

  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => {
            request.cookies.set(name, value);
          });
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) => {
            supabaseResponse.cookies.set(name, value, options);
          });
        },
      },
    },
  );

  const { data } = await supabase.auth.getClaims();
  const role = roleFromClaims(data?.claims as Record<string, unknown> | undefined);
  const pathname = request.nextUrl.pathname;

  if (role && shouldRedirectSignedInFromAuth(role, pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = defaultHome(role);
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (!canAccessPath(role, pathname)) {
    const dest = redirectForDenied(role, pathname) ?? loginPathForPathname(pathname);
    const url = request.nextUrl.clone();
    url.pathname = dest;
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
