mod navigation;

use crate::app::App;
use crate::event::navigation::handle_navigation;
use crate::screen::chat::ChatSection;
use crossterm::event::{self, Event as CEvent, KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use std::io;

pub fn handle_events(app: &mut App) -> io::Result<()> {
    if let CEvent::Key(key_event) = event::read()? {
        if key_event.kind == KeyEventKind::Press {
            if key_event.modifiers.contains(KeyModifiers::CONTROL) {
                handle_control_keys(app, key_event);
            } else {
                handle_key(app, key_event);
            }
        }
    }
    Ok(())
}

fn handle_control_keys(app: &mut App, event: KeyEvent) {
    match event.code {
        KeyCode::Char('q') => app.quit(),
        _ => {}
    }
}

fn handle_key(app: &mut App, event: KeyEvent) {
    // handle navigation first to avoid double borrowing
    let section = app.screen.section();
    match event.code {
        KeyCode::Left | KeyCode::Right => handle_navigation(app, event.code),
        _ => {}
    }

    if let Some(chat) = app.screen.as_chat_mut() {
        match chat.section {
            ChatSection::Contacts => match event.code {
                KeyCode::Up => {
                    if chat.highlighted_contact > 0 {
                        chat.highlighted_contact -= 1;
                        chat.contacts_state.select(Some(chat.highlighted_contact));
                    }
                }
                KeyCode::Down => {
                    if chat.highlighted_contact < chat.contacts.len().saturating_sub(1) {
                        chat.highlighted_contact += 1;
                        chat.contacts_state.select(Some(chat.highlighted_contact));
                    }
                }
                KeyCode::Enter => {
                    chat.selected_contact = Some(chat.highlighted_contact);
                    chat.section = ChatSection::Messages;
                    chat.chat_scroll = chat.messages[chat.highlighted_contact].len().saturating_sub(1);
                }
                _ => {}
            },
            ChatSection::Messages => match event.code {
                KeyCode::Up => {
                    chat.chat_scroll = chat.chat_scroll.saturating_sub(1);
                }
                KeyCode::Down => {
                    if let Some(selected) = chat.selected_contact {
                        let max = chat.messages[selected].len().saturating_sub(1);
                        chat.chat_scroll = chat.chat_scroll.saturating_add(1).min(max);
                    }
                }
                KeyCode::Char('i') => chat.section = ChatSection::Input,
                KeyCode::Tab => chat.section = ChatSection::Contacts,
                KeyCode::Esc => chat.section = ChatSection::Messages,
                KeyCode::Char('q') => app.quit(),
                _ => {}
            },
            ChatSection::Input => match event.code {
                KeyCode::Char(c) => {
                    app.input_buffer.push(c);
                }
                KeyCode::Backspace => {
                    app.input_buffer.pop();
                }
                KeyCode::Enter => {
                    if let Some(selected) = chat.selected_contact {
                        let sender = "you";
                        let message = crate::model::message::Message::new(sender, &app.input_buffer);
                        chat.messages[selected].push(message);
                        app.input_buffer.clear();
                    }
                }
                KeyCode::Esc => chat.section = ChatSection::Messages,
                _ => {}
            },
        }
    }
}

