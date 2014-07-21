"""Apply a graph convolutionally to datapoints in an optimus file."""

import argparse
import json
import numpy as np
import os
import mir_eval.chord as chord_eval
import marl.fileutils as futil
from dl4mir.chords import labels
import sklearn.metrics as metrics
import warnings


def rotate(posterior, root):
    """Rotate a class posterior to C (root invariance)"""
    return np.array([posterior[(n + root) % 12 + 12*(n/12)]
                     for n in range(len(posterior) - 1)]+[posterior[-1]])


def collapse_estimations(estimations):
    """Accumulate a set of track-wise estimations to a flattened set.

    Parameters
    ----------
    estimations: dict
        Dict of track keys, pointing to another dict of chord labels and
        class counts.

    Returns
    -------
    results: dict
        Dict of chord labels and corresponding class counts.
    """

    total = dict()
    for key in estimations:
        for label, counts in estimations[key].items():
            # N:maj are cropping up right now...?
            if label.startswith("N"):
                label = "N"
            if not label in total:
                total[label] = np.zeros_like(np.array(counts))
            total[label] += np.array(counts)
    return total


def confusion_matrix(results, num_classes,
                     label_to_index=labels.chord_label_to_class_index):
    """

    Confusion matrix is actual x estimations.

    """
    classifications = np.zeros([num_classes, num_classes])
    for label, counts in results.items():
        idx = label_to_index(label, num_classes)
        if idx is None:
            continue
        classifications[idx, :] += counts
    return classifications


def quality_confusion_matrix(results):
    num_classes = 157
    qual_conf = np.zeros([num_classes, num_classes])
    for label, counts in results.items():
        root, semitones, bass = chord_eval.encode(label)
        qidx = 13 if label == 'N' else labels.get_quality_index(semitones,
                                                                num_classes)
        if qidx is None:
            continue
        qual_conf[qidx*12, :] += rotate(counts,
                                        root) if qidx != 13 else counts
    return qual_conf


def compute_confusions(quality_confusions, top_k=5):
    if quality_confusions.shape[0] == 157:
        quality_confusions = quality_confusions[::12, :]

    outputs = []
    for idx, row in enumerate(quality_confusions):
        row /= float(row.sum())
        line = "%7s (%7.4f) ||" % (labels.index_to_chord_label(idx*12, 157),
                                   row[idx*12]*100)
        sidx = row.argsort()[::-1]
        k = 0
        count = 0
        while count < top_k:
            if sidx[k] != idx*12:
                line += " %7s (%7.4f) |" % \
                    (labels.index_to_chord_label(sidx[k], 157),
                     row[sidx[k]]*100)
                count += 1
            k += 1
        # print line
        outputs.append(line)
    return "\n".join(outputs)


def compute_scores(estimations):
    results = collapse_estimations(estimations)
    # confusions = confusion_matrix(results, 157)
    quality_confusions = quality_confusion_matrix(results)
    # chord_true, chord_est = confusions_to_comparisons(confusions)
    quality_true, quality_est = confusions_to_comparisons(quality_confusions)
    output = []
    with warnings.catch_warnings():
        labels = range(157)
        warnings.simplefilter("ignore")

        qual_precision_weighted = metrics.precision_score(
            quality_true, quality_est, labels=labels, average='weighted')
        qual_precision_ave = np.mean(metrics.precision_score(
            quality_true, quality_est, labels=labels, average=None)[::12])

        qual_recall_weighted = metrics.recall_score(
            quality_true, quality_est, labels=labels, average='weighted')
        qual_recall_ave = np.mean(metrics.recall_score(
            quality_true, quality_est, labels=labels, average=None)[::12])

        qual_f1_weighted = metrics.f1_score(
            quality_true, quality_est, labels=labels, average='weighted')
        qual_f1_ave = np.mean(metrics.f1_score(
            quality_true, quality_est, labels=labels, average=None)[::12])

    stat_line = "  Precision: %0.4f\t Recall: %0.4f\tf1: %0.4f"
    res1 = "Weighted: " + stat_line % (100*qual_precision_weighted,
                                       100*qual_recall_weighted,
                                       100*qual_f1_weighted)

    res2 = "Averaged: " + stat_line % (100*qual_precision_ave,
                                       100*qual_recall_ave,
                                       100*qual_f1_ave)
    res3 = "-"*60
    outputs = [res3, res1, res2, res3]
    outputs.append(compute_confusions(quality_confusions, 5))
    return "\n".join(outputs)


def confusions_to_comparisons(conf_mat):
    y_true, y_pred = [], []
    conf_mat = np.round(conf_mat).astype(int)
    for i in range(conf_mat.shape[0]):
        for j in range(conf_mat.shape[1]):
            count = conf_mat[i, j]
            y_true.append(i + np.zeros(count, dtype=int))
            y_pred.append(j + np.zeros(count, dtype=int))
    return np.concatenate(y_true), np.concatenate(y_pred)


def main(args):
    if not os.path.exists(args.estimation_file):
        print "File does not exist: %" % args.estimation_file
        return
    stats = compute_scores(json.load(open(args.estimation_file)))

    futil.create_directory(os.path.split(args.stats_file)[0])
    with open(args.stats_file, 'w') as fp:
        fp.write(stats)
    print "\n\n%s\n%s"  % (args.estimation_file, stats)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")

    # Inputs
    parser.add_argument("estimation_file",
                        metavar="estimation_file", type=str,
                        help="Path to a JSON file of estimations.")
    # Outputs
    parser.add_argument("stats_file",
                        metavar="stats_file", type=str,
                        help="Path for the resulting statistics as plaintext.")
    main(parser.parse_args())