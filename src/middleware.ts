import NextAuth from "next-auth";
import { authConfig } from "@/auth.config";

const { auth } = NextAuth(authConfig);

export default auth;

export const config = {
  // Protect everything except Next internals, auth endpoints, and file serving.
  matcher: ["/((?!api/auth|api/files|_next/static|_next/image|favicon.ico).*)"],
};
