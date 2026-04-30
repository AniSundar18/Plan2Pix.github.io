import os
import sys


if sys.version_info[0] < 3:
    sys.stderr.write("This script needs Python 3. Run: python3 crop_gif_gradio.py\n")
    sys.exit(1)


from pathlib import Path

# The cluster has an old system Jinja2 paired with user-installed MarkupSafe.
# Jinja2 imports soft_unicode, which MarkupSafe 2.1+ renamed to soft_str.
try:
    import markupsafe

    if not hasattr(markupsafe, "soft_unicode") and hasattr(markupsafe, "soft_str"):
        markupsafe.soft_unicode = markupsafe.soft_str
except ImportError:
    pass

try:
    import gradio as gr
except AttributeError as exc:
    if "BitGenerator" in str(exc):
        sys.stderr.write(
            "Gradio installed pandas 2.x, but this Python is loading an old numpy.\n"
            "Fix it with:\n"
            "  python3 -m pip install --user --upgrade 'numpy==1.24.4'\n"
            "Then rerun:\n"
            "  python3 crop_gif_gradio.py\n"
        )
        sys.exit(1)
    raise
from PIL import Image, ImageSequence


ROOT = Path(__file__).resolve().parent
GIF_DIR = ROOT / "gifs"


def list_gifs():
    GIF_DIR.mkdir(exist_ok=True)
    return sorted(path.name for path in GIF_DIR.glob("*.gif"))


def gif_size(gif_name):
    if not gif_name:
        return 1, 1

    with Image.open(GIF_DIR / gif_name) as image:
        return image.size


def clamp_crop_box(width, height, left, top, right, bottom):
    left = max(0, min(left, width - 1))
    top = max(0, min(top, height - 1))
    right = max(0, min(right, width - left - 1))
    bottom = max(0, min(bottom, height - top - 1))
    return left, top, width - right, height - bottom


def crop_gif(gif_name, left, top, right, bottom, output_name, overwrite):
    if not gif_name:
        raise gr.Error("Pick a GIF first.")

    input_path = GIF_DIR / gif_name
    if not input_path.exists():
        raise gr.Error("Missing GIF: {}".format(input_path))

    if not output_name.strip():
        output_name = "{}-cropped.gif".format(input_path.stem)

    if not output_name.lower().endswith(".gif"):
        output_name = "{}.gif".format(output_name)

    output_path = GIF_DIR / output_name
    if output_path.exists() and not overwrite:
        raise gr.Error(
            "{} already exists. Enable overwrite or choose a new name.".format(output_path.name)
        )

    with Image.open(input_path) as image:
        width, height = image.size
        box = clamp_crop_box(width, height, int(left), int(top), int(right), int(bottom))

        frames = []
        durations = []
        disposals = []

        for frame in ImageSequence.Iterator(image):
            frames.append(frame.convert("RGBA").crop(box))
            durations.append(frame.info.get("duration", image.info.get("duration", 100)))
            disposals.append(frame.disposal_method if hasattr(frame, "disposal_method") else 2)

        save_kwargs = {
            "save_all": True,
            "append_images": frames[1:],
            "duration": durations,
            "loop": image.info.get("loop", 0),
            "disposal": disposals,
            "optimize": False,
        }

        frames[0].save(output_path, **save_kwargs)

    return str(output_path)


def preview_crop(gif_name, left, top, right, bottom):
    if not gif_name:
        return None

    with Image.open(GIF_DIR / gif_name) as image:
        width, height = image.size
        box = clamp_crop_box(width, height, int(left), int(top), int(right), int(bottom))
        return image.convert("RGBA").crop(box)


def update_info(gif_name):
    if not gif_name:
        return "No GIF selected.", 0, 0, 0, 0

    width, height = gif_size(gif_name)
    max_x = max(0, width // 3)
    max_y = max(0, height // 3)
    text = "{}: {} x {}px".format(gif_name, width, height)
    return (
        text,
        gr.update(maximum=max_x, value=0),
        gr.update(maximum=max_y, value=0),
        gr.update(maximum=max_x, value=0),
        gr.update(maximum=max_y, value=0),
    )


def refresh_dropdown():
    gifs = list_gifs()
    return gr.Dropdown(choices=gifs, value=gifs[0] if gifs else None)


with gr.Blocks(title="GIF Cropper") as demo:
    gr.Markdown("# GIF Cropper")
    gr.Markdown("Crop all frames of a GIF by setting pixel margins. Files are read from and saved to `gifs/`.")

    with gr.Row():
        gif_dropdown = gr.Dropdown(choices=list_gifs(), label="GIF", scale=3)
        refresh = gr.Button("Refresh", scale=1)

    info = gr.Textbox(label="Selected GIF", interactive=False)

    with gr.Row():
        left = gr.Slider(0, 500, value=0, step=1, label="Crop left")
        right = gr.Slider(0, 500, value=0, step=1, label="Crop right")

    with gr.Row():
        top = gr.Slider(0, 500, value=0, step=1, label="Crop top")
        bottom = gr.Slider(0, 500, value=0, step=1, label="Crop bottom")

    preview = gr.Image(label="First-frame preview", type="pil")

    with gr.Row():
        output_name = gr.Textbox(label="Output filename", placeholder="example-cropped.gif")
        overwrite = gr.Checkbox(label="Overwrite existing file", value=False)

    save = gr.Button("Save Cropped GIF", variant="primary")
    saved_path = gr.File(label="Saved GIF")

    crop_inputs = [gif_dropdown, left, top, right, bottom]
    gif_dropdown.change(update_info, gif_dropdown, [info, left, top, right, bottom])
    gif_dropdown.change(preview_crop, crop_inputs, preview)
    left.change(preview_crop, crop_inputs, preview)
    top.change(preview_crop, crop_inputs, preview)
    right.change(preview_crop, crop_inputs, preview)
    bottom.change(preview_crop, crop_inputs, preview)
    refresh.click(refresh_dropdown, None, gif_dropdown)
    save.click(
        crop_gif,
        [gif_dropdown, left, top, right, bottom, output_name, overwrite],
        saved_path,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    demo.launch(server_name="0.0.0.0", server_port=port)
