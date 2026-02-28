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
    widgets::{Block, Borders, Paragraph, List, ListItem},
    Frame, Terminal,
};
use std::{io, time::{Duration, Instant}};
use tokio::sync::mpsc;
use futures_util::StreamExt;
use tokio_tungstenite::connect_async;
use serde_json::Value;

struct App {
    frame_count: u64,
    messages: Vec<String>,
    scroll: u16,
}

impl App {
    fn new() -> App {
        App { 
            frame_count: 0,
            messages: vec!["Initializing neural links...".to_string()],
            scroll: 0,
        }
    }

    fn on_tick(&mut self) {
        self.frame_count += 1;
    }

    fn add_message(&mut self, msg: String) {
        self.messages.push(msg);
        if self.messages.len() > 100 {
            self.messages.remove(0);
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
    tokio::spawn(async move {
        let url = "ws://127.0.0.1:18789/ws";
        if let Ok((mut ws_stream, _)) = connect_async(url).await {
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
                }
            }
        }
    });

    // create app and run it
    let tick_rate = Duration::from_millis(50);
    let mut app = App::new();
    let res = run_app(&mut terminal, &mut app, tick_rate, &mut rx).await;

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
) -> io::Result<()> {
    let mut last_tick = Instant::now();
    loop {
        terminal.draw(|f| ui(f, app))?;

        let timeout = tick_rate
            .checked_sub(last_tick.elapsed())
            .unwrap_or_else(|| Duration::from_secs(0));
        
        if crossterm::event::poll(timeout)? {
            if let Event::Key(key) = event::read()? {
                if let KeyCode::Char('q') = key.code {
                    return Ok(());
                }
            }
        }

        // Process incoming WebSocket messages
        while let Ok(msg) = rx.try_recv() {
            app.add_message(msg);
        }

        if last_tick.elapsed() >= tick_rate {
            app.on_tick();
            last_tick = Instant::now();
        }
    }
}

fn ui(f: &mut Frame, app: &App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .margin(1)
        .constraints(
            [
                Constraint::Length(10),
                Constraint::Min(0),
                Constraint::Length(3),
            ]
            .as_ref(),
        )
        .split(f.size());

    // Animated Banner
    let colors = [
        Color::Red,
        Color::Yellow,
        Color::Green,
        Color::Cyan,
        Color::Blue,
        Color::Magenta,
    ];
    let color = colors[(app.frame_count / 2 % 6) as usize];

    let banner_text = "
   _____  __      __  ___   ____    __  __ 
  / ____| \\ \\    / / / _ \\ |  _ \\  |  \\/  |
 | (___    \\ \\  / / | |_| || |_) | | \\  / |
  \\___ \\    \\ \\/ /  |  _  ||  _ <  | |\\/| |
  ____) |    \\  /   | | | || | | | | |  | |
 |_____/      \\/    |_| |_||_| |_| |_|  |_|
                                           
        >>> SWARM DISPATCH ACTIVE <<<
";
    let banner = Paragraph::new(banner_text)
        .style(Style::default().fg(color).add_modifier(Modifier::BOLD))
        .alignment(ratatui::layout::Alignment::Center)
        .block(Block::default().borders(Borders::ALL).title(" SYSTEM CORE "));
    
    f.render_widget(banner, chunks[0]);

    // Messages List
    let items: Vec<ListItem> = app.messages.iter().map(|m| {
        let style = if m.contains("THOUGHT") {
            Style::default().fg(Color::Cyan).add_modifier(Modifier::ITALIC)
        } else if m.contains("TOOL") {
            Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(Color::Gray)
        };
        ListItem::new(Line::from(vec![Span::styled(m, style)]))
    }).collect();

    let list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title(" EVENT STREAM "));
    
    f.render_widget(list, chunks[1]);

    // Input Bar
    let input = Paragraph::new("> Init system sequence...")
        .style(Style::default().fg(Color::Green))
        .block(Block::default().borders(Borders::ALL).title(" COMMAND MATRIX "));
    f.render_widget(input, chunks[2]);
}
