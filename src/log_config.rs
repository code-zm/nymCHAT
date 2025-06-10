use chrono::Local;
use fern::Dispatch;
use log::LevelFilter;
use std::io;

/// Initialize logging to file and stdout with timestamps.
pub fn init_logging(log_file: &str) -> anyhow::Result<()> {
    Dispatch::new()
        .format(move |out, message, record| {
            out.finish(format_args!(
                "{} - {} - {} - {}",
                Local::now().to_rfc3339(),
                record.level(),
                record.target(),
                message
            ))
        })
        .level(LevelFilter::Info)
        .chain(fern::log_file(log_file)?)
        .chain(io::stdout())
        .apply()?;
    Ok(())
}
