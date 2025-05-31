use crate::model::Id;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Message {
    pub sender: Id,
    pub content: String,
    pub timestamp: DateTime<Utc>,
}

impl Message {
    pub fn new(sender: &str, content: &str) -> Self {
        Self {
            sender: sender.to_string(),
            content: content.to_string(),
            timestamp: Utc::now(),
        }
    }
}
