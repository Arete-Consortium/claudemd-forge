# CLAUDE.md — {{PROJECT_NAME}}

> {{DESCRIPTION}}

## Quick Reference

- **Version**: {{VERSION}}
- **Language**: Rust (edition 2024)
- **MSRV**: 1.80+
- **Testing**: cargo test + criterion (benchmarks)
- **CI**: GitHub Actions (test, clippy, fmt, audit)

## Architecture

```
{{PROJECT_NAME}}/
├── src/
│   ├── main.rs               # Binary entry point (thin — calls lib)
│   ├── lib.rs                 # Library root (re-exports public API)
│   ├── config.rs              # Configuration (clap + env vars)
│   ├── error.rs               # Error types (thiserror)
│   ├── models/                # Domain types and data structures
│   │   ├── mod.rs
│   │   └── user.rs
│   ├── services/              # Business logic
│   │   ├── mod.rs
│   │   └── user_service.rs
│   └── handlers/              # API/CLI handlers (if applicable)
├── benches/                   # Criterion benchmarks
│   └── core_bench.rs
├── tests/                     # Integration tests
│   └── integration.rs
├── Cargo.toml
├── Cargo.lock                 # Always commit for binaries
├── rust-toolchain.toml        # Pin Rust version
└── deny.toml                  # cargo-deny configuration
```

## Coding Standards

### General
- Use `Result<T, E>` for all fallible operations — no `.unwrap()` in production
- Derive `Debug` on all types. Add `Clone`, `PartialEq`, `Eq`, `Hash` where useful
- Use `thiserror` for library error types, `anyhow` for application error types
- Document all public items with `///` doc comments including `# Examples`
- Maximum function length: 40 lines. Extract helper functions if longer
- Prefer `&str` parameters over `String` when ownership isn't needed

### Error Handling
- Define a crate-level `Error` enum with `#[derive(thiserror::Error)]`
- Use `?` operator for propagation — no manual `match` on `Result` for early returns
- Add context with `.context("what failed")` (anyhow) or `map_err`
- Never use `.unwrap()` or `.expect()` in library code
- `.expect("reason")` is acceptable only in tests and infallible paths with a comment

### Async (if applicable)
- Use `tokio` runtime with `#[tokio::main]` or `#[tokio::test]`
- Use `tokio::select!` for concurrent operations, not raw `spawn` + `join`
- Async functions return `impl Future` — avoid `Box<dyn Future>` unless required
- Use `tokio::sync::Mutex` for shared state in async, not `std::sync::Mutex`
- Cancel safety: document whether functions are cancel-safe

### Performance
- Prefer `&[T]` over `Vec<T>` in function parameters
- Use `Cow<'_, str>` when a function might or might not allocate
- Avoid allocations in hot paths — pre-allocate with `Vec::with_capacity`
- Use `#[inline]` sparingly — only on small, frequently-called functions
- Benchmark before optimizing — use criterion for micro-benchmarks

### Testing
- Unit tests in `#[cfg(test)] mod tests` at bottom of each module
- Integration tests in `tests/` directory
- Use `#[test]` for sync, `#[tokio::test]` for async
- Table-driven tests with arrays of `(input, expected)` tuples
- Property-based testing with `proptest` for parsing/serialization

## Common Commands

```bash
# Build
cargo build                              # Debug build
cargo build --release                    # Release build

# Test
cargo test                               # All tests
cargo test -- --nocapture                # Show println! output
cargo test -p {{PROJECT_NAME}} --lib     # Lib tests only

# Lint
cargo clippy -- -W warnings             # Clippy (treat warnings as errors)
cargo fmt -- --check                     # Format check
cargo deny check                         # Dependency audit

# Benchmark
cargo bench                              # Run criterion benchmarks

# Documentation
cargo doc --open --no-deps               # Generate and open docs

# Release
cargo publish --dry-run                  # Verify crates.io packaging
```

## Anti-Patterns (Do NOT Do)

### Safety
- Do NOT use `.unwrap()` in production code — use `?` or handle the error
- Do NOT use `unsafe` without a `// SAFETY:` comment explaining the invariant
- Do NOT suppress clippy warnings without `// reason: ...` justification
- Do NOT use `mem::transmute` — use safe alternatives (`From`, `TryFrom`, `as`)
- Do NOT use `panic!()` for recoverable errors — return `Result`

### Ownership
- Do NOT clone when a reference will do — prefer `&T` over `T.clone()`
- Do NOT use `Rc<RefCell<T>>` when a simpler design works
- Do NOT fight the borrow checker with `unsafe` — redesign the data flow
- Do NOT use `String` parameters when `&str` is sufficient
- Do NOT use `Box<dyn Trait>` when generics (`impl Trait`) work

### Performance
- Do NOT use `format!()` for simple string concatenation — use `push_str()`
- Do NOT allocate in loops — pre-allocate or use iterators
- Do NOT use `HashMap` for tiny collections (<10 items) — use `Vec` with linear search
- Do NOT use `Arc<Mutex<T>>` when channels (`mpsc`, `broadcast`) fit better
- Do NOT add `#[inline(always)]` without benchmarks proving it helps

### Dependencies
- Do NOT use `*` in Cargo.toml version requirements — pin major version `^1.0`
- Do NOT add dependencies for trivial operations — check if std has it
- Do NOT use deprecated crates — check maintenance status
- Do NOT commit Cargo.lock for libraries (do commit for binaries)

## Cargo.toml Essentials

```toml
[package]
name = "{{PROJECT_NAME}}"
version = "0.1.0"
edition = "2024"
rust-version = "1.80"
description = "{{DESCRIPTION}}"
license = "MIT"

[lints.rust]
unsafe_code = "forbid"

[lints.clippy]
all = { level = "warn", priority = -1 }
pedantic = { level = "warn", priority = -1 }
unwrap_used = "warn"
expect_used = "warn"

[profile.release]
lto = true
codegen-units = 1
strip = true
```

## Git Conventions

- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Run `cargo test && cargo clippy && cargo fmt -- --check` before pushing
- Squash merge feature branches
