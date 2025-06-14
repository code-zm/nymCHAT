use crate::app::App;
use crate::screen::chat::ChatSection;
use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use std::io;

/// Handle the single KeyEvent you already read in App::run
pub fn handle_key_event(app: &mut App, key_event: KeyEvent) -> io::Result<()> {
    if key_event.kind != KeyEventKind::Press {
        return Ok(());
    }

    // Global control keys (e.g., Ctrl+q quits)
    if key_event.modifiers.contains(KeyModifiers::CONTROL) {
        if key_event.code == KeyCode::Char('q') {
            app.quit();
        }
        return Ok(());
    }

    // Chat section-specific behavior
    if let Some(chat) = app.screen.as_chat_mut() {
        match chat.section {
            // neutral: Tab→Contacts, i→Input, s→Search phase, q→Quit
            ChatSection::Messages => match key_event.code {
                KeyCode::Tab => {
                    chat.section = ChatSection::Contacts;
                    chat.contacts_state.select(Some(chat.highlighted_contact));
                }
                KeyCode::Char('i') => {
                    chat.section = ChatSection::Input;
                }
                KeyCode::Char('s') => {
                    app.phase = crate::app::Phase::Search;
                }
                KeyCode::Char('q') => {
                    app.quit();
                }
                _ => {}
            },

            // Contacts navigation mode
            ChatSection::Contacts => match key_event.code {
                KeyCode::Up => {
                    if chat.highlighted_contact > 0 {
                        chat.highlighted_contact -= 1;
                    }
                    chat.contacts_state.select(Some(chat.highlighted_contact));
                }
                KeyCode::Down => {
                    let next =
                        (chat.highlighted_contact + 1).min(chat.contacts.len().saturating_sub(1));
                    chat.highlighted_contact = next;
                    chat.contacts_state.select(Some(chat.highlighted_contact));
                }
                KeyCode::Tab => {
                    let next =
                        (chat.highlighted_contact + 1).min(chat.contacts.len().saturating_sub(1));
                    chat.highlighted_contact = next;
                    chat.contacts_state.select(Some(chat.highlighted_contact));
                }
                KeyCode::Enter => {
                    chat.selected_contact = Some(chat.highlighted_contact);
                    chat.section = ChatSection::Messages;
                }
                KeyCode::Esc => {
                    chat.section = ChatSection::Messages;
                }
                _ => {}
            },

            // Input mode (typing)
            ChatSection::Input => {
                match key_event.code {
                    KeyCode::Char(c) => {
                        app.input_buffer.push(c);
                    }
                    KeyCode::Tab => {
                        app.input_buffer.push('\t');
                    }
                    KeyCode::Backspace => {
                        app.input_buffer.pop();
                    }
                    KeyCode::Enter => {
                        if let Some(sel) = chat.selected_contact {
                            // local echo
                            let text = std::mem::take(&mut app.input_buffer);
                            let sender = app
                                .logged_in_user
                                .as_ref()
                                .map(|u| u.username.as_str())
                                .unwrap_or("you");
                            chat.messages[sel]
                                .push(crate::model::message::Message::new(sender, &text));
                            // enqueue for network
                            app.pending_outgoing.push((sel, text));
                        }
                    }
                    KeyCode::Esc => {
                        chat.section = ChatSection::Messages;
                    }
                    _ => {}
                }
            }
        }
    }

    Ok(())
}
