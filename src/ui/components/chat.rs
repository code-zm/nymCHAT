use crate::app::App;
use crate::model::message::Message;
use crate::screen::chat::ChatSection;
use ratatui::{
    Frame,
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span, Text},
    widgets::{Block, Borders, List, ListItem, Paragraph, Wrap},
};
use serde::de::Error;
use serde_json::Value;

pub fn render_chat(
    app: &App,
    chat: &crate::screen::chat::ChatScreen,
    frame: &mut Frame,
    area: ratatui::layout::Rect,
) {
    let layout = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(20), Constraint::Percentage(80)])
        .split(area);

    let left = layout[0];
    let right = layout[1];

    // === CONTACTS LIST ===
    let contact_items: Vec<ListItem> = chat
        .contacts
        .iter()
        .enumerate()
        .map(|(i, contact)| {
            let style = if i == chat.highlighted_contact {
                Style::default()
                    .fg(Color::Yellow)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default()
            };
            ListItem::new(Span::styled(contact.display_name.clone(), style))
        })
        .collect();

    let contacts_border = if chat.section == ChatSection::Contacts {
        Style::default().fg(Color::Green)
    } else {
        Style::default()
    };

    let contacts = List::new(contact_items).block(
        Block::default()
            .borders(Borders::ALL)
            .title("Contacts")
            .border_style(contacts_border),
    );
    frame.render_stateful_widget(contacts, left, &mut chat.contacts_state.clone());

    // === RIGHT SIDE ===
    let right_layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Percentage(85), Constraint::Percentage(15)])
        .split(right);

    let messages_area = right_layout[0];
    let input_area = right_layout[1];

    let chat_messages: Vec<Line> = if let Some(selected) = chat.selected_contact {
        chat.messages[selected]
            .iter()
            .map(message_to_line)
            .collect()
    } else {
        vec![Line::from("Select a contact to view messages.")]
    };

    let messages = Paragraph::new(Text::from(chat_messages))
        .block(Block::default().borders(Borders::ALL).title("Chat"))
        .wrap(Wrap { trim: false })
        .scroll((chat.chat_scroll as u16, 0));
    frame.render_widget(messages, messages_area);

    let input_border = if chat.section == ChatSection::Input {
        Style::default().fg(Color::Green)
    } else {
        Style::default()
    };

    let input = Paragraph::new(app.input_buffer.clone())
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Input")
                .border_style(input_border),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(input, input_area);
}

fn message_to_line(msg: &Message) -> Line {
    // try to parse JSON payload and extract the inner text
    let text = serde_json::from_str::<Value>(&msg.content)
        .and_then(|v| {
            // look for either "message" or "body"
            v.get("message")
                .or_else(|| v.get("body"))
                .and_then(|f| f.as_str().map(str::to_string))
                .ok_or_else(|| serde_json::Error::custom("no chat field"))
        })
        .unwrap_or_else(|_| msg.content.clone());

    Line::from(Span::raw(format!("[{}] {}", msg.sender, text)))
}
