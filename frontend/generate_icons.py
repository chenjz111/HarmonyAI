"""Generate tabBar icons for HarmonyAI uni-app project.
Creates 4 PNG icons (81x81): home + play, normal(gray) + active(purple).
"""
from PIL import Image, ImageDraw

SIZE = 81
GRAY = (153, 153, 163, 255)
PURPLE = (108, 99, 255, 255)
WHITE_BG = (0, 0, 0, 0)  # transparent


def draw_home(draw, color):
    """Draw a simple house icon."""
    # Roof (triangle)
    draw.polygon([(40, 12), (66, 36), (14, 36)], fill=color)
    # Body (rectangle)
    draw.rectangle([20, 36, 60, 66], fill=color)
    # Door (cut out with transparent)
    draw.rectangle([34, 48, 46, 66], fill=WHITE_BG)


def draw_play(draw, color):
    """Draw a music note icon."""
    # Note head (ellipse)
    draw.ellipse([16, 48, 42, 68], fill=color)
    # Stem
    draw.rectangle([40, 18, 46, 56], fill=color)
    # Flag (triangle)
    draw.polygon([(46, 18), (62, 30), (46, 38)], fill=color)


def make_icon(draw_func, color, filename):
    img = Image.new("RGBA", (SIZE, SIZE), WHITE_BG)
    draw = ImageDraw.Draw(img)
    draw_func(draw, color)
    img.save(filename)
    print(f"Saved: {filename}")


def main():
    import os
    out_dir = os.path.join(os.path.dirname(__file__), "static", "tabbar")
    os.makedirs(out_dir, exist_ok=True)

    make_icon(draw_home, GRAY, os.path.join(out_dir, "home.png"))
    make_icon(draw_home, PURPLE, os.path.join(out_dir, "home-active.png"))
    make_icon(draw_play, GRAY, os.path.join(out_dir, "play.png"))
    make_icon(draw_play, PURPLE, os.path.join(out_dir, "play-active.png"))

    print("\nAll 4 tabBar icons generated successfully!")


if __name__ == "__main__":
    main()
