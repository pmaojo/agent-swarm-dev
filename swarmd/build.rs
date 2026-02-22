fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("cargo:rerun-if-changed=../synapse-engine/crates/semantic-engine/proto/semantic_engine.proto");
    tonic_build::compile_protos("../synapse-engine/crates/semantic-engine/proto/semantic_engine.proto")?;
    Ok(())
}
