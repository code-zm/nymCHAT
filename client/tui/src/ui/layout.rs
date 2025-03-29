use ratatui::layout::{Constraint, Direction, Layout, Rect};

pub struct MainLayout {
    pub content: Rect,
    pub footer: Rect,
}

pub fn main_layout(frame: &mut ratatui::Frame) -> MainLayout {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(0),    // content
            Constraint::Length(1), // footer
        ])
        .split(frame.area());

    MainLayout {
        content: chunks[0],
        footer: chunks[1],
    }
}



