#!/usr/bin/env python3
"""Stitch four claude-in-chrome `zoom` captures (2x pixels each) into one sharp full-viewport frame.

    python3 stitch_tiles.py OUT.png TL.png TR.png BL.png BR.png --frame 1456x839

The tiles must be the zoom regions [0,0,W/2,H/2], [W/2,0,W,H/2], [0,H/2,W/2,H], [W/2,H/2,W,H] of the
coordinate frame W x H (integer halves, as printed by --regions). Output is 2W x 2H.
"""
import argparse

from PIL import Image


def halves(w, h):
    mw, mh = w // 2, h // 2
    return [(0, 0, mw, mh), (mw, 0, w, mh), (0, mh, mw, h), (mw, mh, w, h)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('out', nargs='?')
    parser.add_argument('tiles', nargs='*')
    parser.add_argument('--frame', required=True, help='coordinate frame, e.g. 1456x839')
    parser.add_argument('--regions', action='store_true', help='print the four zoom regions and exit')
    args = parser.parse_args()
    w, h = (int(v) for v in args.frame.lower().split('x'))
    regions = halves(w, h)
    if args.regions:
        for r in regions:
            print(list(r))
        return
    if not args.out or len(args.tiles) != 4:
        parser.error('give OUT and four tiles (TL TR BL BR)')
    canvas = Image.new('RGB', (w * 2, h * 2), (255, 255, 255))
    for path, (x0, y0, x1, y1) in zip(args.tiles, regions):
        tile = Image.open(path).convert('RGB')
        target = ((x1 - x0) * 2, (y1 - y0) * 2)
        if tile.size != target:
            tile = tile.resize(target, Image.LANCZOS)
        canvas.paste(tile, (x0 * 2, y0 * 2))
    canvas.save(args.out)
    print(args.out, canvas.size)


if __name__ == '__main__':
    main()
