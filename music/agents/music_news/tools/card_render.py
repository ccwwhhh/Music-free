

# tools/card_renderer.py
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
from pathlib import Path
import imgkit
from PIL import Image

WKHTMLTOIMAGE_PATH = r"D:\OpenAgents\music_free\wkhtmltopdf\bin\wkhtmltoimage.exe"
env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


def render_newspaper_html(article: dict, output_html: Path) -> Path:
    # Render the Jinja2 newspaper template with article content and sidebar summary.
    template = env.get_template("newspaper.html")
    summary = article.get("summary", article.get("caption", ""))
    quote = article.get("url", "")
    html = template.render(
        headline=article["title"],
        image_url=article["image_url"],
        caption=article["caption"],
        paragraphs=article["paragraphs"],
        sidebar_title_1="Summary",
        quote_text=quote,
        sidebar_text_1=summary,
    )

    output_html.write_text(html, encoding="utf-8")
    return output_html




def shrink_image(img_path: Path,
                 max_width: int = 900,
                 quality: int = 60) -> None:
    # Downscale and recompress the image to keep cards lightweight for transport.
    img_path = Path(img_path)
    im = Image.open(img_path).convert("RGB")
    w, h = im.size

    if w > max_width:
        new_h = int(h * max_width / w)
        im = im.resize((max_width, new_h), Image.LANCZOS)


    im.save(img_path, format="JPEG", quality=quality, optimize=True)

def html_to_image(html_path: Path, output_img: Path) -> Path:
    # Use wkhtmltoimage via imgkit to rasterize the HTML card and then shrink it.
    config = imgkit.config(wkhtmltoimage=WKHTMLTOIMAGE_PATH)
    options = {
        "format": "jpg",
        "quality": "70",
        "width": "900",

    }
    imgkit.from_file(str(html_path), str(output_img), config=config, options=options)


    shrink_image(output_img, max_width=900, quality=60)
    print("[html_to_image] final size:", output_img.stat().st_size, "bytes")

    return output_img