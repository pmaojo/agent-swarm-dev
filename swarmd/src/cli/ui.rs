use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Span, Line},
    widgets::{Block, Borders, Paragraph, List, ListItem},
    Frame,
};
use crate::cli::app::{App, ActivePanel};

pub fn draw_ui(f: &mut Frame, app: &mut App) {
    let size = f.size();
    
    if app.active_panel == ActivePanel::KnowledgeDetail {
        draw_knowledge_detail(f, app, size);
        return;
    }

    let main_layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(5),
            Constraint::Min(0),
            Constraint::Length(3),
        ])
        .split(size);

    let panel_layout = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(25),
            Constraint::Percentage(60),
            Constraint::Percentage(15),
        ])
        .split(main_layout[1]);

    draw_logo(f, app, main_layout[0]);
    draw_knowledge(f, app, panel_layout[0]);
    draw_stream(f, app, panel_layout[1]);
    draw_actions(f, app, panel_layout[2]);
    draw_input(f, app, main_layout[2]);
}

fn draw_knowledge_detail(f: &mut Frame, app: &mut App, size: Rect) {
    let block = Block::default()
        .borders(Borders::ALL)
        .title(Span::styled(" KNOWLEDGE CORE: DEEP INSPECTION ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)))
        .border_style(Style::default().fg(Color::Cyan));
    
    let detail_text = Paragraph::new(app.active_node_detail.as_str())
        .block(block)
        .wrap(ratatui::widgets::Wrap { trim: true });
        
    f.render_widget(detail_text, size);
    
    let help_rect = Rect::new(size.x + size.width - 25, size.y + size.height - 2, 24, 1);
    let help_hint = Paragraph::new(" [ESC] Return to Swarm ")
        .style(Style::default().fg(Color::Rgb(120, 120, 120)))
        .alignment(ratatui::layout::Alignment::Right);
    f.render_widget(help_hint, help_rect);
}

fn draw_logo(f: &mut Frame, app: &App, area: Rect) {
    let colors = [Color::Red, Color::Yellow, Color::Green, Color::Cyan, Color::Blue, Color::Magenta];
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
    f.render_widget(logo, area);
}

fn draw_knowledge(f: &mut Frame, app: &mut App, area: Rect) {
    let style = if app.active_panel == ActivePanel::Knowledge { Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD) } else { Style::default().fg(Color::DarkGray) };
    let knowledge_items: Vec<ListItem> = app.knowledge_nodes.iter().map(|k| {
        ListItem::new(Line::from(vec![
            Span::styled("● ", Style::default().fg(if k.id.contains("LOCKED") { Color::Red } else { Color::Cyan })),
            Span::styled(format!("{:<15} ", format!("[{}]", k.domain)), Style::default().fg(Color::DarkGray)),
            Span::styled(&k.name, Style::default().fg(Color::Gray)),
            Span::styled(format!(" L{}", k.level), Style::default().fg(Color::Rgb(100, 100, 100))),
        ]))
    }).collect();
    
    let title = if app.active_panel == ActivePanel::Knowledge { " [ SELECTED: KNOWLEDGE (Up/Down) ] " } else { " KNOWLEDGE " };
    let list = List::new(knowledge_items)
        .block(Block::default().borders(Borders::ALL).title(title).border_style(style))
        .highlight_style(Style::default().bg(Color::Rgb(30, 30, 50)).add_modifier(Modifier::BOLD))
        .highlight_symbol(">> ");
    f.render_stateful_widget(list, area, &mut app.knowledge_state);
}

fn draw_stream(f: &mut Frame, app: &mut App, area: Rect) {
    let style = if app.active_panel == ActivePanel::Stream { Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD) } else { Style::default().fg(Color::DarkGray) };
    let messages: Vec<ListItem> = app.messages.iter().map(|m| {
        let line_style = if m.contains("[THOUGHT]") {
            Style::default().fg(Color::Cyan).add_modifier(Modifier::ITALIC)
        } else if m.contains("[TOOL]") {
            Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)
        } else if m.contains("[USER]") {
            Style::default().fg(Color::Green)
        } else if m.contains("[AI]") {
             Style::default().fg(Color::Magenta).add_modifier(Modifier::BOLD)
        } else if m.contains("[SUCCESS]") {
            Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)
        } else if m.contains("[ERROR]") {
            Style::default().fg(Color::Red).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(Color::Gray)
        };
        ListItem::new(Line::from(vec![Span::styled(m, line_style)]))
    }).collect();

    let title = if app.active_panel == ActivePanel::Stream { " [ SELECTED: NEURAL STREAM ] " } else { " NEURAL STREAM " };
    let list = List::new(messages)
        .block(Block::default().borders(Borders::ALL).title(title).border_style(style));
    f.render_stateful_widget(list, area, &mut app.list_state);
}

fn draw_actions(f: &mut Frame, app: &App, area: Rect) {
    let style = if app.active_panel == ActivePanel::Actions { Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD) } else { Style::default().fg(Color::DarkGray) };
    let actions: Vec<ListItem> = app.actions.iter().enumerate().map(|(i, a)| {
        let item_style = if i == app.action_index && app.active_panel == ActivePanel::Actions {
            Style::default().fg(Color::Black).bg(Color::Green).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)
        };
        ListItem::new(Line::from(vec![Span::styled(format!(" [{}] ", a), item_style)]))
    }).collect();

    let title = if app.active_panel == ActivePanel::Actions { " [ ACTIONS ] " } else { " ACTIONS " };
    let list = List::new(actions)
        .block(Block::default().borders(Borders::ALL).title(title).border_style(style));
    f.render_widget(list, area);
}

fn draw_input(f: &mut Frame, app: &App, area: Rect) {
    let style = if app.active_panel == ActivePanel::Input { Style::default().fg(Color::Green).add_modifier(Modifier::BOLD) } else { Style::default().fg(Color::DarkGray) };
    let input_text = format!("> {}", app.input);
    let title = if app.active_panel == ActivePanel::Input { " [ COMMAND MATRIX ] " } else { " COMMAND MATRIX " };
    
    let input = Paragraph::new(input_text)
        .style(Style::default().fg(Color::Green))
        .block(Block::default().borders(Borders::ALL).title(title).border_style(style));
    f.render_widget(input, area);

    let help_hint = Paragraph::new(" [TAB] Cycle Panels | [ENTER] Execute | [^L] Clear | [^A] Quick Mission ")
        .style(Style::default().fg(Color::Rgb(120, 120, 120)))
        .alignment(ratatui::layout::Alignment::Right);
    
    let mut help_area = area;
    help_area.y += 1;
    help_area.height = 1;
    help_area.x += 2;
    help_area.width -= 4;
    f.render_widget(help_hint, help_area);
}
