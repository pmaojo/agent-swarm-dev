mod cli;

use anyhow::Result;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::{Backend, CrosstermBackend},
    Terminal,
};
use std::{io, time::{Duration, Instant}};
use tokio::sync::mpsc;

use crate::cli::app::{App, ActivePanel};
use crate::cli::ui::draw_ui;
use crate::cli::handlers::{spawn_telemetry_handler, spawn_command_handler};

// Cleanup function to restore terminal on exit/crash
fn cleanup_terminal() {
    eprint!("\x1b[?1049l");  // Exit alternate screen
    eprint!("\x1bc");         // Reset terminal  
    eprint!("\x1b[?1000l");   // Disable mouse
    eprint!("\n");
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

    // Setup communication channels
    let (tx_msg, mut rx_msg) = mpsc::channel(100);
    let (command_tx_ext, command_rx) = mpsc::channel::<String>(10);
    let (status_tx, mut status_rx) = mpsc::channel(1);

    // Spawn modular handlers
    spawn_telemetry_handler(tx_msg.clone(), status_tx).await;
    spawn_command_handler(tx_msg.clone(), command_rx, command_tx_ext.clone()).await;

    // create app and run it
    let tick_rate = Duration::from_millis(50);
    let mut app = App::new().await;
    
    let res = run_app(&mut terminal, &mut app, tick_rate, &mut rx_msg, &mut status_rx, command_tx_ext).await;

    // restore terminal
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

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
    rx_msg: &mut mpsc::Receiver<String>,
    status_rx: &mut mpsc::Receiver<bool>,
    command_tx: mpsc::Sender<String>,
) -> io::Result<()> {
    let mut last_tick = Instant::now();
    loop {
        terminal.draw(|f| draw_ui(f, app))?;

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
                            app.add_message(format!("[SYSTEM] Requesting: {}", action));
                            let _ = command_tx.try_send(action);
                        } else if app.active_panel == ActivePanel::Knowledge {
                            if let Some(idx) = app.knowledge_state.selected() {
                                if let Some(node) = app.knowledge_nodes.get(idx).cloned() {
                                    app.add_message(format!("[SYSTEM] Accessing knowledge core: {}", node.name));
                                    let _ = command_tx.try_send(format!("KNOWLEDGE:{}", node.id));
                                }
                            }
                        }
                    },
                    KeyCode::Char('l') if key.modifiers.contains(crossterm::event::KeyModifiers::CONTROL) => {
                        app.clear_messages();
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

        while let Ok(msg) = rx_msg.try_recv() {
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
