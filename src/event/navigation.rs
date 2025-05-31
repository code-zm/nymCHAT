use crate::app::App;
use crossterm::event::KeyCode;

pub fn handle_navigation(app: &mut App, key: KeyCode) {
    match key {
        KeyCode::Left => app.screen.prev_section(),
        KeyCode::Right => app.screen.next_section(),
        _ => {}
    }
}

