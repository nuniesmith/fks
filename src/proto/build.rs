//! Build script for FKS Proto crate
//!
//! Compiles all centralized Protocol Buffer definitions for FKS services.
//! This provides a single source of truth for all gRPC types across the system.
//!
//! Proto files are located in: ../../proto/fks/
//!
//! ## Two-pass compilation strategy
//!
//! We use two separate `compile_protos` calls to avoid a chicken-and-egg problem
//! caused by `extern_path`:
//!
//! * **Pass 1** — compile `common.proto` and `regime_bridge.proto` *without*
//!   `extern_path`.  Because those packages are the ones being declared extern
//!   in pass 2, using `extern_path` in pass 1 would tell prost to *skip*
//!   generating their `.rs` files — the very files that `include_proto!` in
//!   `lib.rs` expects to exist.
//!
//! * **Pass 2** — compile every other proto *with*
//!   `extern_path(".fks.common.v1",       "crate::common")` and
//!   `extern_path(".fks.janus.v1.bridge", "crate::janus::regime_bridge")`.
//!   `forward.proto` and `execution.proto` both `import "fks/common/v1/common.proto"`;
//!   the extern-path entry rewrites those cross-package references to the
//!   `crate::common` module path that `lib.rs` exposes, instead of the
//!   `super::super::fks::common::v1` path that prost would otherwise emit.
//!
//! Generated modules (all land in `OUT_DIR`, included via `include_proto!`):
//! - fks.common.v1                    → `pub mod common`
//! - fks.janus.v1                     → `pub mod janus`
//! - fks.janus.v1.bridge              → `pub mod janus::regime_bridge`
//! - fks.forward.v1                   → `pub mod forward`
//! - fks.execution.v1                 → `pub mod execution`
//! - fks.data.v1                      → `pub mod data`
//! - fks.cns.v1                       → `pub mod cns`
//! - fks.neuromorphic.distributed.v1  → `pub mod neuromorphic::distributed`
//! - fks.signals.v1                   → `pub mod signals`
//! - fks.paper_trading.v1             → `pub mod paper_trading`
//! - fks.rustcode.v1                  → 'pub mod rustcode'

use std::path::PathBuf;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // -------------------------------------------------------------------------
    // Locate the proto root directory.
    // The fks-proto crate lives at  <workspace>/src/proto/
    // The canonical proto files are at <workspace>/proto/
    // So the relative path from the crate directory is ../../proto.
    // Cargo sets the crate directory as the current directory when running
    // build scripts.
    // -------------------------------------------------------------------------
    let proto_root = PathBuf::from("../../proto");

    if !proto_root.exists() {
        panic!(
            "Proto directory not found at {:?} (resolved from crate build dir). \
             Make sure you are building from the repository root or that the \
             `proto/` directory has been copied into the Docker build context.",
            proto_root
                .canonicalize()
                .unwrap_or_else(|_| proto_root.clone())
        );
    }

    // Helper: turn a slice of relative proto paths into full PathBufs, silently
    // dropping any that do not yet exist on disk (so a missing optional proto
    // never breaks the build).
    let resolve = |files: &[&str]| -> Vec<PathBuf> {
        files
            .iter()
            .map(|f| proto_root.join(f))
            .filter(|p| {
                if !p.exists() {
                    println!(
                        "cargo:warning=Proto file not found (skipped): {}",
                        p.display()
                    );
                }
                p.exists()
            })
            .collect()
    };

    // =========================================================================
    // PASS 1 — "base" packages
    //
    // Compile common.proto and regime_bridge.proto *without* extern_path so
    // that prost actually writes:
    //   $OUT_DIR/fks.common.v1.rs
    //   $OUT_DIR/fks.janus.v1.bridge.rs
    //
    // These two protos have no imports from each other or from any other FKS
    // proto, so they can be compiled independently with no extern_path config.
    // =========================================================================
    let pass1_protos = resolve(&[
        "fks/common/v1/common.proto",
        "fks/janus/v1/regime_bridge.proto",
    ]);

    if pass1_protos.is_empty() {
        panic!(
            "Pass-1 proto files (common.proto, regime_bridge.proto) were not found \
             under {:?}. Cannot continue.",
            proto_root
        );
    }

    println!(
        "cargo:info=Pass 1: compiling {} base proto file(s) ...",
        pass1_protos.len()
    );

    #[cfg_attr(not(feature = "serde"), allow(unused_mut))]
    let mut pass1_builder = tonic_prost_build::configure()
        .build_server(true)
        .build_client(true);

    #[cfg(feature = "serde")]
    {
        pass1_builder = pass1_builder
            .type_attribute(".", "#[derive(serde::Serialize, serde::Deserialize)]")
            .type_attribute(".", "#[serde(rename_all = \"camelCase\")]");
    }

    pass1_builder.compile_protos(
        &pass1_protos.iter().map(|p| p.as_path()).collect::<Vec<_>>(),
        &[proto_root.as_path()],
    )?;

    // =========================================================================
    // PASS 2 — all remaining packages
    //
    // Compile every other proto WITH extern_path mappings for the two packages
    // generated in pass 1.  This rewrites cross-package references from prost's
    // default `super::…::fks::common::v1::Foo` form into `crate::common::Foo`
    // (and `crate::janus::regime_bridge::Foo`), matching the flat module
    // structure declared in lib.rs.
    //
    // forward.proto  → imports fks/common/v1/common.proto
    // execution.proto → imports fks/common/v1/common.proto
    // =========================================================================
    let pass2_protos = resolve(&[
        "fks/janus/v1/janus.proto",
        "fks/forward/v1/forward.proto",
        "fks/execution/v1/execution.proto",
        "fks/data/v1/data.proto",
        "fks/cns/v1/cns.proto",
        "fks/neuromorphic/distributed/v1/distributed.proto",
        "fks/signals/v1/signals.proto",
        "fks/paper_trading/v1/paper_trading.proto",
        "fks/feedback/v1/feedback.proto",
        "fks/rustcode/v1/rustcode.proto",
    ]);

    if !pass2_protos.is_empty() {
        println!(
            "cargo:info=Pass 2: compiling {} service proto file(s) with extern_path ...",
            pass2_protos.len()
        );

        #[cfg_attr(not(feature = "serde"), allow(unused_mut))]
        let mut pass2_builder = tonic_prost_build::configure()
            .build_server(true)
            .build_client(true)
            // Map fks.common.v1 references to the `crate::common` module that
            // lib.rs exposes via `include_proto!("fks.common.v1")`.
            .extern_path(".fks.common.v1", "crate::common")
            // Map fks.janus.v1.bridge references to the nested regime_bridge
            // module inside `pub mod janus { pub mod regime_bridge { … } }`.
            .extern_path(".fks.janus.v1.bridge", "crate::janus::regime_bridge");

        #[cfg(feature = "serde")]
        {
            pass2_builder = pass2_builder
                .type_attribute(".", "#[derive(serde::Serialize, serde::Deserialize)]")
                .type_attribute(".", "#[serde(rename_all = \"camelCase\")]");
        }

        pass2_builder.compile_protos(
            &pass2_protos.iter().map(|p| p.as_path()).collect::<Vec<_>>(),
            &[proto_root.as_path()],
        )?;
    } else {
        println!("cargo:warning=Pass-2 proto files not found — skipping service protos.");
    }

    // =========================================================================
    // Rerun triggers
    //
    // Tell Cargo to re-run this build script whenever anything under proto/
    // changes (new files, edits, deletions).
    // =========================================================================
    println!("cargo:rerun-if-changed={}", proto_root.display());

    let all_protos = [
        "fks/common/v1/common.proto",
        "fks/janus/v1/janus.proto",
        "fks/janus/v1/regime_bridge.proto",
        "fks/forward/v1/forward.proto",
        "fks/execution/v1/execution.proto",
        "fks/data/v1/data.proto",
        "fks/cns/v1/cns.proto",
        "fks/neuromorphic/distributed/v1/distributed.proto",
        "fks/signals/v1/signals.proto",
        "fks/paper_trading/v1/paper_trading.proto",
        "fks/feedback/v1/feedback.proto",
        "fks/rustcode/v1/rustcode.proto",
    ];

    for proto_file in &all_protos {
        let path = proto_root.join(proto_file);
        if path.exists() {
            println!("cargo:rerun-if-changed={}", path.display());
        }
    }

    // Watch each proto directory for newly added files.
    let proto_dirs = [
        "fks/common/v1",
        "fks/janus/v1",
        "fks/forward/v1",
        "fks/execution/v1",
        "fks/data/v1",
        "fks/cns/v1",
        "fks/neuromorphic/distributed/v1",
        "fks/signals/v1",
        "fks/paper_trading/v1",
        "fks/feedback/v1",
        "fks/rustcode/v1",
    ];

    for dir in &proto_dirs {
        let path = proto_root.join(dir);
        if path.exists() {
            println!("cargo:rerun-if-changed={}", path.display());
        }
    }

    println!("cargo:info=Proto compilation complete.");

    Ok(())
}
