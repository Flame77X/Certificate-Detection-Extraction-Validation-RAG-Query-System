"""
Generate synthetic (fictional) certificate fixtures in backend/data/.

Real certificates must never be committed; use these for demos and OCR tests instead.
    python backend/scripts/make_sample_certs.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

SAMPLES = {
    # Trusted issuer, no expiry date (course completion)
    'sample_cert_image.png': [
        ('CERTIFICATE OF COMPLETION', 44),
        ('This is to certify that', 26),
        ('Jane Sample', 40),
        ('has successfully completed the course', 26),
        ('Applied Machine Learning Foundations', 30),
        ('Issued By: Global Tech Institute', 24),
        ('Certificate Number: GTI-2025-00417', 24),
        ('Date of Issue: 2025-02-14', 24),
    ],
    # Rendered to an image-only PDF to exercise the scanned-PDF OCR path
    'sample_scanned_cert.pdf': [
        ('CERTIFICATE OF ACHIEVEMENT', 44),
        ('This is to certify that', 26),
        ('Sam Example', 40),
        ('is hereby awarded the', 26),
        ('Cloud Operations Practitioner Certification', 30),
        ('Issued By: Ministry of Education', 24),
        ('Certificate Number: MOE-CP-2024-7731', 24),
        ('Date of Issue: 2024-06-01', 24),
        ('Valid Until: 2027-06-01', 24),
    ],
}

def _font(size):
    for name in ('DejaVuSans.ttf', 'arial.ttf', 'Arial.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)

def render(lines):
    img = Image.new('RGB', (1400, 1000), 'white')
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, 1370, 970], outline='black', width=6)
    y = 110
    for text, size in lines:
        font = _font(size)
        width = draw.textlength(text, font=font)
        draw.text(((1400 - width) / 2, y), text, fill='black', font=font)
        y += size + 45
    return img

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    for filename, lines in SAMPLES.items():
        path = os.path.join(DATA_DIR, filename)
        img = render(lines)
        if filename.endswith('.pdf'):
            img.save(path, 'PDF', resolution=150)
        else:
            img.save(path)
        print(f"wrote {path}")

if __name__ == '__main__':
    main()
