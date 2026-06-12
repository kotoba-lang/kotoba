use kami_devtools::{ElementSnapshot, SceneSnapshot, SemanticRole};
use kami_text::{ColorGlyphAtlas, FontAtlas, build_color_glyph_atlas, layout_color_glyphs, layout_text};
use kami_ui_gpu::{UiLayer, UiRect};
use serde::{Deserialize, Serialize};

pub mod runtime;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct KamiHostConfig {
    pub app_name: String,
    pub width: u32,
    pub height: u32,
    pub runtime_mode: String,
}

impl Default for KamiHostConfig {
    fn default() -> Self {
        Self {
            app_name: "Kotodama KAMI Host".to_string(),
            width: 1280,
            height: 820,
            runtime_mode: "desktop-wasm-kami-ui".to_string(),
        }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct Color(pub [f32; 4]);

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct Rect {
    pub x: f32,
    pub y: f32,
    pub width: f32,
    pub height: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PanelNode {
    pub id: String,
    pub rect: Rect,
    pub fill: Color,
    pub border: Option<Color>,
    pub border_width: f32,
    pub radius: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TextNode {
    pub id: String,
    pub content: String,
    pub x: f32,
    pub y: f32,
    pub size: f32,
    pub color: Color,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MeterNode {
    pub id: String,
    pub rect: Rect,
    pub value: f32,
    pub track: Color,
    pub fill: Color,
    pub radius: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct KamiScene {
    pub panels: Vec<PanelNode>,
    pub text: Vec<TextNode>,
    pub meters: Vec<MeterNode>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum KamiInputEvent {
    PointerMove { x: f32, y: f32 },
    PointerDown { x: f32, y: f32, button: u8 },
    PointerUp { x: f32, y: f32, button: u8 },
    Wheel { delta_x: f32, delta_y: f32 },
    KeyDown { code: String },
    KeyUp { code: String },
    Resize { width: u32, height: u32 },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct KamiFrameModel {
    pub config: KamiHostConfig,
    pub scene: KamiScene,
}

impl KamiFrameModel {
    pub fn current_text_corpus(&self) -> String {
        self.scene
            .text
            .iter()
            .map(|text| text.content.as_str())
            .collect::<Vec<_>>()
            .join("\n")
    }

    pub fn relayout(&mut self) {
        if self.config.app_name == "Disk Cleaner" {
            self.relayout_diskcleaner_sample();
        }
    }

    pub fn to_ui_layer(&self) -> UiLayer {
        let atlas = FontAtlas::from_default_font_stack(18.0, &self.current_text_corpus())
            .unwrap_or_else(|_| FontAtlas::ascii_procedural(18.0));
        let color_atlas = build_color_glyph_atlas(&self.current_text_corpus(), 18.0);
        self.to_ui_layer_with_atlases(&atlas, &color_atlas)
    }

    pub fn to_ui_layer_with_atlas(&self, atlas: &FontAtlas) -> UiLayer {
        let color_atlas = build_color_glyph_atlas(&self.current_text_corpus(), 18.0);
        self.to_ui_layer_with_atlases(atlas, &color_atlas)
    }

    pub fn to_ui_layer_with_atlases(&self, atlas: &FontAtlas, color_atlas: &ColorGlyphAtlas) -> UiLayer {
        let mut layer = UiLayer::new(self.config.width as f32, self.config.height as f32);

        for panel in &self.scene.panels {
            let border = panel.border.unwrap_or(Color([0.0, 0.0, 0.0, 0.0]));
            layer.commands.push(kami_ui_gpu::UiCommand::Rect(UiRect {
                position: [panel.rect.x, panel.rect.y],
                size: [panel.rect.width, panel.rect.height],
                color: panel.fill.0,
                border_color: border.0,
                corner_radius: panel.radius,
                border_width: panel.border_width,
                _pad: [0.0, 0.0],
            }));
        }

        for meter in &self.scene.meters {
            let clamped = meter.value.clamp(0.0, 1.0);
            layer.rounded_rect(
                meter.rect.x,
                meter.rect.y,
                meter.rect.width,
                meter.rect.height,
                meter.track.0,
                meter.radius,
            );
            layer.rounded_rect(
                meter.rect.x,
                meter.rect.y,
                meter.rect.width * clamped,
                meter.rect.height,
                meter.fill.0,
                meter.radius,
            );
        }

        for text in &self.scene.text {
            let scale = (text.size / 18.0).max(0.5);
            let origin = glam::Vec2::new(text.x, text.y);
            let color = glam::Vec4::from_array(text.color.0);
            for glyph in layout_text(&atlas, &text.content, origin, color, scale) {
                layer.text(glyph.position, glyph.size, glyph.uv_rect, glyph.color);
            }
            for glyph in layout_color_glyphs(color_atlas, &text.content, origin, atlas.line_height, scale) {
                layer.color_glyph(glyph.position, glyph.size, glyph.uv_rect);
            }
        }

        layer
    }

    pub fn to_scene_snapshot(&self) -> SceneSnapshot {
        let mut elements = Vec::new();

        for panel in &self.scene.panels {
            let role = if panel.id == "scan-now" {
                SemanticRole::Button
            } else {
                SemanticRole::Panel
            };
            elements.push(ElementSnapshot {
                id: panel.id.clone(),
                role,
                rect: kami_devtools::Rect {
                    x: panel.rect.x,
                    y: panel.rect.y,
                    width: panel.rect.width,
                    height: panel.rect.height,
                },
                visible: true,
                enabled: true,
                text: None,
                tags: vec![panel.id.clone()],
            });
        }

        for text in &self.scene.text {
            elements.push(ElementSnapshot {
                id: text.id.clone(),
                role: SemanticRole::Text,
                rect: kami_devtools::Rect {
                    x: text.x,
                    y: text.y,
                    width: text.content.len() as f32 * text.size * 0.55,
                    height: text.size * 1.2,
                },
                visible: true,
                enabled: false,
                text: Some(text.content.clone()),
                tags: vec![text.id.clone()],
            });
        }

        for meter in &self.scene.meters {
            elements.push(ElementSnapshot {
                id: meter.id.clone(),
                role: SemanticRole::Meter,
                rect: kami_devtools::Rect {
                    x: meter.rect.x,
                    y: meter.rect.y,
                    width: meter.rect.width,
                    height: meter.rect.height,
                },
                visible: true,
                enabled: true,
                text: None,
                tags: vec![meter.id.clone(), "meter".to_string()],
            });
        }

        SceneSnapshot {
            width: self.config.width,
            height: self.config.height,
            elements,
        }
    }

    fn relayout_diskcleaner_sample(&mut self) {
        let width = self.config.width as f32;
        let height = self.config.height as f32;
        let gutter = (width * 0.028).clamp(20.0, 40.0);
        let top_h = (height * 0.268).clamp(190.0, 260.0);
        let summary_w = (width * 0.33).clamp(320.0, 460.0);
        let hero_w = (width - gutter * 3.0 - summary_w).max(320.0);
        let content_y = gutter + top_h + gutter;
        let list_h = (height - content_y - gutter).max(240.0);

        set_panel(
            &mut self.scene.panels,
            "hero",
            Rect {
                x: gutter,
                y: gutter,
                width: hero_w,
                height: top_h,
            },
        );
        set_panel(
            &mut self.scene.panels,
            "summary",
            Rect {
                x: gutter * 2.0 + hero_w,
                y: gutter,
                width: summary_w,
                height: top_h,
            },
        );
        set_panel(
            &mut self.scene.panels,
            "list",
            Rect {
                x: gutter,
                y: content_y,
                width: (width - gutter * 2.0).max(320.0),
                height: list_h,
            },
        );

        let summary = self
            .scene
            .panels
            .iter()
            .find(|p| p.id == "summary")
            .cloned();
        if let Some(summary) = summary {
            let button_w = summary.rect.width * 0.40;
            let button_h = 46.0;
            let button_x = summary.rect.x + summary.rect.width * 0.14;
            let button_y = summary.rect.y + summary.rect.height - 74.0;
            set_panel(
                &mut self.scene.panels,
                "scan-now",
                Rect {
                    x: button_x,
                    y: button_y,
                    width: button_w.clamp(144.0, 200.0),
                    height: button_h,
                },
            );
            set_meter(
                &mut self.scene.meters,
                "reclaimable",
                Rect {
                    x: summary.rect.x + summary.rect.width * 0.09,
                    y: summary.rect.y + summary.rect.height * 0.49,
                    width: (summary.rect.width * 0.72).clamp(220.0, summary.rect.width - 56.0),
                    height: 20.0,
                },
            );
        }

        set_text(
            &mut self.scene.text,
            "title",
            gutter + 36.0,
            gutter + 52.0,
            (width * 0.033).clamp(28.0, 42.0),
        );
        set_text(
            &mut self.scene.text,
            "subtitle",
            gutter + 36.0,
            gutter + 100.0,
            (width * 0.014).clamp(16.0, 20.0),
        );

        if let Some(button) = self.scene.panels.iter().find(|p| p.id == "scan-now") {
            let label_size = (button.rect.height * 0.34).clamp(14.0, 18.0);
            set_text(
                &mut self.scene.text,
                "scan-now-label",
                button.rect.x + button.rect.width * 0.24,
                button.rect.y + button.rect.height * 0.62,
                label_size,
            );
        }
    }
}

pub fn sample_diskcleaner_scene() -> KamiFrameModel {
    let mut frame = KamiFrameModel {
        config: KamiHostConfig {
            app_name: "Disk Cleaner".to_string(),
            ..KamiHostConfig::default()
        },
        scene: KamiScene {
            panels: vec![
                PanelNode {
                    id: "hero".to_string(),
                    rect: Rect {
                        x: 36.0,
                        y: 36.0,
                        width: 760.0,
                        height: 220.0,
                    },
                    fill: Color([0.97, 0.94, 0.88, 1.0]),
                    border: Some(Color([0.40, 0.32, 0.24, 0.18])),
                    border_width: 1.0,
                    radius: 28.0,
                },
                PanelNode {
                    id: "summary".to_string(),
                    rect: Rect {
                        x: 822.0,
                        y: 36.0,
                        width: 422.0,
                        height: 220.0,
                    },
                    fill: Color([0.92, 0.97, 0.95, 1.0]),
                    border: Some(Color([0.06, 0.33, 0.29, 0.15])),
                    border_width: 1.0,
                    radius: 28.0,
                },
                PanelNode {
                    id: "scan-now".to_string(),
                    rect: Rect {
                        x: 884.0,
                        y: 182.0,
                        width: 168.0,
                        height: 46.0,
                    },
                    fill: Color([0.07, 0.44, 0.38, 1.0]),
                    border: Some(Color([0.04, 0.28, 0.24, 0.18])),
                    border_width: 1.0,
                    radius: 23.0,
                },
                PanelNode {
                    id: "list".to_string(),
                    rect: Rect {
                        x: 36.0,
                        y: 282.0,
                        width: 1208.0,
                        height: 480.0,
                    },
                    fill: Color([1.0, 0.98, 0.95, 1.0]),
                    border: Some(Color([0.42, 0.30, 0.20, 0.12])),
                    border_width: 1.0,
                    radius: 28.0,
                },
            ],
            text: vec![
                TextNode {
                    id: "title".to_string(),
                    content: "Disk Cleaner ✨".to_string(),
                    x: 72.0,
                    y: 88.0,
                    size: 42.0,
                    color: Color([0.14, 0.10, 0.08, 1.0]),
                },
                TextNode {
                    id: "subtitle".to_string(),
                    content: "WASM guest + KAMI GPU host 👨‍👩‍👧‍👦".to_string(),
                    x: 72.0,
                    y: 136.0,
                    size: 18.0,
                    color: Color([0.22, 0.34, 0.31, 1.0]),
                },
                TextNode {
                    id: "scan-now-label".to_string(),
                    content: "Scan now".to_string(),
                    x: 926.0,
                    y: 211.0,
                    size: 16.0,
                    color: Color([0.96, 0.98, 0.97, 1.0]),
                },
            ],
            meters: vec![MeterNode {
                id: "reclaimable".to_string(),
                rect: Rect {
                    x: 860.0,
                    y: 144.0,
                    width: 300.0,
                    height: 20.0,
                },
                value: 0.38,
                track: Color([0.82, 0.88, 0.86, 1.0]),
                fill: Color([0.07, 0.44, 0.38, 1.0]),
                radius: 999.0,
            }],
        },
    };
    frame.relayout();
    frame
}

fn set_panel(panels: &mut [PanelNode], id: &str, rect: Rect) {
    if let Some(panel) = panels.iter_mut().find(|p| p.id == id) {
        panel.rect = rect;
    }
}

fn set_text(text_nodes: &mut [TextNode], id: &str, x: f32, y: f32, size: f32) {
    if let Some(text) = text_nodes.iter_mut().find(|t| t.id == id) {
        text.x = x;
        text.y = y;
        text.size = size;
    }
}

fn set_meter(meters: &mut [MeterNode], id: &str, rect: Rect) {
    if let Some(meter) = meters.iter_mut().find(|m| m.id == id) {
        meter.rect = rect;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sample_scene_adapts_to_ui_layer() {
        let frame = sample_diskcleaner_scene();
        let layer = frame.to_ui_layer();
        assert_eq!(layer.screen_width, 1280.0);
        assert_eq!(layer.screen_height, 820.0);
        assert!(layer.commands.len() > frame.scene.panels.len() + frame.scene.meters.len() * 2);
    }

    #[test]
    fn host_config_default_is_desktop_kami_mode() {
        let cfg = KamiHostConfig::default();
        assert_eq!(cfg.runtime_mode, "desktop-wasm-kami-ui");
    }

    #[test]
    fn scene_snapshot_contains_scan_button() {
        let scene = sample_diskcleaner_scene().to_scene_snapshot();
        let scan = scene.find_by_id("scan-now").expect("scan-now");
        assert_eq!(scan.role, SemanticRole::Button);
    }

    #[test]
    fn sample_scene_relayout_keeps_content_within_width() {
        let mut frame = sample_diskcleaner_scene();
        frame.config.width = 960;
        frame.config.height = 700;
        frame.relayout();
        let snapshot = frame.to_scene_snapshot();
        let max_right = snapshot
            .elements
            .iter()
            .map(|e| e.rect.x + e.rect.width)
            .fold(0.0, f32::max);
        assert!(max_right <= snapshot.width as f32 + 0.5);
    }
}
