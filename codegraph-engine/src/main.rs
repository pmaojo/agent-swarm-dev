pub mod codegraph {
    tonic::include_proto!("codegraph");
}

pub mod parser;
pub mod indexer;
pub mod slicer;
pub mod service;

use codegraph::code_graph_service_server::CodeGraphServiceServer;
use service::CodeGraphServiceImpl;
use tonic::transport::Server;
use std::env;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let port = env::var("CODEGRAPH_GRPC_PORT").unwrap_or_else(|_| "50053".to_string());
    let addr = format!("0.0.0.0:{}", port).parse()?;

    let service_impl = CodeGraphServiceImpl::default();
    let service = CodeGraphServiceServer::new(service_impl);

    println!("CodeGraph Engine listening on {}", addr);

    Server::builder()
        .add_service(service)
        .serve(addr)
        .await?;

    Ok(())
}
