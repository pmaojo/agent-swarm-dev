use crate::codegraph::{SliceRequest, SliceResponse};
use tonic::Status;

pub fn slice(req: SliceRequest) -> Result<SliceResponse, Status> {
    // Placeholder implementation
    let context = format!("/* Skeleton view centered on {} */\n\nfn main() {{}}", req.target_symbol_uri);

    Ok(SliceResponse {
        context,
        original_size: 100,
        pruned_size: 50,
        savings_percent: 50.0,
    })
}
