use crate::model::Id;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct User {
    pub id: Id,
    pub username: String,
    pub display_name: String,
    pub online: bool,
}
