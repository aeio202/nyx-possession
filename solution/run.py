"""Regenerate the submission from the provided data.

    python solution/run.py                      # writes solution/output/submission.csv
    python solution/run.py --name myteam        # writes solution/output/myteam.csv

Deterministic: same data in, byte-identical file out.
"""

import argparse
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from games import GAME, GAMES, half_video_blocks  # noqa: E402
from solution import features as F  # noqa: E402
from solution.audio import whistles  # noqa: E402
from solution.load import load_atd, load_tags  # noqa: E402
from solution.model import LETTERS, PARAMS, emissions, restart_owner, viterbi  # noqa: E402

HALF_NAMES = {1: "1st Half", 2: "2nd Half"}


def predict(game=GAME, use_audio=True):
    atd = load_atd(game)
    tags = load_tags(game)
    return predict_with(atd, tags, PARAMS, game, with_feats=True, use_audio=use_audio)


def predict_with(atd, tags, params, game=GAME, with_feats=False, use_audio=True):
    blasts = whistles(game) if use_audio else None
    scores, feats = emissions(atd, tags, GAMES[game]["pitch"], params, blasts)
    kickoffs = F.kickoff_frames(tags)

    n = len(scores)
    labels = np.full(n, "X", dtype="<U1")
    for half, first, last in half_video_blocks(game):
        seg = slice(first, last + 1)
        force = np.zeros(last + 1 - first, dtype=bool)
        k = kickoffs.get(HALF_NAMES[half])
        if k is not None and k > first:
            # Before the automatically tagged kick-off window the match has not started,
            # and inside it not before the referee has whistled for the kick-off.
            force[:kickoff_release(k, blasts) - first] = True
        costs = {k: v[seg] for k, v in feats["costs"].items()}
        path = viterbi(scores[seg], costs, params, force_dead=force)
        path = restart_owner(path, tags, feats["team"][seg], first, params)
        labels[seg] = LETTERS[path]
    return (labels, feats) if with_feats else labels


def kickoff_release(tag_start, blasts, window=10 * F.FPS):
    """First frame at which play may start: the end of the first whistle blast within `window`
    frames of the start of the kick-off tag, or the tag start itself if none is heard."""
    if blasts is not None:
        inside = blasts[(blasts[:, 1] >= tag_start) & (blasts[:, 0] <= tag_start + window)]
        if len(inside):
            return int(inside[0, 1]) + 1
    return tag_start


def summarise(labels, game=GAME):
    fps = GAMES[game]["fps"]
    spells = []
    for _, first, last in half_video_blocks(game):
        seg = labels[first:last + 1]
        start = 0
        for i in range(1, len(seg) + 1):
            if i == len(seg) or seg[i] != seg[start]:
                if seg[start] in "HA":
                    spells.append(i - start)
                start = i
    graded = np.concatenate([labels[a:b + 1] for _, a, b in half_video_blocks(game)])
    counts = {k: int(np.sum(graded == k)) for k in "HADX"}
    print("graded frames: {}".format(counts))
    print("possessions: {}   mean {:.1f} s   median {:.1f} s".format(
        len(spells), np.mean(spells) / fps, np.median(spells) / fps))


def write(path, labels):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        fh.write("frame,label\n")
        fh.writelines("{},{}\n".format(i, l) for i, l in enumerate(labels))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="submission")
    ap.add_argument("--no-audio", action="store_true",
                    help="decode without the referee-whistle evidence (no ffmpeg needed)")
    ap.add_argument("--copy-to-results", action="store_true",
                    help="also copy into evaluation/results/ for local scoring")
    args = ap.parse_args()

    labels, _ = predict(use_audio=not args.no_audio)
    out = os.path.join(HERE, "output", args.name + ".csv")
    write(out, labels)
    summarise(labels)
    print("wrote", os.path.relpath(out, ROOT))
    if args.copy_to_results:
        dst = os.path.join(ROOT, "evaluation", "results", args.name + ".csv")
        shutil.copyfile(out, dst)
        print("copied to", os.path.relpath(dst, ROOT))
