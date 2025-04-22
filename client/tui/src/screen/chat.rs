use crate::model::contact::Contact;
use crate::model::message::Message;
use ratatui::widgets::ListState;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChatSection {
    Contacts,
    Messages,
    Input,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChatScreen {
    pub section: ChatSection,
    pub contacts: Vec<Contact>,
    pub selected_contact: Option<usize>,
    pub highlighted_contact: usize,
    pub messages: Vec<Vec<Message>>,
    pub chat_scroll: usize,
    pub contacts_state: ListState,
}

impl Default for ChatScreen {
    fn default() -> Self {
        let mut contacts_state = ListState::default();
        contacts_state.select(None);
        Self {
            section: ChatSection::Messages,
            contacts: Vec::new(),
            selected_contact: None,
            highlighted_contact: 0,
            messages: Vec::new(),
            chat_scroll: 0,
            contacts_state,
        }
    }
}

// ChatScreen focus-cycling removed; input/navigation now handled in event handlers
