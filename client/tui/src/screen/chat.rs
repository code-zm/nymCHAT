use crate::model::contact::Contact;
use crate::model::message::Message;
use ratatui::widgets::ListState;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChatSection {
    Contacts,
    Messages,
    Input,
}

impl ChatSection {
    pub fn all() -> Vec<Self> {
        vec![Self::Contacts, Self::Messages, Self::Input]
    }

    pub fn next(&self) -> Self {
        let idx = self.to_index().saturating_add(1);
        Self::from_index(idx)
    }

    pub fn prev(&self) -> Self {
        let idx = self.to_index().saturating_sub(1);
        Self::from_index(idx)
    }

    pub fn to_index(&self) -> usize {
        Self::all().iter().position(|s| s == self).unwrap()
    }

    pub fn from_index(i: usize) -> Self {
        Self::all().get(i).cloned().unwrap_or(Self::Input)
    }
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
        contacts_state.select(Some(0));

        let contacts = vec![
            Contact::new("alice"),
            Contact::new("bob"),
            Contact::new("charlie"),
        ];

        let messages = vec![
            (0..30).map(|i| Message::new("alice", &format!("Hi from Alice {}", i))).collect(),
            (0..20).map(|i| Message::new("bob", &format!("Hi from Bob {}", i))).collect(),
            (0..10).map(|i| Message::new("charlie", &format!("Hi from Charlie {}", i))).collect(),
        ];

        Self {
            section: ChatSection::Messages,
            contacts,
            selected_contact: None,
            highlighted_contact: 0,
            messages,
            chat_scroll: 0,
            contacts_state,
        }
    }
}

impl ChatScreen {
    pub fn next_section(&mut self) {
        self.section = self.section.next();
    }

    pub fn prev_section(&mut self) {
        self.section = self.section.prev();
    }
}

