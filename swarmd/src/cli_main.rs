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
    text::{Span, Spans},
    widgets::{Block, Borders, Paragraph, Wrap},
    Frame, Terminal,
};
use std::{io, time::{Duration, Instant}};

struct App {
    frame_count: u64,
}

impl App {
    fn new() -> App {
        App { frame_count: 0 }
    }

    fn on_tick(&mut self) {
        self.frame_count += 1;
    }
}

fn main() -> Result<()> {
    // setup terminal
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // create app and run it
    let tick_rate = Duration::from_millis(50);
    let mut app = App::new();
    let res = run_app(&mut terminal, &mut app, tick_rate);

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

fn run_app<B: Backend>(
    terminal: &mut Terminal<B>,
    app: &mut App,
    tick_rate: Duration,
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
        if last_tick.elapsed() >= tick_rate {
            app.on_tick();
            last_tick = Instant::now();
        }
    }
}

fn ui<B: Backend>(f: &mut Frame<B>, app: &App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .margin(1)
        .constraints(
            [
                Constraint::Length(10),
                Constraint::Min(0),
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

    // Main Content Placeholder
    let content = Paragraph::new("Press 'q' to exit. Initializing neural links...")
        .style(Style::default().fg(Color::Gray))
        .block(Block::default().borders(Borders::ALL).title(" THOUGHT STREAM "));
    f.render_widget(content, chunks[1]);
}
