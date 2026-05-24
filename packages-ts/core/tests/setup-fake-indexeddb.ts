// Polyfill IndexedDB for jsdom-routed tests. The polyfill registers a
// no-op on Node-only tests (typeof indexedDB stays undefined there because
// `fake-indexeddb/auto` only mounts when invoked).
//
// vitest applies setupFiles globally; the polyfill is loaded for every test
// run but only registers itself when the runtime environment supports it.
import "fake-indexeddb/auto";
