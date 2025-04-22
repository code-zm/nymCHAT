mod app;
mod core;
mod event;
mod model;
mod screen;
mod ui;

use crate::app::App;
use color_eyre::Result;
// Custom logger to capture log output in TUI
mod log_buffer;
use chrono::Utc;
use dotenvy::dotenv;
use env_logger::Builder;
use log::LevelFilter;
use log_buffer::LOG_BUFFER;

#[tokio::main]
async fn main() -> Result<()> {
    color_eyre::install()?;
    // load environment variables from .env file, if present
    dotenv().ok();
    // initialize logging with in-app buffer and stderr
    Builder::from_default_env()
        .format(move |_buf, record| {
            // Format log message and capture in TUI log buffer, suppress stderr
            let ts = Utc::now().format("%Y-%m-%dT%H:%M:%SZ");
            let s = format!(
                "[{}] {} [{}] {}",
                ts,
                record.level(),
                record.target(),
                record.args()
            );
            if let Ok(mut v) = LOG_BUFFER.lock() {
                v.push(s.clone());
                if v.len() > 1000 {
                    v.remove(0);
                }
            }
            Ok(())
        })
        .filter(None, LevelFilter::Info)
        .init();
    let mut terminal = ratatui::init();
    let mut app = App::new();
    // Load splash pages before entering main UI loop
    app.load_splash()?;
    app.run(&mut terminal).await?;
    ratatui::restore();
    Ok(())
}
