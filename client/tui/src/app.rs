use crate::event::handle_events;
use crate::model::user::User;
use crate::screen::ScreenState;
use ratatui::{DefaultTerminal, Frame};
use std::io;

pub struct App {
    pub running: bool,
    pub screen: ScreenState,
    pub logged_in_user: Option<User>,
    pub input_buffer: String,
}

impl App {
    pub fn new() -> Self {
        Self {
            running: true,
            screen: ScreenState::default(),
            logged_in_user: None,
            input_buffer: String::new(),
        }
    }

    pub async fn run(&mut self, terminal: &mut DefaultTerminal) -> io::Result<()> {
        while self.running {
            terminal.draw(|frame| self.draw(frame))?;
            handle_events(self)?;
        }
        Ok(())
    }

    pub fn draw(&mut self, frame: &mut Frame) {
        crate::ui::render_ui(self, frame);
    }

    pub fn quit(&mut self) {
        self.running = false;
    }
}

