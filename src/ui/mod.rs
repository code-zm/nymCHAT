mod components;
mod layout;
pub mod widgets;

use crate::app::App;
use ratatui::{Frame, layout::Rect};

pub fn render_ui(app: &App, frame: &mut Frame, area: Rect) {
    let layout = layout::main_layout(area);

    // Header will go here in future if needed
    // frame.render_widget(..., layout.header);

    let crate::screen::Screen::Chat(chat) = &app.screen.current;
    components::chat::render_chat(app, chat, frame, layout.content);
    components::footer::render_footer(app, frame, layout.footer);
}
