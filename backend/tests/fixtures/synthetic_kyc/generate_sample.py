
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT_DIR = Path(__file__).resolve().parent

OUTPUT_FILE = OUTPUT_DIR / "synthetic_national_id.png"

WIDTH = 1400
HEIGHT = 800

image = Image.new(
    "RGB",
    (WIDTH, HEIGHT),
    color="white",
)

draw = ImageDraw.Draw(image)

try:
    heading_font = ImageFont.truetype(
        "C:/Windows/Fonts/arialbd.ttf",
        48,
    )

    body_font = ImageFont.truetype(
        "C:/Windows/Fonts/arial.ttf",
        42,
    )

except OSError:
    heading_font = ImageFont.load_default()
    body_font = ImageFont.load_default()


draw.rectangle(
    [(20, 20), (WIDTH - 20, HEIGHT - 20)],
    outline="black",
    width=4,
)

draw.text(
    (70, 55),
    "SYNTHETIC TEST DOCUMENT",
    fill="black",
    font=heading_font,
)

draw.text(
    (70, 125),
    "NOT A VALID IDENTITY DOCUMENT",
    fill="black",
    font=body_font,
)

fields = [
    "DOCUMENT TYPE: NATIONAL ID",
    "ID NUMBER: 12345678",
    "FULL NAME: JOHN KAMAU MWANGI",
    "DATE OF BIRTH: 15/06/2000",
    "SEX: MALE",
]

y_position = 230

for field in fields:
    draw.text(
        (70, y_position),
        field,
        fill="black",
        font=body_font,
    )

    y_position += 90


draw.text(
    (70, 710),
    "TEST DATA ONLY",
    fill="black",
    font=body_font,
)

image.save(OUTPUT_FILE)

print(f"Synthetic document created: {OUTPUT_FILE}")
