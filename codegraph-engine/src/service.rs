use crate::codegraph::code_graph_service_server::CodeGraphService;
use crate::codegraph::{
    IndexProgress, IndexRequest, ParseRequest, ParseResponse, SliceRequest, SliceResponse,
};
use tonic::{Request, Response, Status};
use tokio::sync::mpsc;
use tokio_stream::wrappers::ReceiverStream;

#[derive(Default)]
pub struct CodeGraphServiceImpl {}

#[tonic::async_trait]
impl CodeGraphService for CodeGraphServiceImpl {
    async fn parse_file(
        &self,
        request: Request<ParseRequest>,
    ) -> Result<Response<ParseResponse>, Status> {
        let req = request.into_inner();
        let resp = crate::parser::parse(req)?;
        Ok(Response::new(resp))
    }

    type IndexRepositoryStream = ReceiverStream<Result<IndexProgress, Status>>;

    async fn index_repository(
        &self,
        request: Request<IndexRequest>,
    ) -> Result<Response<Self::IndexRepositoryStream>, Status> {
        let req = request.into_inner();
        let (tx, rx) = mpsc::channel(128);

        // Spawn indexer
        tokio::spawn(async move {
            crate::indexer::index_repo(req, tx).await;
        });

        Ok(Response::new(ReceiverStream::new(rx)))
    }

    async fn slice_graph(
        &self,
        request: Request<SliceRequest>,
    ) -> Result<Response<SliceResponse>, Status> {
        let req = request.into_inner();
        let resp = crate::slicer::slice(req)?;
        Ok(Response::new(resp))
    }
}
