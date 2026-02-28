use anyhow::Result;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::{Backend, CrosstermBackend},
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Span, Line},
    widgets::{Block, Borders, Paragraph, List, ListItem, ListState, Clear},
    Frame, Terminal,
};
use std::{io, time::{Duration, Instant}};
use tokio::sync::mpsc;
use futures_util::StreamExt;
use tokio_tungstenite::connect_async;
use serde_json::Value;

#[derive(PartialEq, Eq, Clone, Copy)]
enum ActivePanel {
    Input,
    Knowledge,
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
    actions: Vec<String>,
    action_index: usize,
}

impl App {
    fn new() -> App {
        let mut list_state = ListState::default();
        list_state.select(Some(0));
        let mut knowledge_state = ListState::default();
        knowledge_state.select(Some(0));
        App { 
            frame_count: 0,
            messages: vec!["Initializing neural links...".to_string()],
            input: String::new(),
            connected: false,
            list_state,
            active_panel: ActivePanel::Input,
            knowledge_nodes: vec![
                "Neural Link v1".to_string(),
                "Cyber-Psychosis Guard".to_string(),
                "Quantum Compiler".to_string(),
                "Swarm Mind v2".to_string(),
                "NIST Authorization".to_string(),
            ],
            knowledge_state,
            actions: vec![
                "LAUNCH MISSION".to_string(),
                "HALT SWARM".to_string(),
                "RESET BRAIN".to_string(),
                "SCAN SECTOR".to_string(),
            ],
            action_index: 0,
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
        };
    }

    fn handle_input(&mut self, input: String, command_tx: &mpsc::Sender<String>) {
        let normalized = input.trim().to_lowercase();
        if normalized == "hello" || normalized == "hola" {
            self.add_message("[SYSTEM] Neural link established. Hello, Operator.".to_string());
        } else if normalized == "status" {
            let status = if self.connected { "SECURE" } else { "SEVERED" };
            self.add_message(format!("[SYSTEM] Core telemetry: {}", status));
        } else if normalized == "mission" || normalized == "launch" {
            self.add_message("[SYSTEM] Mission protocols identified. Use ACTION matrix to execute.".to_string());
        } else if normalized == "help" {
            self.add_message("[SYSTEM] Available: hello, status, mission, help, or any command to assign a mission".to_string());
        } else {
            // Send as a real mission
            self.add_message(format!("[SYSTEM] Assigning mission: {}", input));
            let _ = command_tx.try_send(input);
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // setup terminal
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // Setup WebSocket communication
    let (tx, mut rx) = mpsc::channel(100);
    let (command_tx, mut command_rx) = mpsc::channel(10);
    let (status_tx, mut status_rx) = mpsc::channel(1);

    tokio::spawn(async move {
        let url = "ws://127.0.0.1:18792/api/v1/events/combat/stream";
        let client = reqwest::Client::new();
        
        loop {
            // Check for outgoing commands
            while let Ok(cmd) = command_rx.try_recv() {
                if cmd == "LAUNCH MISSION" {
                    let _ = client.post("http://127.0.0.1:18792/api/v1/mission/assign")
                        .json(&serde_json::json!({
                            "agent_id": "http://swarm.os/agents/Coder",
                            "repo_id": "root",
                            "task": "Scan and analyze neural nodes"
                        }))
                        .send()
                        .await;
                } else {
                    // Regular command from TUI input
                    let _ = client.post("http://127.0.0.1:18792/api/v1/mission/assign")
                        .json(&serde_json::json!({
                            "agent_id": "http://swarm.os/agents/Coder",
                            "repo_id": "root",
                            "task": cmd
                        }))
                        .send()
                        .await;
                }
            }

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
                                    let _ = tx.send(formatted).await;
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
    let mut app = App::new();
    let res = run_app(&mut terminal, &mut app, tick_rate, &mut rx, &mut status_rx, command_tx).await;

    // restore terminal
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    if let Err(err) = res {
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
                    KeyCode::Tab => app.next_panel(),
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
                    KeyCode::Esc => return Ok(()),
                    _ => {}
                }
            }
        }

        while let Ok(msg) = rx.try_recv() {
            app.add_message(msg);
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
    
    // Scanline effect (subtle animation via background colors)
    if app.frame_count % 20 == 0 {
        // We could render something subtle here, but let's focus on layout first
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
   __ _ _ _ ___ ___ _____ 
  | _ | | | | _ | _ |     |
  |___|__|_||_|_| _| _| _|_|
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

    // 2. Sidebar: Knowledge Explorer
    let knowledge_items: Vec<ListItem> = app.knowledge_nodes.iter().map(|k| {
        ListItem::new(Line::from(vec![
            Span::styled("● ", Style::default().fg(Color::Cyan)),
            Span::styled(k, Style::default().fg(Color::Gray)),
        ]))
    }).collect();
    
    let k_title = if app.active_panel == ActivePanel::Knowledge { " [ SELECTED: KNOWLEDGE ] " } else { " KNOWLEDGE " };
    let knowledge = List::new(knowledge_items)
        .block(Block::default().borders(Borders::ALL).title(k_title).border_style(k_border_style))
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
        } else {
            Style::default().fg(Color::Gray)
        };
        ListItem::new(Line::from(vec![Span::styled(m, style)]))
    }).collect();

    let s_title = if app.active_panel == ActivePanel::Stream { " [ SELECTED: NEURAL STREAM ] " } else { " NEURAL STREAM " };
    let stream = List::new(messages)
        .block(Block::default().borders(Borders::ALL).title(s_title).border_style(s_border_style));
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

    let a_title = if app.active_panel == ActivePanel::Actions { " [ SELECTED: ACTIONS ] " } else { " ACTIONS " };
    let actions_list = List::new(actions)
        .block(Block::default().borders(Borders::ALL).title(a_title).border_style(a_border_style));
    f.render_widget(actions_list, panel_layout[2]);

    // 5. Bottom: Input Command
    let i_title = if app.active_panel == ActivePanel::Input { " [ SELECTED: COMMAND MATRIX ] " } else { " COMMAND MATRIX " };
    let input_text = format!("> {}", app.input);
    let input = Paragraph::new(input_text)
        .style(Style::default().fg(Color::Green))
        .block(Block::default().borders(Borders::ALL).title(i_title).border_style(i_border_style));
    f.render_widget(input, main_layout[2]);
    
    // Help hint
    let help_hint = Paragraph::new(" [TAB] Switch | [ENTER] Run | [^L] Clear | [^R] Sync | [^A] Launch Mission ")
        .style(Style::default().fg(Color::Rgb(100, 100, 100)))
        .alignment(ratatui::layout::Alignment::Right);
    
    f.render_widget(help_hint, main_layout[2]);
}
