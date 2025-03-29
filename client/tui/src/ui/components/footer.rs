use crate::app::App;
use ratatui::{
    layout::Alignment,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::Paragraph,
    Frame,
};

pub fn render_footer(_app: &App, frame: &mut Frame, area: ratatui::layout::Rect) {
    let line = Line::from(vec![
        Span::styled(" Tab - Contacts ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        Span::raw("|"),
        Span::styled(" i - Input ", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
        Span::raw("|"),
        Span::styled(" Esc - Back ", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
        Span::raw("|"),
        Span::styled(" q - Quit ", Style::default().fg(Color::Red).add_modifier(Modifier::BOLD)),
    ]);

    let widget = Paragraph::new(line).alignment(Alignment::Center);
    frame.render_widget(widget, area);
}

