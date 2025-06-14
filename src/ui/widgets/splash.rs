use ratatui::{
    Frame,
    layout::{Alignment, Constraint, Direction, Layout, Rect},
    style::{Color, Style},
    text::{Line, Text},
    widgets::Paragraph,
};

/// Renders the splash screen with optional dynamic glow and spinner
pub fn render_splash(
    frame: &mut Frame,
    area: Rect,
    splash_text: &str,
    glow_step: usize,
    glow_dynamic: bool,
    show_spinner: bool,
    spinner_idx: usize,
    label: &str,
) {
    // Determine glow intensity
    let glow_intensity = if glow_dynamic {
        32 + ((glow_step * (255 - 32)) / 20) as u8
    } else {
        255
    };

    let glow = Color::Rgb(0, glow_intensity, 0);
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Percentage(66), Constraint::Percentage(34)].as_ref())
        .split(area);

    // Splash text
    frame.render_widget(
        Paragraph::new(Text::raw(splash_text))
            .style(Style::default().fg(glow))
            .alignment(Alignment::Center),
        chunks[0],
    );

    // bottom strip: always render the label; if show_spinner, include the bouncing‑ball above it
    if show_spinner {
        let spin = bouncing_ball(spinner_idx, 12);
        let lines = vec![Line::raw(spin), Line::raw(label)];
        frame.render_widget(
            Paragraph::new(Text::from(lines))
                .style(Style::default().fg(Color::Rgb(0, 255, 0)))
                .alignment(Alignment::Center),
            chunks[1],
        );
    } else {
        // just the label prompt
        frame.render_widget(
            Paragraph::new(label)
                .style(Style::default().fg(Color::Rgb(0, 255, 0)))
                .alignment(Alignment::Center),
            chunks[1],
        );
    }
}

/// Bouncing-ball animation: solid bullet moves within a bracket of given width
pub fn bouncing_ball(idx: usize, width: usize) -> String {
    let cycle = idx % (2 * (width - 1));
    let pos = if cycle < width {
        cycle
    } else {
        2 * (width - 1) - cycle
    };
    let mut s = String::from("[");
    for i in 0..width {
        s.push(if i == pos { '●' } else { ' ' });
    }
    s.push(']');
    s
}
