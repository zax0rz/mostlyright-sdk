// @tradewinds/codegen — public entry. The CLI implementation lives in
// `./codegen.ts`. This file just re-exports the small public surface so
// downstream tooling can import `runCodegen` programmatically if it ever
// wants to (today nothing does — CI calls the CLI script directly).

export const version = "0.0.0";

export function helloCodegen(): string {
  return "hello @tradewinds/codegen";
}

/**
 * Programmatic entry point. Spawns the CLI under the same Node process by
 * delegating to the implementation module, which performs file I/O.
 *
 * Most callers should invoke the CLI (`pnpm --filter @tradewinds/codegen
 * run codegen`) rather than calling this. Kept for API stability and tests.
 */
export async function runCodegen(): Promise<void> {
  await import("./codegen.js");
}
