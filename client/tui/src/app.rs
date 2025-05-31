use crate::core::message_handler::MessageHandler;
use crate::event::handle_key_event;
use crate::log_buffer::LOG_BUFFER;
use crate::model::contact::Contact;
use crate::model::message::Message;
use crate::model::user::User;
use crate::screen::ScreenState;
use crossterm::event::{self, Event as CEvent, KeyCode};
use log::info;
use ratatui::layout::Rect;
use ratatui::{DefaultTerminal, Frame};
use std::io;
use std::sync::Mutex;
use std::fs;
use std::collections::HashMap;
use std::time::Duration;
// tachyonfx imports removed

/// The different UI phases
/// The different UI phases
#[derive(Debug, PartialEq, Eq)]
pub enum Phase {
    Connect,
    Connecting,
    Welcome,
    Chat,
    Search,
}

pub struct App {
    pub running: bool,
    /// Current UI phase
    pub(crate) phase: Phase,
    pub screen: ScreenState,
    pub logged_in_user: Option<User>,
    pub input_buffer: String,
    /// Backend message handler (initialized on connect)
    pub handler: Option<MessageHandler>,
    /// Search mode buffer & result
    search_buffer: String,
    search_result: Option<String>,
    // search loading animation state
    search_loading: bool,
    search_spinner_idx: usize,
    // handle for in-flight search or welcome-login/register task
    search_handle: Option<tokio::task::JoinHandle<HandleResult>>,
    /// Log panel scroll offset (0 = bottom/latest)
    log_scroll: usize,
    /// Outgoing messages queued for sending after local echo
    pub(crate) pending_outgoing: Vec<(usize, String)>,
    /// are we in “welcome” input mode? (login vs register)
    welcome_mode: Option<WelcomeMode>,
    /// which username we’re registering/logging in
    welcome_user: Option<String>,
    /// true once Enter pressed on welcome input, until task finishes
    welcome_loading: bool,
    // Splash animation state
    splash_pages: Vec<String>,      // pre-rendered Figlet outputs
    splash_fonts: Vec<&'static str>,// font names for labels
    splash_idx: usize,              // current font/page index
    splash_step: usize,             // current glow step (0..max)
    splash_rising: bool,            // glow direction
    spinner_idx: usize,             // spinner animation index
    // tachyonfx effect fields removed
}
/// Which welcome action the user picked
#[derive(Debug, Copy, Clone, PartialEq, Eq)]
pub enum WelcomeMode {
    Login,
    Register,
}
/// Unified task result for search or welcome-login/register
enum HandleResult {
    Search(MessageHandler, anyhow::Result<Option<(String, String)>>),
    Welcome(MessageHandler, usize, String, bool),
}

impl App {
    pub fn new() -> Self {
        Self {
            running: true,
            phase: Phase::Connect,
            screen: ScreenState::default(),
            logged_in_user: None,
            input_buffer: String::new(),
            handler: None,
            search_buffer: String::new(),
            search_result: None,
            search_loading: false,
            search_spinner_idx: 0,
            search_handle: None,
            log_scroll: 0,
            pending_outgoing: Vec::new(),
            // welcome-page login/register state
            welcome_mode: None,
            welcome_user: None,
            welcome_loading: false,
            // Splash animation state
            splash_pages: Vec::new(),
            splash_fonts: vec![
                "slant", "roman", "red_phoenix", "rammstein", "poison", "maxiwi", "merlin1",
                "larry 3d", "ghost", "georgi16", "flowerpower", "dos rebel", "dancingfont",
                "cosmike", "bloody", "blocks", "big money-sw", "banner3-d", "amc aaa01", "3d-ascii",
            ],
            splash_idx: 0,
            splash_step: 0,
            splash_rising: true,
            spinner_idx: 0,
            // tachyonfx initialization removed
        }
    }
    /// Pre-render a single random splash page by calling figlet for one randomly chosen font
    pub fn load_splash(&mut self) -> io::Result<()> {
        let font_dir = "/usr/share/figlet";
        // Build lowercase → filename map for .flf files
        let mut map: HashMap<String, String> = HashMap::new();
        for entry in fs::read_dir(font_dir)? {
            let entry = entry?;
            let f = entry.file_name().into_string().unwrap_or_default();
            if f.to_lowercase().ends_with(".flf") {
                let name = f[..f.len() - 4].to_lowercase();
                map.insert(name, f);
            }
        }
        // Select one random font from the list
        let idx = fastrand::usize(..self.splash_fonts.len());
        let font = self.splash_fonts[idx];
        let key = font.to_lowercase();
        // Attempt to render with figlet, fallback on missing
        let page = if let Some(filename) = map.get(&key) {
            let path = format!("{}/{}", font_dir, filename);
            match std::process::Command::new("figlet").args(&["-f", &path, "nymstr"]).output() {
                Ok(o) if o.status.success() => String::from_utf8_lossy(&o.stdout).into_owned(),
                _ => format!("★ missing font: {} ★", font),
            }
        } else {
            format!("★ missing font: {} ★", font)
        };
        // Store only the selected splash page
        self.splash_pages.clear();
        self.splash_pages.push(page);
        // Reset indexes
        self.splash_idx = 0;
        self.splash_step = 0;
        self.splash_rising = true;
        Ok(())
    }

    pub async fn run(&mut self, terminal: &mut DefaultTerminal) -> io::Result<()> {
        // Splash phase (animated)
        let splash_timeout = Duration::from_millis(100);
        const MAX_STEPS: usize = 20;
        loop {
            terminal.draw(|f| self.draw_splash(f))?;
            // on any key, either quit or advance to Connecting
            if event::poll(splash_timeout)? {
                if let CEvent::Key(key) = event::read()? {
                    match key.code {
                        KeyCode::Char('q') | KeyCode::Char('Q') => {
                            // exit the app immediately
                            self.quit();
                            return Ok(());
                        }
                        _ => {
                            // any other key → proceed to connecting
                            self.phase = Phase::Connecting;
                            break;
                        }
                    }
                }
            }
            // update glow and cycle fonts
            if self.splash_rising {
                self.splash_step += 1;
                if self.splash_step >= MAX_STEPS {
                    self.splash_rising = false;
                }
            } else {
                self.splash_step = self.splash_step.saturating_sub(1);
                if self.splash_step == 0 {
                    self.splash_rising = true;
                    self.splash_idx = (self.splash_idx + 1) % self.splash_pages.len();
                }
            }
        }
        // Connecting: spawn mixnet client creation and show spinner until done or timeout
        self.spinner_idx = 0;
        let connect_handle = tokio::spawn(async {
            crate::core::mixnet_client::MixnetService::new("/data/app.db").await
        });
        let start = std::time::Instant::now();
        let timeout = Duration::from_secs(10);
        while !connect_handle.is_finished() {
            terminal.draw(|f| self.draw(f))?;
            // advance spinner and throttle
            std::thread::sleep(Duration::from_millis(100));
            // update spinner index
            self.spinner_idx = self.spinner_idx.wrapping_add(1);
            // update splash glow and cycle fonts
            if self.splash_rising {
                self.splash_step += 1;
                if self.splash_step >= MAX_STEPS {
                    self.splash_rising = false;
                }
            } else {
                self.splash_step = self.splash_step.saturating_sub(1);
                if self.splash_step == 0 {
                    self.splash_rising = true;
                    self.splash_idx = (self.splash_idx + 1) % self.splash_pages.len();
                }
            }
            if start.elapsed() >= timeout {
                // timed out: cancel attempt
                connect_handle.abort();
                break;
            }
        }
        // Retrieve connection result if any
        if let Ok(Ok((svc, rx))) = connect_handle.await {
            if let Ok(handler) = MessageHandler::new(svc, rx, "/data/app.db").await {
                self.handler = Some(handler);
            }
        }
        // Move to welcome screen
        self.phase = Phase::Welcome;
        // Main event loop
        while self.running {
            // —————— Poll outstanding search or welcome task ——————
            if let Some(handle) = &mut self.search_handle {
                if handle.is_finished() {
                    if let Ok(result) = handle.await {
                        match result {
                            HandleResult::Welcome(handler, mode_idx, user, success) => {
                                self.handler = Some(handler);
                                self.welcome_loading = false;
                                if success && mode_idx == WelcomeMode::Login as usize {
                                    // login succeeded → enter chat
                                    self.logged_in_user = Some(User {
                                        id: user.clone(),
                                        username: user.clone(),
                                        display_name: user.clone(),
                                        online: true,
                                    });
                                    self.input_buffer.clear();
                                    self.phase = Phase::Chat;
                                } else {
                                    // back to login/register choice
                                    self.welcome_mode = None;
                                }
                            }
                            HandleResult::Search(handler, res) => {
                                self.handler = Some(handler);
                                self.search_loading = false;
                                match res {
                                    Ok(opt) => {
                                        self.search_result = opt.map(|(u, _)| u)
                                                           .or(Some("<not found>".into()));
                                    }
                                    Err(_) => {
                                        self.search_result = Some("<not found>".into());
                                    }
                                }
                            }
                        }
                    }
                    self.search_handle = None;
                } else {
                    // animate loader
                    self.search_spinner_idx = self.search_spinner_idx.wrapping_add(1);
                }
            }
            // ——— auto‑drain incoming messages in Chat phase ———
            if self.phase == Phase::Chat {
                if let Some(handler) = &mut self.handler {
                    let incoming = handler.drain_incoming().await;
                    for (from, text) in incoming {
                        if let Some(chat) = self.screen.as_chat_mut() {
                            let idx = match chat.contacts.iter().position(|c| c.id == from) {
                                Some(i) => i,
                                None => {
                                    chat.contacts.push(Contact::new(&from));
                                    chat.messages.push(Vec::new());
                                    chat.contacts.len() - 1
                                }
                            };
                            chat.messages[idx].push(Message::new(&from, &text));
                        }
                    }
                }
            }
            // advance the loader spinner on Welcome→loading each frame
            if self.phase == Phase::Welcome && self.welcome_loading {
                self.spinner_idx = self.spinner_idx.wrapping_add(1);
            }
            // draw UI normally
            terminal.draw(|f| self.draw(f))?;
            // small delay to reduce CPU
            std::thread::sleep(Duration::from_millis(50));
            if event::poll(Duration::from_millis(100))? {
                if let CEvent::Key(key) = event::read()? {
                    // scroll log panel for non-chat phases
                    if self.phase != Phase::Chat {
                        match key.code {
                            KeyCode::Up => {
                                self.log_scroll = self.log_scroll.saturating_add(1);
                                continue;
                            }
                            KeyCode::Down => {
                                self.log_scroll = self.log_scroll.saturating_sub(1);
                                continue;
                            }
                            _ => {}
                        }
                    }
                    match self.phase {
                        Phase::Welcome => match key.code {
                            // menu commands only when not in input mode
                            KeyCode::Char('l') | KeyCode::Char('L') if self.welcome_mode.is_none() && !self.welcome_loading => {
                                self.input_buffer.clear();
                                self.welcome_mode = Some(WelcomeMode::Login);
                            }
                            KeyCode::Char('r') | KeyCode::Char('R') if self.welcome_mode.is_none() && !self.welcome_loading => {
                                self.input_buffer.clear();
                                self.welcome_mode = Some(WelcomeMode::Register);
                            }
                            // when typing username
                            KeyCode::Char(c) if self.welcome_mode.is_some() && !self.welcome_loading => {
                                self.input_buffer.push(c);
                            }
                            KeyCode::Backspace if self.welcome_mode.is_some() && !self.welcome_loading => {
                                self.input_buffer.pop();
                            }
                            // start async login/register
                            KeyCode::Enter if self.welcome_mode.is_some() && !self.welcome_loading => {
                                // start welcome loading; keep welcome_mode until task completes
                                self.welcome_loading = true;
                                let mode = self.welcome_mode.unwrap();
                                let user = std::mem::take(&mut self.input_buffer);
                                self.welcome_user = Some(user.clone());
                                if let Ok(mut logs) = LOG_BUFFER.lock() { logs.clear(); }
                                let mut handler = self.handler.take().unwrap();
                                let h = match mode {
                                    WelcomeMode::Register => {
                                        info!("Registering {}", user);
                                        tokio::spawn(async move {
                                            let success = handler.register_user(&user).await.unwrap_or(false);
                                            HandleResult::Welcome(handler, mode as usize, user, success)
                                        })
                                    }
                                    WelcomeMode::Login => {
                                        info!("Logging in {}", user);
                                        tokio::spawn(async move {
                                            let success = handler.login_user(&user).await.unwrap_or(false);
                                            HandleResult::Welcome(handler, mode as usize, user, success)
                                        })
                                    }
                                };
                                self.search_handle = Some(h);
                            }
                            KeyCode::Char('q') if self.welcome_mode.is_none() && !self.welcome_loading => self.quit(),
                            _ => {}
                        },
                        Phase::Chat => {
                            // 1) Drain incoming messages
                            if let Some(handler) = &mut self.handler {
                                let incoming = handler.drain_incoming().await;
                                for (from, text) in incoming {
                                    if let Some(chat) = self.screen.as_chat_mut() {
                                        let idx =
                                            match chat.contacts.iter().position(|c| c.id == from) {
                                                Some(i) => i,
                                                None => {
                                                    chat.contacts.push(Contact::new(&from));
                                                    chat.messages.push(Vec::new());
                                                    chat.contacts.len() - 1
                                                }
                                            };
                                        chat.messages[idx].push(Message::new(&from, &text));
                                    }
                                }
                            }

                            // 2) Dispatch key to unified handler
                            handle_key_event(self, key)?;

                            // 3) Send queued outgoing messages via backend
                            if let Some(handler) = &mut self.handler {
                                let pending = std::mem::take(&mut self.pending_outgoing);
                                for (sel, msg) in pending {
                                    if let Some(chat) = self.screen.as_chat_mut() {
                                        if sel < chat.contacts.len() {
                                            let to = chat.contacts[sel].id.clone();
                                            if let Err(e) =
                                                handler.send_direct_message(&to, &msg).await
                                            {
                                                chat.messages[sel].push(Message::new(
                                                    "error",
                                                    &format!("send failed: {}", e),
                                                ));
                                                chat.chat_scroll =
                                                    chat.messages[sel].len().saturating_sub(1);
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        Phase::Search => {
                            match key.code {
                                // --- MENU COMMANDS (only when a result is present) ---
                                KeyCode::Char('1')
                                    if self.search_result.as_deref().map(|r| r != "<not found>").unwrap_or(false) =>
                                {
                                    // Start chat
                                    if let Some(username) = &self.search_result {
                                        let chat = self.screen.as_chat_mut().unwrap();
                                        chat.contacts.push(Contact::new(username));
                                        chat.messages.push(Vec::new());
                                        chat.highlighted_contact = chat.contacts.len() - 1;
                                        chat.contacts_state.select(Some(chat.highlighted_contact));
                                    }
                                    // Clear search state and exit
                                    self.search_buffer.clear();
                                    self.search_result = None;
                                    self.search_loading = false;
                                    self.search_handle = None;
                                    self.phase = Phase::Chat;
                                }
                                KeyCode::Char('2') if self.search_result.is_some() => {
                                    // Search again: clear only search state
                                    self.search_buffer.clear();
                                    self.search_result = None;
                                    self.search_loading = false;
                                    self.search_handle = None;
                                }
                                KeyCode::Char('3') | KeyCode::Esc
                                    if self.search_result.is_some() =>
                                {
                                    // Back to chat: clear state and exit
                                    self.search_buffer.clear();
                                    self.search_result = None;
                                    self.search_loading = false;
                                    self.search_handle = None;
                                    self.phase = Phase::Chat;
                                }

                                // --- REGULAR TYPING (only when no result & not loading) ---
                                KeyCode::Char(c)
                                    if !self.search_loading && self.search_result.is_none() =>
                                {
                                    self.search_buffer.push(c);
                                }
                                KeyCode::Backspace
                                    if !self.search_loading && self.search_result.is_none() =>
                                {
                                    self.search_buffer.pop();
                                }

                                // --- START SEARCH (only when no result & not loading) ---
                                KeyCode::Enter if !self.search_loading && self.search_result.is_none() => {
                                    if let Some(mut handler) = self.handler.take() {
                                        let q = self.search_buffer.clone();
                                        let h = tokio::spawn(async move {
                                            let res = handler.query_user(&q).await;
                                            HandleResult::Search(handler, res)
                                        });
                                        self.search_handle = Some(h);
                                        self.search_loading = true;
                                        self.search_spinner_idx = 0;
                                    }
                                }

                                // Ignore all other keys in Search
                                _ => {}
                            }
                        },
                        _ => {}
                    }
                }
            }
        }
        Ok(())
    }

    pub fn draw(&mut self, frame: &mut Frame) {
        use ratatui::layout::{Constraint, Direction, Layout, Rect};
        use ratatui::widgets::Clear;
        // during connecting, show splash with spinner bar
        if self.phase == Phase::Connecting {
            frame.render_widget(Clear, frame.area());
            self.draw_splash(frame);
            return;
        }
        // clear entire frame
        frame.render_widget(Clear, frame.area());
        // reserve top for log panel (4 rows: border + 2 lines + border) and rest for content
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Length(4), Constraint::Min(0)].as_ref())
            .split(frame.area());
        // combined log panel
        self.render_log_box(frame, chunks[0], "Logs", &LOG_BUFFER);
        // content area below logs
        let content_area: Rect = chunks[1];
        use Phase::*;
        match self.phase {
            Connect    => self.draw_connect(frame, content_area),
            Connecting => self.draw_connecting(frame, content_area),
            Welcome    => self.draw_welcome(frame, content_area),
            Chat       => crate::ui::render_ui(self, frame, content_area),
            Search     => self.draw_search(frame, content_area),
        }
    }

    pub fn quit(&mut self) {
        self.running = false;
    }
    // --- UI phase drawing helpers ---
    fn draw_connect(&self, frame: &mut Frame, area: Rect) {
        use ratatui::{
            layout::Alignment,
            widgets::{Block, Borders, Paragraph},
        };
        let p = Paragraph::new("press any button to connect to mixnet, q to quit")
            .block(Block::default().borders(Borders::NONE))
            .alignment(Alignment::Center);
        frame.render_widget(p, area);
    }
    fn draw_connecting(&self, frame: &mut Frame, area: Rect) {
        use crate::log_buffer::LOG_BUFFER;
        use ratatui::{
            text::{Line, Text},
            widgets::{Block, Borders, Clear, Paragraph, Wrap},
        };
        frame.render_widget(Clear, area);
        let block = Block::default().borders(Borders::ALL).title("Mixnet Logs");
        let inner = block.inner(area);
        frame.render_widget(block, area);
        let logs = LOG_BUFFER.lock().unwrap();
        let lines: Vec<Line> = logs.iter().map(|l| Line::from(l.as_str())).collect();
        let paragraph = Paragraph::new(Text::from(lines)).wrap(Wrap { trim: false });
        frame.render_widget(paragraph, inner);
    }

    fn draw_splash(&self, frame: &mut Frame) {
        use crate::ui::widgets::splash;

        let splash_text = &self.splash_pages[self.splash_idx];
        // only spin once the user has pressed a key (i.e. in Connecting phase)
        let show_spinner = self.phase == Phase::Connecting;
        let label = match self.phase {
            // include the quit hint on initial splash
            Phase::Connect => "press any button to connect to mixnet, q to quit",
            Phase::Connecting => "Connecting to Mixnet",
            _ => "",
        };

        splash::render_splash(
            frame,
            frame.area(),
            splash_text,
            self.splash_step,
            true,          // still glow dynamically
            show_spinner,  // only bounce once Connecting
            self.spinner_idx,
            label,
        );
    }


    // Bouncing-ball logic moved to ui/widgets/splash.rs
    fn draw_welcome(&self, frame: &mut Frame, area: Rect) {
        use crate::ui::widgets::splash;
        use ratatui::{
            layout::{Alignment, Constraint, Direction, Layout},
            widgets::{Block, Borders, Paragraph},
            style::{Style, Color},
        };

        // full welcome box with green border
        let block = Block::default()
            .title("Welcome")
            .borders(Borders::ALL)
            .style(Style::default().fg(Color::Rgb(0, 255, 0)));

        let inner = block.inner(area);
        frame.render_widget(block, area);

        // split 2/3 splash logo, 1/3 controls
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Ratio(2,3), Constraint::Ratio(1,3)].as_ref())
            .split(inner);

        // always show static bright splash in upper 2/3
        splash::render_splash(
            frame, chunks[0],
            &self.splash_pages[self.splash_idx],
            20,     // full brightness
            false,  // no dynamic glow
            false,  // no spinner on the logo
            self.spinner_idx,
            "",
        );

        // lower area: either options, input, or loader
        if let Some(mode) = self.welcome_mode {
            if self.welcome_loading {
                // show only spinner + label (no duplicated logo)
                use ratatui::{
                    layout::{Constraint, Direction, Layout},
                    widgets::Paragraph,
                    style::{Style, Color},
                    layout::Alignment,
                };
                // split the lower third into spinner row and label row
                let parts = Layout::default()
                    .direction(Direction::Vertical)
                    .constraints([
                        Constraint::Length(1),
                        Constraint::Length(1),
                        Constraint::Min(0)
                    ].as_ref())
                    .split(chunks[1]);
                // bouncing ball spinner (fixed width for visible bounce)
                let spin = splash::bouncing_ball(self.spinner_idx, 12);
                let p_spin = Paragraph::new(spin)
                    .style(Style::default().fg(Color::Rgb(0,255,0)))
                    .alignment(Alignment::Center);
                frame.render_widget(p_spin, parts[0]);
                // label beneath
                let uname = self.welcome_user.as_deref().unwrap_or("");
                let label = match mode {
                    WelcomeMode::Register => format!("Registering {}", uname),
                    WelcomeMode::Login    => format!("Logging in as {}", uname),
                };
                let p_label = Paragraph::new(label)
                    .style(Style::default().fg(Color::Rgb(0,255,0)))
                    .alignment(Alignment::Center);
                frame.render_widget(p_label, parts[1]);
            } else {
                // one-line input box centered at half the width
                use ratatui::{
                    layout::{Constraint, Direction, Layout},
                    widgets::Paragraph,
                    layout::Alignment,
                };
                // vertical carve
                let input_vert = Layout::default()
                    .direction(Direction::Vertical)
                    .constraints([
                        Constraint::Length(3),
                        Constraint::Min(0)
                    ].as_ref())
                    .split(chunks[1])[0];
                // horizontal carve into 25/50/25% to center half-width
                let input_horiz = Layout::default()
                    .direction(Direction::Horizontal)
                    .constraints([
                        Constraint::Percentage(25),
                        Constraint::Percentage(50),
                        Constraint::Percentage(25)
                    ].as_ref())
                    .split(input_vert)[1];
                let title = match mode {
                    WelcomeMode::Register => "Register: enter username and press Enter",
                    WelcomeMode::Login    => "Login: enter username and press Enter",
                };
                let p = Paragraph::new(self.input_buffer.as_str())
                    .block(Block::default().borders(Borders::ALL).title(title))
                    .alignment(Alignment::Left);
                frame.render_widget(p, input_horiz);
            }
        } else {
            // initial options
            let opts = "[L] Login    [R] Register    [Q] Quit";
            let p = Paragraph::new(opts)
                .style(Style::default().fg(Color::Rgb(0, 255, 0)))
                .alignment(Alignment::Center);
            frame.render_widget(p, chunks[1]);
        }
    }
    fn draw_search(&self, frame: &mut Frame, area: Rect) {
        use ratatui::{
            layout::{Alignment, Constraint, Direction, Layout},
            style::{Style, Color},
            widgets::{Block, Borders, Paragraph},
        };
        let title = "Search User: type username and press Enter, Esc to cancel";
        let block = Block::default().title(title).borders(Borders::ALL);
        let inner = block.inner(area);
        frame.render_widget(block, area);
        // Split into 3 rows: input, result, options
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints(
                [
                    Constraint::Length(3),
                    Constraint::Length(3),
                    Constraint::Length(1),
                ]
                .as_ref(),
            )
            .split(inner);

        // 1) Username input
        let input = Paragraph::new(self.search_buffer.as_str())
            .block(Block::default().borders(Borders::ALL).title("Username"))
            .alignment(Alignment::Left);
        frame.render_widget(input, chunks[0]);

        // 2) Loading spinner or Result
        if self.search_loading {
            // bouncing ball animation
            let spin = crate::ui::widgets::splash::bouncing_ball(self.search_spinner_idx, 12);
            let p = Paragraph::new(spin)
                .style(Style::default().fg(Color::Rgb(0, 255, 0)))
                .alignment(Alignment::Left);
            frame.render_widget(p, chunks[1]);
        } else if let Some(res) = &self.search_result {
            let result = Paragraph::new(res.as_str())
                .block(Block::default().borders(Borders::ALL).title("Result"))
                .alignment(Alignment::Left);
            frame.render_widget(result, chunks[1]);
        }

        // 3) Options, only if we got a real user back and not loading
        if !self.search_loading {
            if let Some(res) = &self.search_result {
                if res != "<not found>" {
                    let opts = "[1] Start Chat    [2] Search Again    [3] Home";
                    let menu = Paragraph::new(opts).alignment(Alignment::Center);
                    frame.render_widget(menu, chunks[2]);
                }
            }
        }
    }

    /// Render a log buffer in a small box of the last 2 lines at given area
    fn render_log_box(
        &self,
        frame: &mut Frame,
        area: Rect,
        title: &str,
        buffer: &Mutex<Vec<String>>,
    ) {
        use ratatui::{
            text::{Line, Text},
            widgets::{Block, Borders, Clear, Paragraph, Wrap},
        };
        // clear log area
        frame.render_widget(Clear, area);
        // border and title
        let block = Block::default().borders(Borders::ALL).title(title);
        let inner = block.inner(area);
        frame.render_widget(block, area);
        // collect last N log lines based on inner area height and scroll offset
        let logs = buffer.lock().unwrap();
        let total = logs.len();
        let height = inner.height as usize;
        // scroll offset must not exceed available logs
        let scroll = self.log_scroll.min(total.saturating_sub(1));
        let end = total.saturating_sub(scroll);
        let start = end.saturating_sub(height);
        let slice = logs.get(start..end).unwrap_or(&[]);
        let lines: Vec<Line> = slice.iter().map(|l| Line::from(l.as_str())).collect();
        let paragraph = Paragraph::new(Text::from(lines)).wrap(Wrap { trim: false });
        frame.render_widget(paragraph, inner);
    }

}
