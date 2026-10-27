/**
 * Cloudflare Pages Functions API Handler (under frontend/ root).
 * Routes all /api/* requests to the edge backend handler.
 */

import { handleApiRequest, Env } from "../../../worker";

interface EventContext {
  request: Request;
  env: Env;
  params: Record<string, string | string[]>;
  next: () => Promise<Response>;
}

export async function onRequest(context: EventContext): Promise<Response> {
  return handleApiRequest(context.request, context.env);
}
