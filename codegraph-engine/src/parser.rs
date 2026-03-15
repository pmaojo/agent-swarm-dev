use crate::codegraph::{ParseRequest, ParseResponse, Symbol};
use std::fs;
use tonic::Status;
use tree_sitter::{Language, Parser, Query, QueryCursor};
use sha2::{Digest, Sha256};

pub fn parse(req: ParseRequest) -> Result<ParseResponse, Status> {
    let mut content = req.content;
    if content.is_empty() {
        content = match fs::read_to_string(&req.file_path) {
            Ok(c) => c,
            Err(e) => return Err(Status::internal(format!("Could not read file: {}", e))),
        };
    }

    let language_name = req.language.clone();
    let file_path_clone = req.file_path.clone();

    // Default to extension if language is empty
    let ext = if !language_name.is_empty() {
        language_name.clone()
    } else {
        std::path::Path::new(&file_path_clone)
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_string()
    };

    let language: Language = match ext.as_str() {
        "py" | "python" => tree_sitter_python::language().into(),
        "rs" | "rust" => tree_sitter_rust::language().into(),
        "js" | "javascript" | "ts" => tree_sitter_javascript::language().into(),
        "cpp" | "c" | "h" | "hpp" => tree_sitter_cpp::language().into(),
        _ => return Err(Status::invalid_argument(format!("Unsupported language/extension: {}", ext))),
    };

    let mut parser = Parser::new();
    if let Err(e) = parser.set_language(&language) {
        return Err(Status::internal(format!("Failed to set language: {}", e)));
    }

    let tree = match parser.parse(&content, None) {
        Some(t) => t,
        None => return Err(Status::internal("Failed to parse code")),
    };

    let mut symbols = Vec::new();
    let mut errors = Vec::new();

    let query_str = match ext.as_str() {
        "py" | "python" => r#"
            (class_definition
                name: (identifier) @name
                body: (block) @body) @class
            (function_definition
                name: (identifier) @name
                body: (block) @body) @function
        "#,
        "rs" | "rust" => r#"
            (struct_item
                name: (type_identifier) @name) @struct
            (impl_item
                type: (type_identifier) @name) @impl
            (function_item
                name: (identifier) @name) @function
        "#,
        "js" | "javascript" | "ts" => r#"
            (class_declaration
                name: (identifier) @name) @class
            (function_declaration
                name: (identifier) @name) @function
            (arrow_function) @function
        "#,
        "cpp" | "c" | "h" | "hpp" => r#"
            (class_specifier
                name: (type_identifier) @name) @class
            (function_definition
                declarator: (function_declarator
                    declarator: (identifier) @name)) @function
        "#,
        _ => "",
    };

    if !query_str.is_empty() {
        match Query::new(&language, query_str) {
            Ok(query) => {
                let mut cursor = QueryCursor::new();
                let matches = cursor.matches(&query, tree.root_node(), content.as_bytes());

                for m in matches {
                    let mut sym_name = String::new();
                    let mut sym_type = String::new();
                    let mut start_line = 0;
                    let mut end_line = 0;
                    let mut code_bytes = vec![];

                    for cap in m.captures {
                        let node = cap.node;
                        let capture_name = &query.capture_names()[cap.index as usize];

                        if *capture_name == "name" {
                            sym_name = String::from_utf8_lossy(&content.as_bytes()[node.start_byte()..node.end_byte()]).into_owned();
                        } else if *capture_name == "class" || *capture_name == "function" || *capture_name == "struct" || *capture_name == "impl" {
                            sym_type = capture_name.to_string();
                            start_line = node.start_position().row as i32 + 1;
                            end_line = node.end_position().row as i32 + 1;
                            code_bytes = content.as_bytes()[node.start_byte()..node.end_byte()].to_vec();
                        }
                    }

                    if !sym_name.is_empty() && !sym_type.is_empty() {
                        let mut hasher = Sha256::new();
                        hasher.update(&code_bytes);
                        let hash = format!("{:x}", hasher.finalize());

                        symbols.push(Symbol {
                            name: sym_name.clone(),
                            qualified_name: sym_name, // Simple for now
                            r#type: sym_type,
                            start_line,
                            end_line,
                            hash,
                            calls: vec![],
                            inherits_from: vec![],
                        });
                    }
                }
            }
            Err(e) => {
                errors.push(format!("Query compilation error: {}", e));
            }
        }
    }

    Ok(ParseResponse {
        file_path: req.file_path,
        symbols,
        errors,
    })
}
