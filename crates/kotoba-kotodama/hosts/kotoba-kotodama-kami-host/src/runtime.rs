use crate::{KamiFrameModel, sample_diskcleaner_scene};
use anyhow::{Context, Result};
use bytemuck::{Pod, Zeroable};
use kami_devtools::SemanticRole;
use kami_devtools::{
    AutomationPlan, AutomationStep, AutomationTranscript, RenderCapabilities, SceneSnapshot,
    ScreenshotArtifact, ScreenshotFormat, UiUxReport, click_events_for_target, evaluate_uiux,
    keypress_events, resolve_target,
};
use kami_input::InputEvent;
use kami_text::{DynamicColorGlyphAtlas, DynamicGlyphAtlas};
use kami_ui_gpu::{UiColorGlyph, UiRect, UiText};
use std::collections::VecDeque;
use std::fs::File;
use std::io::Cursor;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use wgpu::util::DeviceExt;
use winit::{
    dpi::PhysicalSize,
    event::{ElementState, Event, KeyEvent, WindowEvent},
    event_loop::EventLoop,
    keyboard::{Key, NamedKey},
    window::WindowBuilder,
};

const RECT_SHADER: &str = r#"
struct ScreenUniform {
  size: vec2<f32>,
  _pad: vec2<f32>,
};

@group(0) @binding(0)
var<uniform> screen: ScreenUniform;

struct VertexIn {
  @location(0) pos: vec2<f32>,
  @location(1) rect_pos: vec2<f32>,
  @location(2) rect_size: vec2<f32>,
  @location(3) color: vec4<f32>,
};

struct VertexOut {
  @builtin(position) position: vec4<f32>,
  @location(0) color: vec4<f32>,
};

@vertex
fn vs_main(input: VertexIn) -> VertexOut {
  let pixel = input.rect_pos + input.pos * input.rect_size;
  let ndc = vec2<f32>(
    (pixel.x / screen.size.x) * 2.0 - 1.0,
    1.0 - (pixel.y / screen.size.y) * 2.0
  );

  var out: VertexOut;
  out.position = vec4<f32>(ndc, 0.0, 1.0);
  out.color = input.color;
  return out;
}

@fragment
fn fs_main(input: VertexOut) -> @location(0) vec4<f32> {
  return input.color;
}
"#;

const TEXT_SHADER: &str = r#"
struct ScreenUniform {
  size: vec2<f32>,
  _pad: vec2<f32>,
};

@group(0) @binding(0)
var<uniform> screen: ScreenUniform;
@group(1) @binding(0)
var text_atlas: texture_2d<f32>;
@group(1) @binding(1)
var text_sampler: sampler;

struct VertexIn {
  @location(0) pos: vec2<f32>,
  @location(1) glyph_pos: vec2<f32>,
  @location(2) glyph_size: vec2<f32>,
  @location(3) uv_rect: vec4<f32>,
  @location(4) color: vec4<f32>,
};

struct VertexOut {
  @builtin(position) position: vec4<f32>,
  @location(0) uv: vec2<f32>,
  @location(1) color: vec4<f32>,
};

@vertex
fn vs_main(input: VertexIn) -> VertexOut {
  let pixel = input.glyph_pos + input.pos * input.glyph_size;
  let ndc = vec2<f32>(
    (pixel.x / screen.size.x) * 2.0 - 1.0,
    1.0 - (pixel.y / screen.size.y) * 2.0
  );
  var out: VertexOut;
  out.position = vec4<f32>(ndc, 0.0, 1.0);
  out.uv = input.uv_rect.xy + input.pos * input.uv_rect.zw;
  out.color = input.color;
  return out;
}

@fragment
fn fs_main(input: VertexOut) -> @location(0) vec4<f32> {
  let alpha = textureSample(text_atlas, text_sampler, input.uv).r;
  return vec4<f32>(input.color.rgb, input.color.a * alpha);
}
"#;

const COLOR_GLYPH_SHADER: &str = r#"
struct ScreenUniform {
  size: vec2<f32>,
  _pad: vec2<f32>,
};

@group(0) @binding(0)
var<uniform> screen: ScreenUniform;
@group(1) @binding(0)
var glyph_atlas: texture_2d<f32>;
@group(1) @binding(1)
var glyph_sampler: sampler;

struct VertexIn {
  @location(0) pos: vec2<f32>,
  @location(1) glyph_pos: vec2<f32>,
  @location(2) glyph_size: vec2<f32>,
  @location(3) uv_rect: vec4<f32>,
};

struct VertexOut {
  @builtin(position) position: vec4<f32>,
  @location(0) uv: vec2<f32>,
};

@vertex
fn vs_main(input: VertexIn) -> VertexOut {
  let pixel = input.glyph_pos + input.pos * input.glyph_size;
  let ndc = vec2<f32>(
    (pixel.x / screen.size.x) * 2.0 - 1.0,
    1.0 - (pixel.y / screen.size.y) * 2.0
  );
  var out: VertexOut;
  out.position = vec4<f32>(ndc, 0.0, 1.0);
  out.uv = input.uv_rect.xy + input.pos * input.uv_rect.zw;
  return out;
}

@fragment
fn fs_main(input: VertexOut) -> @location(0) vec4<f32> {
  return textureSample(glyph_atlas, glyph_sampler, input.uv);
}
"#;

#[repr(C)]
#[derive(Debug, Clone, Copy, Pod, Zeroable)]
struct QuadVertex {
    pos: [f32; 2],
}

#[repr(C)]
#[derive(Debug, Clone, Copy, Pod, Zeroable)]
struct ScreenUniform {
    size: [f32; 2],
    _pad: [f32; 2],
}

pub fn run_sample_window() -> Result<()> {
    let event_loop = EventLoop::new()?;
    let frame = sample_diskcleaner_scene();
    let window = Arc::new(
        WindowBuilder::new()
            .with_title(format!("{} — KAMI Host", frame.config.app_name))
            .with_inner_size(PhysicalSize::new(frame.config.width, frame.config.height))
            .build(&event_loop)
            .context("build window")?,
    );

    let mut state = pollster::block_on(RenderState::new(window.clone(), frame))?;
    event_loop.run(move |event, elwt| match event {
        Event::WindowEvent { event, window_id } if window_id == window.id() => match event {
            WindowEvent::CloseRequested => elwt.exit(),
            WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        logical_key: Key::Named(NamedKey::Escape),
                        state: ElementState::Pressed,
                        ..
                    },
                ..
            } => elwt.exit(),
            WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        logical_key: Key::Named(NamedKey::Tab),
                        state: ElementState::Pressed,
                        ..
                    },
                ..
            } => state.inject_input_events(keypress_events("Tab")),
            WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        logical_key: Key::Named(NamedKey::Enter),
                        state: ElementState::Pressed,
                        ..
                    },
                ..
            } => state.inject_input_events(keypress_events("Enter")),
            WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        logical_key: Key::Named(NamedKey::Space),
                        state: ElementState::Pressed,
                        ..
                    },
                ..
            } => state.inject_input_events(keypress_events("Space")),
            WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        logical_key: Key::Character(ch),
                        state: ElementState::Pressed,
                        ..
                    },
                ..
            } if ch.eq_ignore_ascii_case("p") => {
                if let Ok(path) = default_screenshot_path("kami-host") {
                    match state.capture_screenshot_png(&path) {
                        Ok(artifact) => {
                            eprintln!("kotodama-kami-host screenshot: {}", artifact.path)
                        }
                        Err(err) => eprintln!("kotodama-kami-host screenshot error: {err:#}"),
                    }
                }
            }
            WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        logical_key: Key::Character(ch),
                        state: ElementState::Pressed,
                        ..
                    },
                ..
            } if ch.eq_ignore_ascii_case("s") => {
                let snapshot = state.current_scene_snapshot();
                if let Some(events) = click_events_for_target(
                    &snapshot,
                    &kami_devtools::TargetRef::ElementId("scan-now".to_string()),
                ) {
                    state.inject_input_events(events);
                }
            }
            WindowEvent::CursorMoved { position, .. } => {
                state.inject_input_events([InputEvent::PointerMove {
                    x: position.x as f32,
                    y: position.y as f32,
                    dx: 0.0,
                    dy: 0.0,
                    device: kami_input::Device::Mouse,
                    stylus: None,
                }])
            }
            WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        logical_key: Key::Character(ch),
                        state: ElementState::Pressed,
                        ..
                    },
                ..
            } if ch.eq_ignore_ascii_case("a") => match default_artifact_dir("kami-plan") {
                Ok(dir) => match state
                    .run_automation_plan(&kami_devtools::sample_diskcleaner_plan(), &dir)
                {
                    Ok(transcript) => match write_transcript_json(&transcript, &dir) {
                        Ok(path) => {
                            eprintln!(
                                "kotodama-kami-host automation transcript: {}",
                                path.display()
                            )
                        }
                        Err(err) => {
                            eprintln!("kotodama-kami-host transcript write error: {err:#}")
                        }
                    },
                    Err(err) => eprintln!("kotodama-kami-host automation error: {err:#}"),
                },
                Err(err) => eprintln!("kotodama-kami-host artifact dir error: {err:#}"),
            },
            WindowEvent::MouseInput {
                state: ElementState::Pressed,
                ..
            } => {
                if let Some((x, y)) = state.pointer_pos {
                    state.inject_input_events([InputEvent::PointerDown {
                        x,
                        y,
                        button: 0,
                        device: kami_input::Device::Mouse,
                        stylus: None,
                    }]);
                }
            }
            WindowEvent::MouseInput {
                state: ElementState::Released,
                ..
            } => {
                if let Some((x, y)) = state.pointer_pos {
                    state.inject_input_events([InputEvent::PointerUp {
                        x,
                        y,
                        button: 0,
                        device: kami_input::Device::Mouse,
                        stylus: None,
                    }]);
                }
            }
            WindowEvent::Resized(size) => state.resize(size),
            WindowEvent::RedrawRequested => {
                if let Err(err) = state.render() {
                    eprintln!("kotodama-kami-host render error: {err:#}");
                    elwt.exit();
                }
            }
            _ => {}
        },
        Event::AboutToWait => window.request_redraw(),
        _ => {}
    })?;
    Ok(())
}

pub fn run_sample_headless(artifact_dir: &Path) -> Result<PathBuf> {
    let frame = sample_diskcleaner_scene();
    let mut state = pollster::block_on(RenderState::new_headless(frame))?;
    let transcript =
        state.run_automation_plan(&kami_devtools::sample_diskcleaner_plan(), artifact_dir)?;
    let transcript_path = write_transcript_json(&transcript, artifact_dir)?;
    let report_path = write_uiux_report_json(&state.evaluate_uiux(), artifact_dir)?;
    eprintln!(
        "kotodama-kami-host headless uiux report: {}",
        report_path.display()
    );
    Ok(transcript_path)
}

const GOLDEN_SCREENSHOTS: &[&str] = &["01-boot.png", "03-after-click.png"];

pub fn update_sample_headless_golden(golden_dir: &Path, artifact_dir: &Path) -> Result<()> {
    let _ = run_sample_headless(artifact_dir)?;
    std::fs::create_dir_all(golden_dir)
        .with_context(|| format!("create golden dir {}", golden_dir.display()))?;
    for name in GOLDEN_SCREENSHOTS {
        let src = artifact_dir.join(name);
        let dst = golden_dir.join(name);
        std::fs::copy(&src, &dst)
            .with_context(|| format!("copy golden {} -> {}", src.display(), dst.display()))?;
    }
    let report_src = artifact_dir.join("uiux-report.json");
    let report_dst = golden_dir.join("uiux-report.json");
    std::fs::copy(&report_src, &report_dst).with_context(|| {
        format!(
            "copy golden report {} -> {}",
            report_src.display(),
            report_dst.display()
        )
    })?;
    Ok(())
}

pub fn verify_sample_headless_golden(
    golden_dir: &Path,
    artifact_dir: &Path,
    min_uiux_score: u8,
) -> Result<()> {
    let _ = run_sample_headless(artifact_dir)?;
    for name in GOLDEN_SCREENSHOTS {
        let actual = artifact_dir.join(name);
        let golden = golden_dir.join(name);
        let diff = artifact_dir.join(format!("{name}.diff.png"));
        compare_png_against_golden(&golden, &actual, &diff)
            .with_context(|| format!("verify golden {}", name))?;
    }
    let report_path = artifact_dir.join("uiux-report.json");
    let report = read_uiux_report_json(&report_path)?;
    enforce_uiux_threshold(&report, min_uiux_score, &report_path)?;
    Ok(())
}

pub struct RenderState {
    surface: Option<wgpu::Surface<'static>>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    pipeline: wgpu::RenderPipeline,
    text_pipeline: wgpu::RenderPipeline,
    color_glyph_pipeline: wgpu::RenderPipeline,
    vertex_buffer: wgpu::Buffer,
    vertex_count: u32,
    instance_buffer: wgpu::Buffer,
    instance_count: u32,
    text_instance_buffer: wgpu::Buffer,
    text_instance_count: u32,
    color_glyph_instance_buffer: wgpu::Buffer,
    color_glyph_instance_count: u32,
    uniform_buffer: wgpu::Buffer,
    bind_group: wgpu::BindGroup,
    text_bind_group_layout: wgpu::BindGroupLayout,
    text_bind_group: wgpu::BindGroup,
    text_sampler: wgpu::Sampler,
    text_atlas_texture: wgpu::Texture,
    text_atlas: DynamicGlyphAtlas,
    color_glyph_bind_group: wgpu::BindGroup,
    color_glyph_sampler: wgpu::Sampler,
    color_glyph_texture: wgpu::Texture,
    color_glyph_atlas: DynamicColorGlyphAtlas,
    clear_color: wgpu::Color,
    /// Scene frame model — public for external scene updates (e.g. live mDNS peer list).
    pub frame: KamiFrameModel,
    pending_inputs: VecDeque<InputEvent>,
    focused_element: Option<String>,
    hovered_element: Option<String>,
    pointer_pos: Option<(f32, f32)>,
}

impl RenderState {
    pub async fn new(window: Arc<winit::window::Window>, frame: KamiFrameModel) -> Result<Self> {
        let size = window.inner_size();
        let instance = wgpu::Instance::default();
        let surface = instance.create_surface(window).context("create surface")?;
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                compatible_surface: Some(&surface),
                force_fallback_adapter: false,
            })
            .await
            .context("request adapter")?;
        let (device, queue) = adapter
            .request_device(
                &wgpu::DeviceDescriptor {
                    label: Some("kotodama-kami-host-device"),
                    required_features: wgpu::Features::empty(),
                    required_limits: wgpu::Limits::default(),
                    memory_hints: wgpu::MemoryHints::Performance,
                },
                None,
            )
            .await
            .context("request device")?;

        let surface_caps = surface.get_capabilities(&adapter);
        let surface_format = surface_caps
            .formats
            .iter()
            .copied()
            .find(|f| f.is_srgb())
            .unwrap_or(surface_caps.formats[0]);
        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format: surface_format,
            width: size.width.max(1),
            height: size.height.max(1),
            present_mode: surface_caps.present_modes[0],
            alpha_mode: surface_caps.alpha_modes[0],
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        surface.configure(&device, &config);
        Self::from_parts(Some(surface), device, queue, config, frame)
    }

    pub async fn new_headless(frame: KamiFrameModel) -> Result<Self> {
        let instance = wgpu::Instance::default();
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                compatible_surface: None,
                force_fallback_adapter: false,
            })
            .await
            .context("request headless adapter")?;
        let (device, queue) = adapter
            .request_device(
                &wgpu::DeviceDescriptor {
                    label: Some("kotodama-kami-host-headless-device"),
                    required_features: wgpu::Features::empty(),
                    required_limits: wgpu::Limits::default(),
                    memory_hints: wgpu::MemoryHints::Performance,
                },
                None,
            )
            .await
            .context("request headless device")?;
        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            width: frame.config.width.max(1),
            height: frame.config.height.max(1),
            present_mode: wgpu::PresentMode::Fifo,
            alpha_mode: wgpu::CompositeAlphaMode::Auto,
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        Self::from_parts(None, device, queue, config, frame)
    }

    fn from_parts(
        surface: Option<wgpu::Surface<'static>>,
        device: wgpu::Device,
        queue: wgpu::Queue,
        config: wgpu::SurfaceConfiguration,
        frame: KamiFrameModel,
    ) -> Result<Self> {
        let vertices = [
            QuadVertex { pos: [0.0, 0.0] },
            QuadVertex { pos: [1.0, 0.0] },
            QuadVertex { pos: [1.0, 1.0] },
            QuadVertex { pos: [0.0, 0.0] },
            QuadVertex { pos: [1.0, 1.0] },
            QuadVertex { pos: [0.0, 1.0] },
        ];
        let vertex_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("kami-host-quad-vertices"),
            contents: bytemuck::cast_slice(&vertices),
            usage: wgpu::BufferUsages::VERTEX,
        });

        let mut text_atlas =
            DynamicGlyphAtlas::new_default(18.0, 1024).context("create dynamic glyph atlas")?;
        text_atlas
            .ensure_text(&frame.current_text_corpus())
            .context("seed dynamic glyph atlas")?;
        let mut color_glyph_atlas = DynamicColorGlyphAtlas::new(18.0, 128);
        color_glyph_atlas.ensure_text(&frame.current_text_corpus());
        let layer = frame.to_ui_layer_with_atlases(text_atlas.atlas(), color_glyph_atlas.atlas());
        let instances = layer.to_instances();
        let text_instances = layer.to_text_instances();
        let color_glyph_instances = layer.to_color_glyph_instances();
        let instance_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("kami-host-ui-instances"),
            contents: bytemuck::cast_slice(&instances),
            usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
        });
        let text_instance_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("kami-host-text-instances"),
            contents: bytemuck::cast_slice(&text_instances),
            usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
        });
        let color_glyph_instance_buffer =
            device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("kami-host-color-glyph-instances"),
                contents: bytemuck::cast_slice(&color_glyph_instances),
                usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
            });

        let uniform = ScreenUniform {
            size: [config.width as f32, config.height as f32],
            _pad: [0.0, 0.0],
        };
        let uniform_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("kami-host-screen-uniform"),
            contents: bytemuck::bytes_of(&uniform),
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        });

        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("kami-host-bind-group-layout"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            }],
        });
        let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("kami-host-bind-group"),
            layout: &bind_group_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: uniform_buffer.as_entire_binding(),
            }],
        });

        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("kami-host-shader"),
            source: wgpu::ShaderSource::Wgsl(RECT_SHADER.into()),
        });
        let text_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("kami-host-text-shader"),
            source: wgpu::ShaderSource::Wgsl(TEXT_SHADER.into()),
        });
        let color_glyph_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("kami-host-color-glyph-shader"),
            source: wgpu::ShaderSource::Wgsl(COLOR_GLYPH_SHADER.into()),
        });
        let atlas = text_atlas.atlas();
        let atlas_texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("kami-host-text-atlas"),
            size: wgpu::Extent3d {
                width: atlas.width.max(1),
                height: atlas.height.max(1),
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::R8Unorm,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });
        queue.write_texture(
            atlas_texture.as_image_copy(),
            &atlas.sdf_data,
            wgpu::TexelCopyBufferLayout {
                offset: 0,
                bytes_per_row: Some(atlas.width.max(1)),
                rows_per_image: Some(atlas.height.max(1)),
            },
            wgpu::Extent3d {
                width: atlas.width.max(1),
                height: atlas.height.max(1),
                depth_or_array_layers: 1,
            },
        );
        let atlas_view = atlas_texture.create_view(&wgpu::TextureViewDescriptor::default());
        let atlas_sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("kami-host-text-sampler"),
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            mipmap_filter: wgpu::FilterMode::Nearest,
            ..wgpu::SamplerDescriptor::default()
        });
        let color_glyph_texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("kami-host-color-glyph-atlas"),
            size: wgpu::Extent3d {
                width: color_glyph_atlas.atlas().width.max(1),
                height: color_glyph_atlas.atlas().height.max(1),
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });
        queue.write_texture(
            color_glyph_texture.as_image_copy(),
            &color_glyph_atlas.atlas().rgba_data,
            wgpu::TexelCopyBufferLayout {
                offset: 0,
                bytes_per_row: Some(color_glyph_atlas.atlas().width.max(1) * 4),
                rows_per_image: Some(color_glyph_atlas.atlas().height.max(1)),
            },
            wgpu::Extent3d {
                width: color_glyph_atlas.atlas().width.max(1),
                height: color_glyph_atlas.atlas().height.max(1),
                depth_or_array_layers: 1,
            },
        );
        let color_glyph_view =
            color_glyph_texture.create_view(&wgpu::TextureViewDescriptor::default());
        let color_glyph_sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("kami-host-color-glyph-sampler"),
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            mipmap_filter: wgpu::FilterMode::Nearest,
            ..wgpu::SamplerDescriptor::default()
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("kami-host-pipeline-layout"),
            bind_group_layouts: &[&bind_group_layout],
            push_constant_ranges: &[],
        });
        let text_bind_group_layout =
            device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
                label: Some("kami-host-text-bind-group-layout"),
                entries: &[
                    wgpu::BindGroupLayoutEntry {
                        binding: 0,
                        visibility: wgpu::ShaderStages::FRAGMENT,
                        ty: wgpu::BindingType::Texture {
                            sample_type: wgpu::TextureSampleType::Float { filterable: true },
                            view_dimension: wgpu::TextureViewDimension::D2,
                            multisampled: false,
                        },
                        count: None,
                    },
                    wgpu::BindGroupLayoutEntry {
                        binding: 1,
                        visibility: wgpu::ShaderStages::FRAGMENT,
                        ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                        count: None,
                    },
                ],
            });
        let text_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("kami-host-text-bind-group"),
            layout: &text_bind_group_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: wgpu::BindingResource::TextureView(&atlas_view),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::Sampler(&atlas_sampler),
                },
            ],
        });
        let color_glyph_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("kami-host-color-glyph-bind-group"),
            layout: &text_bind_group_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: wgpu::BindingResource::TextureView(&color_glyph_view),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::Sampler(&color_glyph_sampler),
                },
            ],
        });
        let text_pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("kami-host-text-pipeline-layout"),
            bind_group_layouts: &[&bind_group_layout, &text_bind_group_layout],
            push_constant_ranges: &[],
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("kami-host-pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs_main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                buffers: &[
                    wgpu::VertexBufferLayout {
                        array_stride: std::mem::size_of::<QuadVertex>() as wgpu::BufferAddress,
                        step_mode: wgpu::VertexStepMode::Vertex,
                        attributes: &[wgpu::VertexAttribute {
                            offset: 0,
                            shader_location: 0,
                            format: wgpu::VertexFormat::Float32x2,
                        }],
                    },
                    wgpu::VertexBufferLayout {
                        array_stride: std::mem::size_of::<UiRect>() as wgpu::BufferAddress,
                        step_mode: wgpu::VertexStepMode::Instance,
                        attributes: &[
                            wgpu::VertexAttribute {
                                offset: 0,
                                shader_location: 1,
                                format: wgpu::VertexFormat::Float32x2,
                            },
                            wgpu::VertexAttribute {
                                offset: 8,
                                shader_location: 2,
                                format: wgpu::VertexFormat::Float32x2,
                            },
                            wgpu::VertexAttribute {
                                offset: 16,
                                shader_location: 3,
                                format: wgpu::VertexFormat::Float32x4,
                            },
                        ],
                    },
                ],
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs_main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format: config.format,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });
        let text_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("kami-host-text-pipeline"),
            layout: Some(&text_pipeline_layout),
            vertex: wgpu::VertexState {
                module: &text_shader,
                entry_point: Some("vs_main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                buffers: &[
                    wgpu::VertexBufferLayout {
                        array_stride: std::mem::size_of::<QuadVertex>() as wgpu::BufferAddress,
                        step_mode: wgpu::VertexStepMode::Vertex,
                        attributes: &[wgpu::VertexAttribute {
                            offset: 0,
                            shader_location: 0,
                            format: wgpu::VertexFormat::Float32x2,
                        }],
                    },
                    wgpu::VertexBufferLayout {
                        array_stride: std::mem::size_of::<UiText>() as wgpu::BufferAddress,
                        step_mode: wgpu::VertexStepMode::Instance,
                        attributes: &[
                            wgpu::VertexAttribute {
                                offset: 0,
                                shader_location: 1,
                                format: wgpu::VertexFormat::Float32x2,
                            },
                            wgpu::VertexAttribute {
                                offset: 8,
                                shader_location: 2,
                                format: wgpu::VertexFormat::Float32x2,
                            },
                            wgpu::VertexAttribute {
                                offset: 16,
                                shader_location: 3,
                                format: wgpu::VertexFormat::Float32x4,
                            },
                            wgpu::VertexAttribute {
                                offset: 32,
                                shader_location: 4,
                                format: wgpu::VertexFormat::Float32x4,
                            },
                        ],
                    },
                ],
            },
            fragment: Some(wgpu::FragmentState {
                module: &text_shader,
                entry_point: Some("fs_main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format: config.format,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });
        let color_glyph_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("kami-host-color-glyph-pipeline"),
            layout: Some(&text_pipeline_layout),
            vertex: wgpu::VertexState {
                module: &color_glyph_shader,
                entry_point: Some("vs_main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                buffers: &[
                    wgpu::VertexBufferLayout {
                        array_stride: std::mem::size_of::<QuadVertex>() as wgpu::BufferAddress,
                        step_mode: wgpu::VertexStepMode::Vertex,
                        attributes: &[wgpu::VertexAttribute {
                            offset: 0,
                            shader_location: 0,
                            format: wgpu::VertexFormat::Float32x2,
                        }],
                    },
                    wgpu::VertexBufferLayout {
                        array_stride: std::mem::size_of::<UiColorGlyph>() as wgpu::BufferAddress,
                        step_mode: wgpu::VertexStepMode::Instance,
                        attributes: &[
                            wgpu::VertexAttribute {
                                offset: 0,
                                shader_location: 1,
                                format: wgpu::VertexFormat::Float32x2,
                            },
                            wgpu::VertexAttribute {
                                offset: 8,
                                shader_location: 2,
                                format: wgpu::VertexFormat::Float32x2,
                            },
                            wgpu::VertexAttribute {
                                offset: 16,
                                shader_location: 3,
                                format: wgpu::VertexFormat::Float32x4,
                            },
                        ],
                    },
                ],
            },
            fragment: Some(wgpu::FragmentState {
                module: &color_glyph_shader,
                entry_point: Some("fs_main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format: config.format,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });

        let mut state = Self {
            surface,
            device,
            queue,
            config,
            pipeline,
            text_pipeline,
            color_glyph_pipeline,
            vertex_buffer,
            vertex_count: vertices.len() as u32,
            instance_buffer,
            instance_count: instances.len() as u32,
            text_instance_buffer,
            text_instance_count: text_instances.len() as u32,
            color_glyph_instance_buffer,
            color_glyph_instance_count: color_glyph_instances.len() as u32,
            uniform_buffer,
            bind_group,
            text_bind_group_layout,
            text_bind_group,
            text_sampler: atlas_sampler,
            text_atlas_texture: atlas_texture,
            text_atlas,
            color_glyph_bind_group,
            color_glyph_sampler,
            color_glyph_texture,
            color_glyph_atlas,
            clear_color: wgpu::Color {
                r: 0.94,
                g: 0.91,
                b: 0.86,
                a: 1.0,
            },
            frame,
            pending_inputs: VecDeque::new(),
            focused_element: Some("scan-now".to_string()),
            hovered_element: None,
            pointer_pos: None,
        };
        state.apply_visual_state();
        state.refresh_instances();
        Ok(state)
    }

    pub fn current_scene_snapshot(&self) -> SceneSnapshot {
        self.frame.to_scene_snapshot()
    }

    pub fn render_capabilities(&self) -> RenderCapabilities {
        RenderCapabilities {
            text_visible: true,
            keyboard_navigation: true,
            focus_ring_visible: true,
            hover_feedback: true,
            responsive_layout: true,
            semantic_lists: false,
        }
    }

    pub fn evaluate_uiux(&self) -> UiUxReport {
        evaluate_uiux(&self.current_scene_snapshot(), &self.render_capabilities())
    }

    pub fn inject_input_events<I>(&mut self, events: I)
    where
        I: IntoIterator<Item = InputEvent>,
    {
        self.pending_inputs.extend(events);
    }

    pub fn capture_screenshot_png(&mut self, path: &Path) -> Result<ScreenshotArtifact> {
        let width = self.config.width.max(1);
        let height = self.config.height.max(1);
        let texture = self.device.create_texture(&wgpu::TextureDescriptor {
            label: Some("kami-host-screenshot-texture"),
            size: wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: self.config.format,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
            view_formats: &[],
        });
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());

        let bytes_per_pixel = 4u32;
        let unpadded_bytes_per_row = width * bytes_per_pixel;
        let padded_bytes_per_row = unpadded_bytes_per_row
            .div_ceil(wgpu::COPY_BYTES_PER_ROW_ALIGNMENT)
            * wgpu::COPY_BYTES_PER_ROW_ALIGNMENT;
        let output_buffer_size = padded_bytes_per_row as u64 * height as u64;
        let output_buffer = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("kami-host-screenshot-buffer"),
            size: output_buffer_size,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });

        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("kami-host-screenshot-encoder"),
            });
        self.encode_scene(&mut encoder, &view);
        encoder.copy_texture_to_buffer(
            texture.as_image_copy(),
            wgpu::TexelCopyBufferInfo {
                buffer: &output_buffer,
                layout: wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(padded_bytes_per_row),
                    rows_per_image: Some(height),
                },
            },
            wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
        );
        self.queue.submit(Some(encoder.finish()));

        let buffer_slice = output_buffer.slice(..);
        let (tx, rx) = std::sync::mpsc::channel();
        buffer_slice.map_async(wgpu::MapMode::Read, move |result| {
            let _ = tx.send(result);
        });
        let _ = self.device.poll(wgpu::MaintainBase::Wait);
        rx.recv().context("receive screenshot map result")??;

        let data = buffer_slice.get_mapped_range();
        let mut rgba = vec![0u8; (width * height * bytes_per_pixel) as usize];
        for row in 0..height as usize {
            let src_start = row * padded_bytes_per_row as usize;
            let src_end = src_start + unpadded_bytes_per_row as usize;
            let dst_start = row * unpadded_bytes_per_row as usize;
            let dst_end = dst_start + unpadded_bytes_per_row as usize;
            rgba[dst_start..dst_end].copy_from_slice(&data[src_start..src_end]);
        }
        drop(data);
        output_buffer.unmap();

        std::fs::create_dir_all(path.parent().unwrap_or_else(|| Path::new(".")))
            .with_context(|| format!("create screenshot dir {}", path.display()))?;
        let file =
            File::create(path).with_context(|| format!("create screenshot {}", path.display()))?;
        let mut encoder = png::Encoder::new(file, width, height);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().context("write png header")?;
        writer
            .write_image_data(&rgba)
            .context("write png image data")?;

        Ok(ScreenshotArtifact {
            id: screenshot_id("capture"),
            width,
            height,
            format: ScreenshotFormat::Png,
            path: path.display().to_string(),
            tags: vec!["kami-host".to_string()],
        })
    }

    pub fn run_automation_plan(
        &mut self,
        plan: &AutomationPlan,
        artifact_dir: &Path,
    ) -> Result<AutomationTranscript> {
        std::fs::create_dir_all(artifact_dir)
            .with_context(|| format!("create artifact dir {}", artifact_dir.display()))?;

        let mut transcript = AutomationTranscript {
            plan_id: plan.id.clone(),
            ..AutomationTranscript::default()
        };

        for (step_index, step) in plan.steps.iter().enumerate() {
            self.execute_automation_step(step_index, step, artifact_dir, &mut transcript)?;
        }

        Ok(transcript)
    }

    pub fn resize(&mut self, size: PhysicalSize<u32>) {
        if size.width == 0 || size.height == 0 {
            return;
        }
        self.config.width = size.width;
        self.config.height = size.height;
        self.frame.config.width = size.width;
        self.frame.config.height = size.height;
        self.frame.relayout();
        self.apply_visual_state();
        if let Some(surface) = &self.surface {
            surface.configure(&self.device, &self.config);
        }
        let uniform = ScreenUniform {
            size: [self.config.width as f32, self.config.height as f32],
            _pad: [0.0, 0.0],
        };
        self.queue
            .write_buffer(&self.uniform_buffer, 0, bytemuck::bytes_of(&uniform));
        self.refresh_instances();
    }

    pub fn render(&mut self) -> Result<()> {
        self.apply_pending_inputs();
        let Some(surface) = &self.surface else {
            return Ok(());
        };
        let surface_tex = match surface.get_current_texture() {
            Ok(frame) => frame,
            Err(wgpu::SurfaceError::Outdated | wgpu::SurfaceError::Lost) => {
                surface.configure(&self.device, &self.config);
                return Ok(());
            }
            Err(wgpu::SurfaceError::OutOfMemory) => anyhow::bail!("surface out of memory"),
            Err(wgpu::SurfaceError::Timeout) => return Ok(()),
            Err(wgpu::SurfaceError::Other) => return Ok(()),
        };
        let view = surface_tex
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("kami-host-render-encoder"),
            });
        self.encode_scene(&mut encoder, &view);
        self.queue.submit(Some(encoder.finish()));
        surface_tex.present();
        Ok(())
    }

    fn encode_scene(&self, encoder: &mut wgpu::CommandEncoder, view: &wgpu::TextureView) {
        let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: Some("kami-host-render-pass"),
            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                view,
                resolve_target: None,
                ops: wgpu::Operations {
                    load: wgpu::LoadOp::Clear(self.clear_color),
                    store: wgpu::StoreOp::Store,
                },
            })],
            depth_stencil_attachment: None,
            timestamp_writes: None,
            occlusion_query_set: None,
        });
        pass.set_pipeline(&self.pipeline);
        pass.set_bind_group(0, &self.bind_group, &[]);
        pass.set_vertex_buffer(0, self.vertex_buffer.slice(..));
        pass.set_vertex_buffer(1, self.instance_buffer.slice(..));
        pass.draw(0..self.vertex_count, 0..self.instance_count);
        if self.text_instance_count > 0 {
            pass.set_pipeline(&self.text_pipeline);
            pass.set_bind_group(0, &self.bind_group, &[]);
            pass.set_bind_group(1, &self.text_bind_group, &[]);
            pass.set_vertex_buffer(0, self.vertex_buffer.slice(..));
            pass.set_vertex_buffer(1, self.text_instance_buffer.slice(..));
            pass.draw(0..self.vertex_count, 0..self.text_instance_count);
        }
        if self.color_glyph_instance_count > 0 {
            pass.set_pipeline(&self.color_glyph_pipeline);
            pass.set_bind_group(0, &self.bind_group, &[]);
            pass.set_bind_group(1, &self.color_glyph_bind_group, &[]);
            pass.set_vertex_buffer(0, self.vertex_buffer.slice(..));
            pass.set_vertex_buffer(1, self.color_glyph_instance_buffer.slice(..));
            pass.draw(0..self.vertex_count, 0..self.color_glyph_instance_count);
        }
    }

    fn execute_automation_step(
        &mut self,
        step_index: usize,
        step: &AutomationStep,
        artifact_dir: &Path,
        transcript: &mut AutomationTranscript,
    ) -> Result<()> {
        match step {
            AutomationStep::WaitForElement { target, timeout_ms } => {
                let snapshot = self.current_scene_snapshot();
                let target = resolve_target(&snapshot, target).with_context(|| {
                    format!("step {step_index}: wait target not found within {timeout_ms}ms")
                })?;
                transcript.log(
                    step_index,
                    "ok",
                    format!("found element {} ({:?})", target.id, target.role),
                );
            }
            AutomationStep::Click { target } => {
                let snapshot = self.current_scene_snapshot();
                let events = click_events_for_target(&snapshot, target)
                    .with_context(|| format!("step {step_index}: click target not found"))?;
                self.inject_input_events(events);
                self.apply_pending_inputs();
                transcript.log(step_index, "ok", format!("clicked {:?}", target));
            }
            AutomationStep::DoubleClick { target } => {
                let snapshot = self.current_scene_snapshot();
                let mut events = click_events_for_target(&snapshot, target)
                    .with_context(|| format!("step {step_index}: double-click target not found"))?;
                let second_click = click_events_for_target(&snapshot, target)
                    .with_context(|| format!("step {step_index}: double-click target not found"))?;
                events.extend(second_click);
                self.inject_input_events(events);
                self.apply_pending_inputs();
                transcript.log(step_index, "ok", format!("double-clicked {:?}", target));
            }
            AutomationStep::MovePointer { target } => {
                let snapshot = self.current_scene_snapshot();
                let target = resolve_target(&snapshot, target)
                    .with_context(|| format!("step {step_index}: move target not found"))?;
                self.inject_input_events([InputEvent::PointerMove {
                    x: target.rect.center().x,
                    y: target.rect.center().y,
                    dx: 0.0,
                    dy: 0.0,
                    device: kami_input::Device::Mouse,
                    stylus: None,
                }]);
                self.apply_pending_inputs();
                transcript.log(step_index, "ok", format!("moved pointer to {}", target.id));
            }
            AutomationStep::KeyPress { code } => {
                self.inject_input_events(keypress_events(code));
                self.apply_pending_inputs();
                transcript.log(step_index, "ok", format!("pressed key {}", code));
            }
            AutomationStep::Screenshot { name, tags } => {
                let path = artifact_dir.join(format!("{step_index:02}-{name}.png"));
                let mut artifact = self.capture_screenshot_png(&path).with_context(|| {
                    format!("step {step_index}: capture screenshot {}", path.display())
                })?;
                artifact.id = format!("{}-{}", transcript.plan_id, name);
                artifact.tags.extend(tags.iter().cloned());
                transcript.screenshots.push(artifact);
                transcript.log(step_index, "ok", format!("captured screenshot {}", name));
            }
            AutomationStep::AssertTextContains { target, needle } => {
                let snapshot = self.current_scene_snapshot();
                let target = resolve_target(&snapshot, target).with_context(|| {
                    format!("step {step_index}: assert target not found for text match")
                })?;
                let text = target.text.as_deref().with_context(|| {
                    format!("step {step_index}: target {} has no text", target.id)
                })?;
                if !text.contains(needle) {
                    anyhow::bail!(
                        "step {step_index}: text assertion failed for {}: expected substring {:?} in {:?}",
                        target.id,
                        needle,
                        text
                    );
                }
                transcript.log(
                    step_index,
                    "ok",
                    format!("text assertion matched {:?} in {}", needle, target.id),
                );
            }
        }

        Ok(())
    }

    fn apply_pending_inputs(&mut self) {
        let mut changed = false;

        while let Some(event) = self.pending_inputs.pop_front() {
            match event {
                InputEvent::PointerMove { x, y, .. } => {
                    self.pointer_pos = Some((x, y));
                    let snapshot = self.current_scene_snapshot();
                    let hovered =
                        resolve_target(&snapshot, &kami_devtools::TargetRef::Position { x, y })
                            .filter(|target| target.role == SemanticRole::Button)
                            .map(|target| target.id.clone());
                    if hovered != self.hovered_element {
                        self.hovered_element = hovered;
                        changed = true;
                    }
                }
                InputEvent::PointerUp { x, y, .. } => {
                    let snapshot = self.current_scene_snapshot();
                    if let Some(target) =
                        resolve_target(&snapshot, &kami_devtools::TargetRef::Position { x, y })
                    {
                        self.focused_element = Some(target.id.clone());
                        changed |= self.activate_if_primary_action(&target.id);
                    }
                }
                InputEvent::KeyDown { code, .. } if code == "Tab" => {
                    changed |= self.focus_next_interactive();
                }
                InputEvent::KeyDown { code, .. } if code == "Enter" || code == "Space" => {
                    if let Some(id) = self.focused_element.clone() {
                        changed |= self.activate_if_primary_action(&id);
                    }
                }
                InputEvent::KeyDown { code, .. } if code == "Space" => {
                    self.clear_color = wgpu::Color {
                        r: 0.89,
                        g: 0.93,
                        b: 0.90,
                        a: 1.0,
                    };
                }
                _ => {}
            }
        }

        if changed {
            self.apply_visual_state();
            self.refresh_instances();
        }
    }

    fn focus_next_interactive(&mut self) -> bool {
        let snapshot = self.current_scene_snapshot();
        let interactive: Vec<String> = snapshot
            .elements
            .iter()
            .filter(|e| e.visible && e.enabled && e.role == SemanticRole::Button)
            .map(|e| e.id.clone())
            .collect();
        if interactive.is_empty() {
            return false;
        }
        let next = match self.focused_element.as_ref() {
            Some(current) => interactive
                .iter()
                .position(|id| id == current)
                .map(|index| interactive[(index + 1) % interactive.len()].clone())
                .unwrap_or_else(|| interactive[0].clone()),
            None => interactive[0].clone(),
        };
        let changed = self.focused_element.as_ref() != Some(&next);
        self.focused_element = Some(next);
        changed
    }

    fn activate_if_primary_action(&mut self, element_id: &str) -> bool {
        if element_id != "scan-now" {
            return false;
        }
        let mut changed = false;
        if let Some(meter) = self
            .frame
            .scene
            .meters
            .iter_mut()
            .find(|m| m.id == "reclaimable")
        {
            let next = (meter.value + 0.12).min(1.0);
            if (next - meter.value).abs() > f32::EPSILON {
                meter.value = next;
                changed = true;
            }
        }
        changed
    }

    fn apply_visual_state(&mut self) {
        for panel in &mut self.frame.scene.panels {
            if panel.id == "scan-now" {
                panel.fill.0 = if self.focused_element.as_deref() == Some("scan-now") {
                    [0.10, 0.49, 0.42, 1.0]
                } else if self.hovered_element.as_deref() == Some("scan-now") {
                    [0.09, 0.46, 0.40, 1.0]
                } else {
                    [0.07, 0.44, 0.38, 1.0]
                };
                panel.border = Some(crate::Color(
                    if self.focused_element.as_deref() == Some("scan-now") {
                        [0.95, 0.78, 0.36, 0.95]
                    } else {
                        [0.04, 0.28, 0.24, 0.18]
                    },
                ));
                panel.border_width = if self.focused_element.as_deref() == Some("scan-now") {
                    3.0
                } else {
                    1.0
                };
            }
        }
    }

    fn refresh_instances(&mut self) {
        let text_changed = self
            .text_atlas
            .ensure_text(&self.frame.current_text_corpus())
            .unwrap_or(false);
        let color_changed = self.color_glyph_atlas.ensure_text(&self.frame.current_text_corpus());
        self.refresh_text_atlas_resources(text_changed, color_changed);
        let layer = self
            .frame
            .to_ui_layer_with_atlases(self.text_atlas.atlas(), self.color_glyph_atlas.atlas());
        let instances = layer.to_instances();
        let text_instances = layer.to_text_instances();
        let color_glyph_instances = layer.to_color_glyph_instances();
        self.instance_count = instances.len() as u32;
        self.instance_buffer = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("kami-host-ui-instances"),
                contents: bytemuck::cast_slice(&instances),
                usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
            });
        self.text_instance_count = text_instances.len() as u32;
        self.text_instance_buffer =
            self.device
                .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("kami-host-text-instances"),
                    contents: bytemuck::cast_slice(&text_instances),
                    usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
                });
        self.color_glyph_instance_count = color_glyph_instances.len() as u32;
        self.color_glyph_instance_buffer =
            self.device
                .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("kami-host-color-glyph-instances"),
                    contents: bytemuck::cast_slice(&color_glyph_instances),
                    usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
                });
    }

    fn refresh_text_atlas_resources(&mut self, text_changed: bool, color_changed: bool) {
        if text_changed {
            let atlas = self.text_atlas.atlas();
            self.text_atlas_texture = self.device.create_texture(&wgpu::TextureDescriptor {
                label: Some("kami-host-text-atlas"),
                size: wgpu::Extent3d {
                    width: atlas.width.max(1),
                    height: atlas.height.max(1),
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: wgpu::TextureDimension::D2,
                format: wgpu::TextureFormat::R8Unorm,
                usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
                view_formats: &[],
            });
            self.queue.write_texture(
                self.text_atlas_texture.as_image_copy(),
                &atlas.sdf_data,
                wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(atlas.width.max(1)),
                    rows_per_image: Some(atlas.height.max(1)),
                },
                wgpu::Extent3d {
                    width: atlas.width.max(1),
                    height: atlas.height.max(1),
                    depth_or_array_layers: 1,
                },
            );
            let atlas_view = self
                .text_atlas_texture
                .create_view(&wgpu::TextureViewDescriptor::default());
            self.text_bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("kami-host-text-bind-group"),
                layout: &self.text_bind_group_layout,
                entries: &[
                    wgpu::BindGroupEntry {
                        binding: 0,
                        resource: wgpu::BindingResource::TextureView(&atlas_view),
                    },
                    wgpu::BindGroupEntry {
                        binding: 1,
                        resource: wgpu::BindingResource::Sampler(&self.text_sampler),
                    },
                ],
            });
        }
        if color_changed {
            let atlas = self.color_glyph_atlas.atlas();
            self.color_glyph_texture = self.device.create_texture(&wgpu::TextureDescriptor {
                label: Some("kami-host-color-glyph-atlas"),
                size: wgpu::Extent3d {
                    width: atlas.width.max(1),
                    height: atlas.height.max(1),
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: wgpu::TextureDimension::D2,
                format: wgpu::TextureFormat::Rgba8UnormSrgb,
                usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
                view_formats: &[],
            });
            self.queue.write_texture(
                self.color_glyph_texture.as_image_copy(),
                &atlas.rgba_data,
                wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(atlas.width.max(1) * 4),
                    rows_per_image: Some(atlas.height.max(1)),
                },
                wgpu::Extent3d {
                    width: atlas.width.max(1),
                    height: atlas.height.max(1),
                    depth_or_array_layers: 1,
                },
            );
            let color_view = self
                .color_glyph_texture
                .create_view(&wgpu::TextureViewDescriptor::default());
            self.color_glyph_bind_group =
                self.device.create_bind_group(&wgpu::BindGroupDescriptor {
                    label: Some("kami-host-color-glyph-bind-group"),
                    layout: &self.text_bind_group_layout,
                    entries: &[
                        wgpu::BindGroupEntry {
                            binding: 0,
                            resource: wgpu::BindingResource::TextureView(&color_view),
                        },
                        wgpu::BindGroupEntry {
                            binding: 1,
                            resource: wgpu::BindingResource::Sampler(&self.color_glyph_sampler),
                        },
                    ],
                });
        }
    }
}

pub fn default_screenshot_path(prefix: &str) -> Result<PathBuf> {
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .context("system time before unix epoch")?
        .as_millis();
    Ok(std::env::temp_dir().join(format!("{prefix}-{ts}.png")))
}

pub fn default_artifact_dir(prefix: &str) -> Result<PathBuf> {
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .context("system time before unix epoch")?
        .as_millis();
    Ok(std::env::temp_dir().join(format!("{prefix}-{ts}")))
}

pub fn write_transcript_json(
    transcript: &AutomationTranscript,
    artifact_dir: &Path,
) -> Result<PathBuf> {
    std::fs::create_dir_all(artifact_dir)
        .with_context(|| format!("create artifact dir {}", artifact_dir.display()))?;
    let path = artifact_dir.join(format!("{}.json", transcript.plan_id));
    let json = serde_json::to_vec_pretty(transcript).context("serialize automation transcript")?;
    std::fs::write(&path, json).with_context(|| format!("write transcript {}", path.display()))?;
    Ok(path)
}

pub fn write_uiux_report_json(report: &UiUxReport, artifact_dir: &Path) -> Result<PathBuf> {
    std::fs::create_dir_all(artifact_dir)
        .with_context(|| format!("create artifact dir {}", artifact_dir.display()))?;
    let path = artifact_dir.join("uiux-report.json");
    let json = serde_json::to_vec_pretty(report).context("serialize uiux report")?;
    std::fs::write(&path, json).with_context(|| format!("write uiux report {}", path.display()))?;
    Ok(path)
}

fn screenshot_id(prefix: &str) -> String {
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or_default();
    format!("{prefix}-{ts}")
}

#[derive(Debug)]
struct DecodedPng {
    width: u32,
    height: u32,
    rgba: Vec<u8>,
}

fn compare_png_against_golden(golden: &Path, actual: &Path, diff: &Path) -> Result<()> {
    let golden_png =
        decode_png(golden).with_context(|| format!("decode golden {}", golden.display()))?;
    let actual_png =
        decode_png(actual).with_context(|| format!("decode actual {}", actual.display()))?;
    if golden_png.width != actual_png.width || golden_png.height != actual_png.height {
        anyhow::bail!(
            "image size mismatch for {}: golden={}x{}, actual={}x{}",
            actual.display(),
            golden_png.width,
            golden_png.height,
            actual_png.width,
            actual_png.height
        );
    }

    let mut mismatch_pixels = 0usize;
    let pixel_count = (golden_png.width * golden_png.height) as usize;
    let mut diff_rgba = vec![0u8; actual_png.rgba.len()];

    for i in 0..pixel_count {
        let base = i * 4;
        let dr = actual_png.rgba[base].abs_diff(golden_png.rgba[base]);
        let dg = actual_png.rgba[base + 1].abs_diff(golden_png.rgba[base + 1]);
        let db = actual_png.rgba[base + 2].abs_diff(golden_png.rgba[base + 2]);
        let da = actual_png.rgba[base + 3].abs_diff(golden_png.rgba[base + 3]);
        let max_delta = dr.max(dg).max(db).max(da);
        if max_delta > 4 {
            mismatch_pixels += 1;
            diff_rgba[base] = 255;
            diff_rgba[base + 1] = max_delta;
            diff_rgba[base + 2] = 0;
            diff_rgba[base + 3] = 255;
        }
    }

    let mismatch_ratio = mismatch_pixels as f32 / pixel_count.max(1) as f32;
    if mismatch_ratio > 0.0005 {
        write_png(diff, actual_png.width, actual_png.height, &diff_rgba)
            .with_context(|| format!("write diff {}", diff.display()))?;
        anyhow::bail!(
            "golden mismatch for {}: {} pixels ({:.4}%) differ; diff={}",
            actual.display(),
            mismatch_pixels,
            mismatch_ratio * 100.0,
            diff.display()
        );
    }

    Ok(())
}

fn decode_png(path: &Path) -> Result<DecodedPng> {
    let bytes = std::fs::read(path).with_context(|| format!("read png {}", path.display()))?;
    let decoder = png::Decoder::new(Cursor::new(bytes));
    let mut reader = decoder.read_info().context("read png info")?;
    // png 0.18: output_buffer_size() returns Option<usize> (None on overflow).
    let buf_size = reader
        .output_buffer_size()
        .context("png output buffer size overflow")?;
    let mut buf = vec![0; buf_size];
    let info = reader.next_frame(&mut buf).context("read png frame")?;
    let data = &buf[..info.buffer_size()];
    let rgba = match info.color_type {
        png::ColorType::Rgba => data.to_vec(),
        png::ColorType::Rgb => data
            .chunks_exact(3)
            .flat_map(|px| [px[0], px[1], px[2], 255])
            .collect(),
        png::ColorType::GrayscaleAlpha => data
            .chunks_exact(2)
            .flat_map(|px| [px[0], px[0], px[0], px[1]])
            .collect(),
        png::ColorType::Grayscale => data.iter().flat_map(|v| [*v, *v, *v, 255]).collect(),
        png::ColorType::Indexed => anyhow::bail!("indexed png unsupported"),
    };
    Ok(DecodedPng {
        width: info.width,
        height: info.height,
        rgba,
    })
}

fn read_uiux_report_json(path: &Path) -> Result<UiUxReport> {
    let bytes = std::fs::read(path).with_context(|| format!("read uiux report {}", path.display()))?;
    serde_json::from_slice(&bytes).with_context(|| format!("parse uiux report {}", path.display()))
}

fn enforce_uiux_threshold(report: &UiUxReport, min_uiux_score: u8, report_path: &Path) -> Result<()> {
    if report.score < min_uiux_score {
        anyhow::bail!(
            "uiux score {} is below threshold {} ({})",
            report.score,
            min_uiux_score,
            report_path.display()
        );
    }
    if report.has_blockers() {
        anyhow::bail!(
            "uiux report contains high/critical blockers ({})",
            report_path.display()
        );
    }
    Ok(())
}

fn write_png(path: &Path, width: u32, height: u32, rgba: &[u8]) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("create diff dir {}", parent.display()))?;
    }
    let file = File::create(path).with_context(|| format!("create png {}", path.display()))?;
    let writer = std::io::BufWriter::new(file);
    let mut encoder = png::Encoder::new(writer, width, height);
    encoder.set_color(png::ColorType::Rgba);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder.write_header().context("write png header")?;
    writer.write_image_data(rgba).context("write png body")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use kami_devtools::TargetRef;

    #[test]
    fn default_screenshot_path_uses_png() {
        let path = default_screenshot_path("kami").expect("path");
        assert_eq!(path.extension().and_then(|s| s.to_str()), Some("png"));
    }

    #[test]
    fn default_artifact_dir_uses_prefix() {
        let path = default_artifact_dir("kami-plan").expect("path");
        assert!(
            path.file_name()
                .and_then(|s| s.to_str())
                .is_some_and(|s| s.starts_with("kami-plan-"))
        );
    }

    #[test]
    fn sample_scene_has_clickable_scan_target() {
        let snapshot = sample_diskcleaner_scene().to_scene_snapshot();
        let target = resolve_target(&snapshot, &TargetRef::ElementId("scan-now".to_string()))
            .expect("scan-now");
        assert!(target.enabled);
    }

    #[test]
    fn can_write_transcript_json() {
        let dir = std::env::temp_dir().join(format!("kami-transcript-{}", std::process::id()));
        let transcript = AutomationTranscript {
            plan_id: "smoke".to_string(),
            ..AutomationTranscript::default()
        };
        let path = write_transcript_json(&transcript, &dir).expect("write transcript");
        assert!(path.exists());
        let body = std::fs::read_to_string(&path).expect("read transcript");
        assert!(body.contains("\"plan_id\": \"smoke\""));
        let _ = std::fs::remove_file(&path);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn sample_scene_uiux_is_usable_after_text_and_input_upgrades() {
        let state = pollster::block_on(RenderState::new_headless(sample_diskcleaner_scene()))
            .expect("headless state");
        let report = state.evaluate_uiux();
        assert!(report.usable);
        assert!(report.score >= 70);
        assert!(
            !report
                .findings
                .iter()
                .any(|f| f.rule_id == "text.not-rendered")
        );
        assert!(
            !report
                .findings
                .iter()
                .any(|f| f.rule_id == "layout.not-responsive")
        );
    }

    #[test]
    fn compare_png_against_golden_accepts_identical_images() {
        let dir = std::env::temp_dir().join(format!("kami-golden-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("create dir");
        let golden = dir.join("golden.png");
        let actual = dir.join("actual.png");
        let diff = dir.join("diff.png");
        let rgba = vec![
            255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255,
        ];
        write_png(&golden, 2, 2, &rgba).expect("write golden");
        write_png(&actual, 2, 2, &rgba).expect("write actual");
        compare_png_against_golden(&golden, &actual, &diff).expect("compare");
        assert!(!diff.exists());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn compare_png_against_golden_rejects_large_diff() {
        let dir = std::env::temp_dir().join(format!("kami-golden-diff-{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("create dir");
        let golden = dir.join("golden.png");
        let actual = dir.join("actual.png");
        let diff = dir.join("diff.png");
        let golden_rgba = vec![255u8; 4 * 4 * 4];
        let actual_rgba = vec![0u8; 4 * 4 * 4];
        write_png(&golden, 4, 4, &golden_rgba).expect("write golden");
        write_png(&actual, 4, 4, &actual_rgba).expect("write actual");
        let err = compare_png_against_golden(&golden, &actual, &diff).expect_err("should fail");
        assert!(err.to_string().contains("golden mismatch"));
        assert!(diff.exists());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn enforce_uiux_threshold_rejects_low_score_report() {
        let report_path =
            std::env::temp_dir().join(format!("kami-uiux-threshold-{}.json", std::process::id()));
        let report = UiUxReport {
            score: 60,
            usable: false,
            findings: Vec::new(),
        };
        let err =
            enforce_uiux_threshold(&report, 85, &report_path).expect_err("score gate should fail");
        assert!(err.to_string().contains("below threshold"));
    }
}
