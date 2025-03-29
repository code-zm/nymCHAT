mod components;
mod layout;

use crate::app::App;
use ratatui::Frame;

pub fn render_ui(app: &App, frame: &mut Frame) {
    let layout = layout::main_layout(frame);

    // Header will go here in future if needed
    // frame.render_widget(..., layout.header);

    match &app.screen.current {
        crate::screen::Screen::Chat(chat) => {
            components::chat::render_chat(app, chat, frame, layout.content);
        }
    }

    components::footer::render_footer(app, frame, layout.footer);
}

