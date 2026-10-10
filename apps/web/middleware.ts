import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** When demo org is baked in at deploy time, land visitors in the app shell. */
export function middleware(request: NextRequest) {
  if (!process.env.NEXT_PUBLIC_DEFAULT_DEMO_ORG_ID) {
    return NextResponse.next();
  }
  if (request.nextUrl.pathname === "/") {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: "/",
};
