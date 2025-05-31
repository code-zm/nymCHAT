use ratatui::{
    buffer::Buffer,
    layout::{Alignment, Rect},
    style::Style,
    widgets::{Block, Paragraph, Widget},
    text::Text,
};

pub struct InputField<'a> {
    pub value: String,
    pub placeholder: Option<String>,
    pub style: Style,
    pub block: Block<'a>,
}

impl<'a> Widget for InputField<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        let text = if self.value.is_empty() {
            self.placeholder.unwrap_or_default()
        } else {
            self.value.clone()
        };

        let content = Text::from(text);
        let paragraph = Paragraph::new(content)
            .style(self.style)
            .alignment(Alignment::Left)
            .block(self.block);

        paragraph.render(area, buf);
    }
}

