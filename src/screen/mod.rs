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
    // Navigation methods removed; focus switching now handled in event handlers

    /// Get a mutable reference to the ChatScreen, if active
    pub fn as_chat_mut(&mut self) -> Option<&mut ChatScreen> {
        match &mut self.current {
            Screen::Chat(chat) => Some(chat),
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
