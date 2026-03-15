use crate::codegraph::{IndexProgress, IndexRequest};
use tokio::sync::mpsc;
use tonic::Status;
use ignore::WalkBuilder;

pub async fn index_repo(req: IndexRequest, tx: mpsc::Sender<Result<IndexProgress, Status>>) {
    let mut builder = WalkBuilder::new(&req.root_path);
    builder.hidden(false).parents(false).ignore(false);

    for pattern in &req.ignore_patterns {
        builder.add_custom_ignore_filename(pattern);
    }

    let walker = builder.build();
    let mut files_processed = 0;

    // Send initial status
    let _ = tx.send(Ok(IndexProgress {
        current_file: String::new(),
        files_processed: 0,
        total_files: 0,
        status: "indexing".to_string(),
        error_message: String::new(),
    })).await;

    for result in walker {
        match result {
            Ok(entry) => {
                if entry.file_type().map_or(false, |ft| ft.is_file()) {
                    let path = entry.path().to_string_lossy().to_string();
                    files_processed += 1;

                    let _ = tx.send(Ok(IndexProgress {
                        current_file: path.clone(),
                        files_processed,
                        total_files: 0,
                        status: "indexing".to_string(),
                        error_message: String::new(),
                    })).await;

                    // In a real implementation, we would parse and index here
                }
            }
            Err(e) => {
                let _ = tx.send(Ok(IndexProgress {
                    current_file: String::new(),
                    files_processed,
                    total_files: 0,
                    status: "error".to_string(),
                    error_message: format!("Walk error: {}", e),
                })).await;
            }
        }
    }

    let _ = tx.send(Ok(IndexProgress {
        current_file: String::new(),
        files_processed,
        total_files: files_processed,
        status: "complete".to_string(),
        error_message: String::new(),
    })).await;
}
