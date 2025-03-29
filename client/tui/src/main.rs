mod app;
mod event;
mod model;
mod screen;
mod ui;

use crate::app::App;
use color_eyre::Result;

#[tokio::main]
async fn main() -> Result<()> {
    color_eyre::install()?;
    let mut terminal = ratatui::init();
    let mut app = App::new();
    app.run(&mut terminal).await?;
    ratatui::restore();
    Ok(())
}

