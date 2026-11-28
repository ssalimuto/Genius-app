"""Makes icon.png and presplash.png (navy + gold 'O'). Run once with Pillow; the app itself never imports Pillow."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); APP = os.path.dirname(HERE)
NAVY = (11, 21, 48); NAVY2 = (22, 38, 78); GOLD = (212, 165, 55); GOLD2 = (246, 214, 128)
def emblem(size, bg=True):
    S = size * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if bg:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=NAVY)
        glow = Image.new("RGBA", (S, S), (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
        g.ellipse([S * .18, S * .18, S * .82, S * .82], fill=NAVY2)
        im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(S * .06)))
        d = ImageDraw.Draw(im)
    # gold ring = the "O"
    c, r_out, w = S / 2, S * 0.30, S * 0.085
    d.ellipse([c - r_out, c - r_out, c + r_out, c + r_out], fill=GOLD)
    d.ellipse([c - r_out + w, c - r_out + w, c + r_out - w, c + r_out - w], fill=NAVY if bg else (0, 0, 0, 0))
    # small highlight arc + spark
    d.arc([c - r_out, c - r_out, c + r_out, c + r_out], 200, 250, fill=GOLD2, width=int(w * .35))
    s = S * 0.045
    d.polygon([(c + r_out * .72, c - r_out * .98 - s), (c + r_out * .72 + s * .35, c - r_out * .98 - s * .35),
               (c + r_out * .72 + s, c - r_out * .98), (c + r_out * .72 + s * .35, c - r_out * .98 + s * .35),
               (c + r_out * .72, c - r_out * .98 + s), (c + r_out * .72 - s * .35, c - r_out * .98 + s * .35),
               (c + r_out * .72 - s, c - r_out * .98), (c + r_out * .72 - s * .35, c - r_out * .98 - s * .35)], fill=GOLD2)
    return im.resize((size, size), Image.LANCZOS)
emblem(512).save(os.path.join(APP, "icon.png"), optimize=True)
# presplash: emblem + word on navy, small file
P = Image.new("RGB", (512, 640), NAVY)
P.paste(emblem(360, bg=False), (76, 90), emblem(360, bg=False))
d = ImageDraw.Draw(P)
font = os.path.join(APP, "fonts", "Inter-Bold.ttf")
f = ImageFont.truetype(font, 64) if os.path.exists(font) else ImageFont.load_default()
f2 = ImageFont.truetype(font.replace("Bold", "Regular"), 22) if os.path.exists(font) else ImageFont.load_default()
for text, fo, y, col in (("Orax", f, 470, GOLD), ("Made by Ssali Muto", f2, 560, (170, 180, 200))):
    w = d.textlength(text, font=fo); d.text(((512 - w) / 2, y), text, font=fo, fill=col)
P.save(os.path.join(APP, "presplash.png"), optimize=True)
print("ok")
