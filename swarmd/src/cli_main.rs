use anyhow::Result;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::{Backend, CrosstermBackend},
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Span, Line},
    widgets::{Block, Borders, Paragraph, List, ListItem, ListState},
    Frame, Terminal,
};
use std::{io, time::{Duration, Instant}};
use tokio::sync::mpsc;

// Cleanup function to restore terminal on exit/crash
fn cleanup_terminal() {
    // Print reset sequences to restore terminal
    eprint!("\x1b[?1049l");  // Exit alternate screen
    eprint!("\x1bc");         // Reset terminal  
    eprint!("\x1b[?1000l");   // Disable mouse
    eprint!("\n");
}
use futures_util::StreamExt;
use tokio_tungstenite::connect_async;
use serde_json::Value;

#[derive(PartialEq, Eq, Clone, Copy)]
enum ActivePanel {
    Input,
    Knowledge,
    KnowledgeDetail,
    Actions,
    Stream,
}

struct App {
    frame_count: u64,
    messages: Vec<String>,
    input: String,
    connected: bool,
    list_state: ListState,
    active_panel: ActivePanel,
    knowledge_nodes: Vec<String>,
    knowledge_state: ListState,
    active_node_detail: String,
    actions: Vec<String>,
    action_index: usize,
}

impl App {
    async fn new() -> App {
        let mut list_state = ListState::default();
        list_state.select(Some(0));
        let mut knowledge_state = ListState::default();
        knowledge_state.select(Some(0));
        
        // Fetch real knowledge nodes from Synapse
        let knowledge_nodes = Self::fetch_knowledge_nodes().await;
        
        // Fetch real system status
        let status = Self::fetch_system_status().await;
        let mut messages = vec!["Initializing neural links...".to_string()];
        if let Some(s) = status {
            messages.push(s);
        }
        
        App { 
            frame_count: 0,
            messages,
            input: String::new(),
            connected: false,
            list_state,
            active_panel: ActivePanel::Input,
            knowledge_nodes,
            knowledge_state,
            active_node_detail: String::new(),
            actions: vec![
                "LAUNCH MISSION".to_string(),
                "HALT SWARM".to_string(),
                "RESET BRAIN".to_string(),
                "SCAN SECTOR".to_string(),
            ],
            action_index: 0,
        }
    }
    
    async fn fetch_knowledge_nodes() -> Vec<String> {
        let client = reqwest::Client::new();
        match client.get("http://127.0.0.1:18789/api/v1/game-state")
            .timeout(Duration::from_secs(3))
            .send()
            .await
        {
            Ok(resp) => {
                match resp.json::<serde_json::Value>().await {
                    Ok(json) => {
                        let nodes = json.get("knowledge_tree")
                            .and_then(|n| n.as_array())
                            .map(|arr| arr.iter()
                                .filter_map(|n| n.get("name").or_else(|| n.get("id")))
                                .filter_map(|v| v.as_str())
                                .map(|s| s.to_string())
                                .collect::<Vec<String>>()
                            );
                        
                        let resolved = nodes.unwrap_or_default();
                        if resolved.is_empty() {
                            vec!["No knowledge nodes found".to_string()]
                        } else {
                            resolved
                        }
                    }
                    Err(_) => vec!["Failed to parse knowledge".to_string()]
                }
            }
            Err(_) => vec!["Connect to gateway for knowledge".to_string()]
        }
    }
    
    async fn fetch_system_status() -> Option<String> {
        let client = reqwest::Client::new();
        match client.get("http://127.0.0.1:18789/api/v1/game-state")
            .timeout(Duration::from_secs(3))
            .send()
            .await
        {
            Ok(resp) => {
                match resp.json::<serde_json::Value>().await {
                    Ok(json) => {
                        let status = json.get("system_status")
                            .and_then(|s| s.as_str())
                            .unwrap_or("UNKNOWN");
                        let budget = json.get("daily_budget").and_then(|b| {
                            let max = b.get("max").and_then(|m| m.as_f64()).unwrap_or(0.0);
                            let spent = b.get("spent").and_then(|s| s.as_f64()).unwrap_or(0.0);
                            Some(format!("${spent:.2}/${max:.2}"))
                        });
                        Some(format!("System: {} | Budget: {}", status, budget.unwrap_or_default()))
                    }
                    Err(_) => None
                }
            }
            Err(_) => None
        }
    }

    fn on_tick(&mut self) {
        self.frame_count += 1;
    }

    fn add_message(&mut self, msg: String) {
        self.messages.push(msg);
        if self.messages.len() > 500 {
            self.messages.remove(0);
        }
        self.list_state.select(Some(self.messages.len().saturating_sub(1)));
    }

    pub fn clear_messages(&mut self) {
        self.messages.clear();
        self.messages.push("[SYSTEM] Neural stream purged.".to_string());
        self.list_state.select(Some(0));
    }

    fn next_panel(&mut self) {
        self.active_panel = match self.active_panel {
            ActivePanel::Input => ActivePanel::Knowledge,
            ActivePanel::Knowledge => ActivePanel::Stream,
            ActivePanel::Stream => ActivePanel::Actions,
            ActivePanel::Actions => ActivePanel::Input,
            ActivePanel::KnowledgeDetail => ActivePanel::KnowledgeDetail,
        };
    }

    #[allow(dead_code)]
    fn handle_action(&mut self, action: &str) -> String {
        // Handle real actions via HTTP API
        match action {
            "LAUNCH MISSION" => {
                // Show prompt for mission task
                "Enter mission task in command panel".to_string()
            }
            "HALT SWARM" => {
                // Send HALT command to gateway
                let client = reqwest::blocking::Client::new();
                let result = client.post("http://127.0.0.1:18789/api/v1/control/commands")
                    .json(&serde_json::json!({
                        "command_type": "HALT",
                        "target": "all",
                        "reason": "Operator initiated halt"
                    }))
                    .send();
                match result {
                    Ok(resp) if resp.status().is_success() => "[SUCCESS] Swarm HALTED".to_string(),
                    Ok(resp) => format!("[ERROR] HALT failed: {}", resp.status()),
                    Err(e) => format!("[ERROR] Connection failed: {}", e)
                }
            }
            "RESET BRAIN" => {
                // Clear memory / reset agent state
                let client = reqwest::blocking::Client::new();
                let result = client.post("http://127.0.0.1:18789/api/v1/control/commands")
                    .json(&serde_json::json!({
                        "command_type": "RESET",
                        "target": "orchestrator",
                        "reason": "Brain reset requested"
                    }))
                    .send();
                match result {
                    Ok(resp) if resp.status().is_success() => "[SUCCESS] Brain reset complete".to_string(),
                    Ok(resp) => format!("[ERROR] Reset failed: {}", resp.status()),
                    Err(e) => format!("[ERROR] Connection failed: {}", e)
                }
            }
            "SCAN SECTOR" => {
                // Query knowledge graph / scan for new info
                let client = reqwest::blocking::Client::new();
                let result = client.get("http://127.0.0.1:18789/api/v1/graph-nodes")
                    .send();
                match result {
                    Ok(resp) if resp.status().is_success() => "[SUCCESS] Sector scanned - new intel acquired".to_string(),
                    Ok(resp) => format!("[ERROR] Scan failed: {}", resp.status()),
                    Err(e) => format!("[ERROR] Connection failed: {}", e)
                }
            }
            _ => format!("[UNKNOWN] Action: {}", action)
        }
    }
    
    fn handle_input(&mut self, input: String, command_tx: &mpsc::Sender<String>) {
        let normalized = input.trim().to_lowercase();
        if normalized == "status" {
            let status = if self.connected { "SECURE" } else { "SEVERED" };
            self.add_message(format!("[SYSTEM] Core telemetry: {}", status));
        } else if normalized == "help" {
            self.add_message("[SYSTEM] Available: status, help, /run <task>. Standard input talks to AI.".to_string());
        } else if input.starts_with("/run ") || input.starts_with("/mission ") {
            let task = input.replacen("/run ", "", 1).replacen("/mission ", "", 1);
            self.add_message(format!("[SYSTEM] Assigning mission: {}", task));
            let _ = command_tx.try_send(format!("MISSION:{}", task));
        } else {
            // Conversational mode via Gemini
            let _ = command_tx.try_send(format!("CHAT:{}", input));
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // Load environment variables from .env if present
    let _ = dotenv::dotenv();

    // Register panic handler to restore terminal on crash
    std::panic::set_hook(Box::new(|_| {
        cleanup_terminal();
    }));

    // setup terminal
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // Setup WebSocket communication
    let (tx, mut rx) = mpsc::channel(100);
    let (command_tx, mut command_rx) = mpsc::channel::<String>(10);
    let (status_tx, mut status_rx) = mpsc::channel(1);

    let tx_cmd = tx.clone();
    tokio::spawn(async move {
        let client = reqwest::Client::new();
        while let Some(cmd) = command_rx.recv().await {
            if cmd == "LAUNCH MISSION" {
                let res = client.post("http://127.0.0.1:18789/api/v1/mission/assign")
                    .json(&serde_json::json!({
                        "agent_id": "http://swarm.os/agents/Coder",
                        "repo_id": "root",
                        "task": "Scan and analyze neural nodes"
                    }))
                    .send()
                    .await;
                match res {
                    Ok(r) if r.status().is_success() => { let _ = tx_cmd.send("[SUCCESS] Mission 'Scan and analyze' dispatched.".to_string()).await; }
                    _ => { let _ = tx_cmd.send("[ERROR] Failed to dispatch mission.".to_string()).await; }
                }
            } else if cmd == "HALT SWARM" {
                let res = client.post("http://127.0.0.1:18789/api/v1/control/commands")
                    .json(&serde_json::json!({
                        "command_type": "Halt",
                        "actor": "operator",
                        "nist_policy_id": "NIST-800-53-REV5",
                        "approved_by": "operator"
                    }))
                    .send()
                    .await;
                match res {
                    Ok(r) if r.status().is_success() => { let _ = tx_cmd.send("[SUCCESS] System HALTED command sent.".to_string()).await; }
                    _ => { let _ = tx_cmd.send("[ERROR] HALT command failed. Check gateway connection.".to_string()).await; }
                }
            } else if cmd == "RESET BRAIN" {
                let _ = tx_cmd.send("[SYSTEM] Brain reset not fully implemented in backend.".to_string()).await;
            } else if cmd == "SCAN SECTOR" {
                let res = client.get("http://127.0.0.1:18789/api/v1/game-state").send().await;
                match res {
                    Ok(r) if r.status().is_success() => { let _ = tx_cmd.send("[SUCCESS] Sector scanned. Neural sensors active.".to_string()).await; }
                    _ => { let _ = tx_cmd.send("[ERROR] Scan failed. Ensure gateway is online.".to_string()).await; }
                }
            } else if let Some(task) = cmd.strip_prefix("MISSION:") {
                let res = client.post("http://127.0.0.1:18789/api/v1/mission/assign")
                    .json(&serde_json::json!({
                        "agent_id": "http://swarm.os/agents/Coder",
                        "repo_id": "root",
                        "task": task
                    }))
                    .send()
                    .await;
                match res {
                    Ok(r) if r.status().is_success() => { let _ = tx_cmd.send(format!("[SUCCESS] Mission '{}' accepted by Orchestrator.", task)).await; }
                    _ => { let _ = tx_cmd.send("[ERROR] Gateway rejected mission assignment.".to_string()).await; }
                }
            } else if let Some(node_id) = cmd.strip_prefix("KNOWLEDGE:") {
                let url = format!("http://127.0.0.1:18789/api/v1/knowledge/{}/docs", node_id);
                match client.get(&url).send().await {
                    Ok(r) if r.status().is_success() => {
                        if let Ok(json) = r.json::<serde_json::Value>().await {
                            if let Some(docs) = json.get("documentation").and_then(|d| d.as_str()) {
                                let docs_clean = if docs.is_empty() { "No documentation available." } else { docs };
                                // Instead of just logging, we send a special detail message back to the UI thread
                                let _ = tx_cmd.send(format!("DETAIL_VIEW:{}", docs_clean)).await;
                            } else {
                                let _ = tx_cmd.send("DETAIL_VIEW:No documentation found.".to_string()).await;
                            }
                        }
                    }
                    _ => { let _ = tx_cmd.send(format!("DETAIL_VIEW:[ERROR] Failed to access knowledge core for {}.", node_id)).await; }
                }
            } else if let Some(chat) = cmd.strip_prefix("CHAT:") {
                // Call Gemini for conversational fallback and "tool" routing
                if let Ok(api_key) = std::env::var("GEMINI_API_KEY") {
                    let url = format!("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={}", api_key);
                    
                    let sys_prompt = "You are the AI persona of Agent Swarm, a sovereign AI cluster defending a cybernetic empire. Keep responses very short, technical, and slightly ruthless. You control the TUI interface. If the user asks you to do a task, code something, or launch a mission, output exact string: 'MISSION_CMD: <task>'. If the user asks you to scan the sector/network, output exact string: 'SCAN_CMD'. If the user asks to read a specific knowledge node by ID, output exact string: 'KNOWLEDGE_CMD: <node_id>'. If you use a command, do NOT output anything else.";
                    
                    let payload = serde_json::json!({
                        "contents": [{
                            "parts": [{"text": format!("{} The user says: {}", sys_prompt, chat)}]
                        }]
                    });
                    
                    match client.post(&url).json(&payload).send().await {
                        Ok(resp) => {
                            if let Ok(json) = resp.json::<serde_json::Value>().await {
                                if let Some(text) = json.pointer("/candidates/0/content/parts/0/text").and_then(|t| t.as_str()) {
                                    let content = text.trim();
                                    if content.contains("MISSION_CMD:") {
                                        let parts: Vec<&str> = content.split("MISSION_CMD:").collect();
                                        if parts.len() > 1 {
                                            let task = parts[1].trim();
                                            let _ = tx_cmd.send(format!("[AI] Initializing mission: {}", task)).await;
                                            let _ = tx_cmd.send(format!("MISSION:{}", task)).await;
                                        }
                                    } else if content.contains("SCAN_CMD") {
                                        let _ = tx_cmd.send("[AI] Executing sector scan...".to_string()).await;
                                        let _ = tx_cmd.send("SCAN SECTOR".to_string()).await;
                                    } else if content.contains("KNOWLEDGE_CMD:") {
                                        let parts: Vec<&str> = content.split("KNOWLEDGE_CMD:").collect();
                                        if parts.len() > 1 {
                                            let node_id = parts[1].trim();
                                            let _ = tx_cmd.send(format!("[AI] Fetching knowledge databanks for node: {}", node_id)).await;
                                            let _ = tx_cmd.send(format!("KNOWLEDGE:{}", node_id)).await;
                                        }
                                    } else {
                                        let _ = tx_cmd.send(format!("[AI] {}", content.replace('\n', " "))).await;
                                    }
                                } else {
                                    let _ = tx_cmd.send("[ERROR] AI response format invalid.".to_string()).await;
                                }
                            }
                        }
                        Err(_) => { let _ = tx_cmd.send("[ERROR] Connection to AI Core failed.".to_string()).await; }
                    }
                } else {
                    let _ = tx_cmd.send("[SYSTEM] GEMINI_API_KEY not found. Neural speech disabled.".to_string()).await;
                }
            } else {
                // Should not happen with prefixes, but handled
                let _ = tx_cmd.send(format!("[SYSTEM] Unrecognized command format: {}", cmd)).await;
            }
        }
    });

    let tx_ws = tx.clone();
    tokio::spawn(async move {
        let url = "ws://127.0.0.1:18789/api/v1/events/combat/stream";
        loop {
            match connect_async(url).await {
                Ok((mut ws_stream, _)) => {
                    let _ = status_tx.send(true).await;
                    while let Some(msg) = ws_stream.next().await {
                        if let Ok(msg) = msg {
                            if let Ok(text) = msg.to_text() {
                                if let Ok(v) = serde_json::from_str::<Value>(text) {
                                    let type_str = v["type"].as_str().unwrap_or("UNKNOWN");
                                    let msg_str = v["payload"]["message"].as_str().unwrap_or("");
                                    let formatted = format!("[{}] {}", type_str, msg_str);
                                    let _ = tx_ws.send(formatted).await;
                                }
                            }
                        } else {
                            break;
                        }
                    }
                    let _ = status_tx.send(false).await;
                }
                Err(_) => {
                    let _ = status_tx.send(false).await;
                }
            }
            tokio::time::sleep(Duration::from_secs(2)).await;
        }
    });

    // create app and run it
    let tick_rate = Duration::from_millis(50);
    let mut app = App::new().await;
    let res = run_app(&mut terminal, &mut app, tick_rate, &mut rx, &mut status_rx, command_tx).await;

    // restore terminal
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    // Reset terminal to clean state (fixes escape code garbage on exit)
    println!("\x1b[?1049l"); // Exit alternate screen
    println!("\x1bc");        // Reset terminal

    if let Err(err) = res {
        cleanup_terminal();
        println!("{:?}", err)
    }

    Ok(())
}

async fn run_app<B: Backend>(
    terminal: &mut Terminal<B>,
    app: &mut App,
    tick_rate: Duration,
    rx: &mut mpsc::Receiver<String>,
    status_rx: &mut mpsc::Receiver<bool>,
    command_tx: mpsc::Sender<String>,
) -> io::Result<()> {
    let mut last_tick = Instant::now();
    loop {
        terminal.draw(|f| ui(f, app))?;

        let timeout = tick_rate
            .checked_sub(last_tick.elapsed())
            .unwrap_or_else(|| Duration::from_secs(0));
        
        if crossterm::event::poll(timeout)? {
            if let Event::Key(key) = event::read()? {
                match key.code {
                    KeyCode::Char('q') if key.modifiers.contains(crossterm::event::KeyModifiers::CONTROL) => return Ok(()),
                    KeyCode::Tab => {
                        if app.active_panel != ActivePanel::KnowledgeDetail {
                            app.next_panel();
                        }
                    },
                    KeyCode::Char(c) if app.active_panel == ActivePanel::Input => app.input.push(c),
                    KeyCode::Backspace if app.active_panel == ActivePanel::Input => { app.input.pop(); },
                    KeyCode::Enter => {
                        if app.active_panel == ActivePanel::Input && !app.input.is_empty() {
                            let input = app.input.clone();
                            app.add_message(format!("[USER] {}", input));
                            app.handle_input(input, &command_tx);
                            app.input.clear();
                        } else if app.active_panel == ActivePanel::Actions {
                            let action = app.actions[app.action_index].clone();
                            app.add_message(format!("[SYSTEM] Executing: {}", action));
                            let _ = command_tx.try_send(action);
                        } else if app.active_panel == ActivePanel::Knowledge {
                            if let Some(idx) = app.knowledge_state.selected() {
                                if let Some(node) = app.knowledge_nodes.get(idx).cloned() {
                                    app.add_message(format!("[SYSTEM] Accessing knowledge core: {}", node));
                                    let _ = command_tx.try_send(format!("KNOWLEDGE:{}", node));
                                }
                            }
                        }
                    },
                    KeyCode::Char('l') if key.modifiers.contains(crossterm::event::KeyModifiers::CONTROL) => {
                        app.clear_messages();
                    },
                    KeyCode::Char('a') if key.modifiers.contains(crossterm::event::KeyModifiers::CONTROL) => {
                        if !app.input.is_empty() {
                            let input = app.input.clone();
                            app.add_message(format!("[USER] {}", input));
                            app.handle_input(input, &command_tx);
                            app.input.clear();
                        }
                    },
                    KeyCode::Up => {
                        match app.active_panel {
                            ActivePanel::Knowledge => {
                                let i = match app.knowledge_state.selected() {
                                    Some(i) => if i == 0 { app.knowledge_nodes.len() - 1 } else { i - 1 },
                                    None => 0,
                                };
                                app.knowledge_state.select(Some(i));
                            }
                            ActivePanel::Actions => {
                                app.action_index = if app.action_index == 0 { app.actions.len() - 1 } else { app.action_index - 1 };
                            }
                            _ => {}
                        }
                    }
                    KeyCode::Down => {
                        match app.active_panel {
                            ActivePanel::Knowledge => {
                                let i = match app.knowledge_state.selected() {
                                    Some(i) => if i >= app.knowledge_nodes.len() - 1 { 0 } else { i + 1 },
                                    None => 0,
                                };
                                app.knowledge_state.select(Some(i));
                            }
                            ActivePanel::Actions => {
                                app.action_index = if app.action_index >= app.actions.len() - 1 { 0 } else { app.action_index + 1 };
                            }
                            _ => {}
                        }
                    }
                    KeyCode::Esc => {
                        if app.active_panel == ActivePanel::KnowledgeDetail {
                            app.active_panel = ActivePanel::Knowledge;
                        } else {
                            return Ok(())
                        }
                    },
                    _ => {}
                }
            }
        }

        while let Ok(msg) = rx.try_recv() {
            if let Some(detail) = msg.strip_prefix("DETAIL_VIEW:") {
                app.active_node_detail = detail.to_string();
                app.active_panel = ActivePanel::KnowledgeDetail;
            } else {
                app.add_message(msg);
            }
        }

        while let Ok(connected) = status_rx.try_recv() {
            app.connected = connected;
            if connected {
                app.add_message("[ONLINE] Neural link established.".to_string());
            } else if app.frame_count % 100 == 0 { // Don't spam
                app.add_message("[OFFLINE] Neural link severed. Retrying...".to_string());
            }
        }

        if last_tick.elapsed() >= tick_rate {
            app.on_tick();
            last_tick = Instant::now();
        }
    }
}

fn ui(f: &mut Frame, app: &mut App) {
    let size = f.size();
    
    // Check for KnowledgeDetail view (Full Screen)
    if app.active_panel == ActivePanel::KnowledgeDetail {
        let block = Block::default()
            .borders(Borders::ALL)
            .title(Span::styled(" KNOWLEDGE CORE: DEEP INSPECTION ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)))
            .border_style(Style::default().fg(Color::Cyan));
        
        let detail_text = Paragraph::new(app.active_node_detail.as_str())
            .block(block)
            .wrap(ratatui::widgets::Wrap { trim: true })
            .scroll((0, 0)); // Could add scrolling state later if needed
            
        f.render_widget(detail_text, size);
        
        // Help hint for detail view
        let help_rect = ratatui::layout::Rect::new(size.x + size.width - 25, size.y + size.height - 2, 24, 1);
        let help_hint = Paragraph::new(" [ESC] Return to Swarm ")
            .style(Style::default().fg(Color::Rgb(120, 120, 120)))
            .alignment(ratatui::layout::Alignment::Right);
        f.render_widget(help_hint, help_rect);
        
        return;
    }

    let main_layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(5), // Compact Logo
            Constraint::Min(0),    // Panels
            Constraint::Length(3), // Input
        ])
        .split(size);

    let panel_layout = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(25), // Sidebar Knowledge
            Constraint::Percentage(60), // Thought Stream
            Constraint::Percentage(15), // Actions
        ])
        .split(main_layout[1]);

    // 1. Logo Panel
    let colors = [
        Color::Red, Color::Yellow, Color::Green, Color::Cyan, Color::Blue, Color::Magenta,
    ];
    let color = colors[(app.frame_count / 4 % 6) as usize];
    let banner_text = "
 ██████╗ ██████╗ ██╗      ██████╗ ███████╗███████╗██╗   ██╗███████╗
██╔════╝██╔═══██╗██║     ██╔═══██╗██╔════╝██╔════╝██║   ██║██╔════╝
██║     ██║   ██║██║     ██║   ██║███████╗███████╗██║   ██║███████╗
██║     ██║   ██║██║     ██║   ██║╚════██║╚════██║██║   ██║╚════██║
╚██████╗╚██████╔╝███████╗╚██████╔╝███████║███████║╚██████╔╝███████║
 ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝╚══════╝ ╚═════╝ ╚══════╝
";
    let status_color = if app.connected { Color::Green } else { Color::Red };
    let status_text = if app.connected { "ONLINE" } else { "OFFLINE" };

    let logo = Paragraph::new(banner_text)
        .style(Style::default().fg(color).add_modifier(Modifier::BOLD))
        .alignment(ratatui::layout::Alignment::Center)
        .block(Block::default()
            .borders(Borders::ALL)
            .title(Span::styled(format!(" SYSTEM CORE [{}] ", status_text), Style::default().fg(status_color).add_modifier(Modifier::BOLD))));
    f.render_widget(logo, main_layout[0]);

    let k_style = if app.active_panel == ActivePanel::Knowledge { Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD) } else { Style::default().fg(Color::DarkGray) };
    let s_style = if app.active_panel == ActivePanel::Stream { Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD) } else { Style::default().fg(Color::DarkGray) };
    let a_style = if app.active_panel == ActivePanel::Actions { Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD) } else { Style::default().fg(Color::DarkGray) };
    let i_style = if app.active_panel == ActivePanel::Input { Style::default().fg(Color::Green).add_modifier(Modifier::BOLD) } else { Style::default().fg(Color::DarkGray) };

    // 2. Sidebar: Knowledge Explorer
    let knowledge_items: Vec<ListItem> = app.knowledge_nodes.iter().map(|k| {
        ListItem::new(Line::from(vec![
            Span::styled("● ", Style::default().fg(Color::Cyan)),
            Span::styled(k, Style::default().fg(Color::Gray)),
        ]))
    }).collect();
    
    let k_title = if app.active_panel == ActivePanel::Knowledge { " [ SELECTED: KNOWLEDGE (Up/Down to scroll) ] " } else { " KNOWLEDGE " };
    let knowledge = List::new(knowledge_items)
        .block(Block::default().borders(Borders::ALL).title(k_title).border_style(k_style))
        .highlight_style(Style::default().bg(Color::Rgb(30, 30, 50)).add_modifier(Modifier::BOLD))
        .highlight_symbol(">> ");
    f.render_stateful_widget(knowledge, panel_layout[0], &mut app.knowledge_state);

    // 3. Main: Thought Stream
    let messages: Vec<ListItem> = app.messages.iter().map(|m| {
        let style = if m.contains("THOUGHT") {
            Style::default().fg(Color::Cyan).add_modifier(Modifier::ITALIC)
        } else if m.contains("TOOL") {
            Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)
        } else if m.contains("USER") {
            Style::default().fg(Color::Green)
        } else if m.contains("[AI]") {
             Style::default().fg(Color::Magenta).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(Color::Gray)
        };
        ListItem::new(Line::from(vec![Span::styled(m, style)]))
    }).collect();

    let s_title = if app.active_panel == ActivePanel::Stream { " [ SELECTED: NEURAL STREAM ] " } else { " NEURAL STREAM " };
    let stream = List::new(messages)
        .block(Block::default().borders(Borders::ALL).title(s_title).border_style(s_style));
    f.render_stateful_widget(stream, panel_layout[1], &mut app.list_state);

    // 4. Right: Action Matrix
    let actions: Vec<ListItem> = app.actions.iter().enumerate().map(|(i, a)| {
        let style = if i == app.action_index && app.active_panel == ActivePanel::Actions {
            Style::default().fg(Color::Black).bg(Color::Green).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)
        };
        ListItem::new(Line::from(vec![Span::styled(format!(" [{}] ", a), style)]))
    }).collect();

    let a_title = if app.active_panel == ActivePanel::Actions { " [ SELECTED: ACTIONS (Up/Down to select) ] " } else { " ACTIONS " };
    let actions_list = List::new(actions)
        .block(Block::default().borders(Borders::ALL).title(a_title).border_style(a_style));
    f.render_widget(actions_list, panel_layout[2]);

    // 5. Bottom: Input Command
    let i_title = if app.active_panel == ActivePanel::Input { " [ SELECTED: COMMAND MATRIX (Type here) ] " } else { " COMMAND MATRIX " };
    let input_text = format!("> {}", app.input);
    let input = Paragraph::new(input_text)
        .style(Style::default().fg(Color::Green))
        .block(Block::default().borders(Borders::ALL).title(i_title).border_style(i_style));
    f.render_widget(input, main_layout[2]);
    
    // Help hint
    let help_hint = Paragraph::new(" [TAB] Cycle Panels | [ENTER] Execute | [^L] Clear | [^A] Launch mission from Matrix ")
        .style(Style::default().fg(Color::Rgb(120, 120, 120)))
        .alignment(ratatui::layout::Alignment::Right);
    
    f.render_widget(help_hint, main_layout[2]);
}
