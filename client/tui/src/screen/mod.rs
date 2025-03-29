pub mod chat;

use chat::ChatScreen;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Screen {
    Chat(ChatScreen),
}

#[derive(Debug)]
pub struct ScreenState {
    pub current: Screen,
}

impl ScreenState {
    pub fn next_section(&mut self) {
        match &mut self.current {
            Screen::Chat(screen) => screen.next_section(),
        }
    }

    pub fn prev_section(&mut self) {
        match &mut self.current {
            Screen::Chat(screen) => screen.prev_section(),
        }
    }

    pub fn section(&self) -> usize {
        match &self.current {
            Screen::Chat(screen) => screen.section.to_index(),
        }
    }

    pub fn is_chat(&self) -> bool {
        matches!(self.current, Screen::Chat(_))
    }

    pub fn as_chat_mut(&mut self) -> Option<&mut ChatScreen> {
        if let Screen::Chat(chat) = &mut self.current {
            Some(chat)
        } else {
            None
        }
    }

    pub fn as_chat(&self) -> Option<&ChatScreen> {
        if let Screen::Chat(chat) = &self.current {
            Some(chat)
        } else {
            None
        }
    }
}

impl Default for ScreenState {
    fn default() -> Self {
        Self {
            current: Screen::Chat(ChatScreen::default()),
        }
    }
}

