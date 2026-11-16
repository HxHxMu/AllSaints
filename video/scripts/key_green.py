"""Key a flat green (#00FF00) background to transparency, for parallax layers generated on green.

Usage: .venv/bin/python video/scripts/key_green.py in.png [more.png ...]   (writes each file in place)
"""
import sys

import numpy as np
from PIL import Image

for path in sys.argv[1:]:
    rgb = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    # how much greener than the other channels a pixel is: 0 = keep, high = background; soft ramp for antialiased edges
    excess = g - np.maximum(r, b)
    alpha = np.clip(1 - (excess - 40) / 80, 0, 1)
    # despill: pull green down to the other channels on the edges so no green fringe is left
    rgb[..., 1] = np.where(excess > 0, np.maximum(r, b) + excess * alpha * 0.3, g)
    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    Image.fromarray(out, 'RGBA').save(path)
    print(f'{path}: {100 * (alpha < 0.5).mean():.0f}% transparent')
