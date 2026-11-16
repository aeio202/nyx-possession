"""Debugging aid: print predicted segments next to the public 5-minute ground truth.

For checking the pipeline is correct (alignment, label meaning, failure modes) only -- the public
window is not used to fit or choose any parameter. See RULES.md / EVALUATION.md.

    python solution/inspect_public.py solution/output/submission.csv
"""
import sys

import pandas as pd

GT = "evaluation/gt/BAR-ATH_possession_gt_public.csv"
A, B = 11185, 18685


def runs(labels):
    out, s = [], A
    for i in range(A + 1, B + 1):
        if i == B or labels[i] != labels[s]:
            out.append("{}{}-{}".format(labels[s], s, i - 1))
            s = i
    return out


if __name__ == "__main__":
    gt = pd.read_csv(GT).label.values
    pred = pd.read_csv(sys.argv[1]).label.values
    print("GT:  ", " ".join(runs(gt)))
    print("PRED:", " ".join(runs(pred)))
