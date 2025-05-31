use crate::model::Id;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Contact {
    pub id: Id,
    pub display_name: String,
    pub online: bool,
}

impl Contact {
    pub fn new(name: &str) -> Self {
        Self {
            id: name.to_string(),
            display_name: name.to_string(),
            online: true,
        }
    }
}
