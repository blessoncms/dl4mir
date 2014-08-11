import numpy as np
from dl4mir.chords import labels

import biggie
from marl.utils.matrix import circshift
from marl.chords.utils import transpose_chord_index


def _pitch_shift(entity, pitch_shift, bins_per_pitch):
    values = entity.values()
    cqt, chord_label = values.pop('cqt'), str(values.pop('chord_label'))

    # Change the chord label if it has a harmonic root.
    if not chord_label in [labels.NO_CHORD, labels.SKIP_CHORD]:
        root, quality, exts, bass = labels.split(chord_label)
        root = (labels.pitch_class_to_semitone(root) + pitch_shift) % 12
        new_root = labels.semitone_to_pitch_class(root)
        new_label = labels.join(new_root, quality, exts, bass)
        # print "Input %12s // Shift: %3s // Output %12s" % \
        #     (chord_label, pitch_shift, new_label)
        chord_label = new_label

    # Always rotate the CQT.
    bin_shift = pitch_shift*bins_per_pitch
    cqt = circshift(cqt[0], 0, bin_shift)[np.newaxis, ...]
    return biggie.Entity(cqt=cqt, chord_label=chord_label, **values)


def pitch_shift(stream, max_pitch_shift=12, bins_per_pitch=3):
    """Apply a random circular shift to the CQT, and rotate the root."""
    for entity in stream:
        if entity is None:
            yield entity
            continue

        # Determine the amount of pitch-shift.
        shift = np.random.randint(low=-max_pitch_shift,
                                  high=max_pitch_shift)
        yield _pitch_shift(entity, shift, bins_per_pitch)


def map_to_chord_index(stream, vocab_dim):
    """
    vocab_dim: int
    """
    for entity in stream:
        if entity is None:
            yield entity
            continue
        values = entity.values()
        cqt, chord_label = values.pop('cqt'), str(values.pop('chord_label'))
        chord_idx = labels.chord_label_to_class_index(chord_label, vocab_dim)
        yield None if chord_idx is None else biggie.Entity(cqt=cqt,
                                                           chord_idx=chord_idx)


def map_to_chroma(stream):
    """
    vocab_dim: int
    """
    for entity in stream:
        if entity is None:
            yield entity
            continue
        values = entity.values()
        cqt, chord_label = values.pop('cqt'), str(values.pop('chord_label'))
        chroma = labels.chord_label_to_chroma(chord_label)
        yield biggie.Entity(cqt=cqt, target_chroma=chroma.squeeze())


def map_to_chord_quality_index(stream, vocab_dim):
    """
    vocab_dim: int
    """
    for entity in stream:
        if entity is None:
            yield entity
            continue
        values = entity.values()
        cqt, chord_label = values.pop('cqt'), str(values.pop('chord_label'))
        qual_idx = labels.chord_label_to_quality_index(chord_label, vocab_dim)
        yield None if qual_idx is None else biggie.Entity(cqt=cqt,
                                                          quality_idx=qual_idx)


def map_to_joint_index(stream, vocab_dim):
    """
    vocab_dim: int
    """
    for entity in stream:
        if entity is None:
            yield entity
            continue
        values = entity.values()
        cqt, chord_label = values.pop('cqt'), str(values.pop('chord_label'))
        chord_idx = labels.chord_label_to_class_index(chord_label, vocab_dim)
        if chord_idx is None:
            yield None
            continue
        if chord_idx == vocab_dim - 1:
            root_idx = 13
        else:
            root_idx = chord_idx % 12
        quality_idx = int(chord_idx) / 12

        yield biggie.Entity(cqt=cqt,
                            root_idx=root_idx,
                            quality_idx=quality_idx)


def rotate_chroma_to_root(stream, target_root):
    """Apply a circular shift to the CQT, and rotate the root."""
    for entity in stream:
        if entity is None:
            yield entity
            continue
        chroma = entity.chroma.value.reshape(1, 12)
        chord_label = str(entity.chord_label.value)
        chord_idx = labels.chord_label_to_class_index(chord_label, 157)
        shift = target_root - chord_idx % 12
        # print chord_idx, shift, chord_label
        yield circshift(chroma, 0, shift).flatten()


def unpack_contrastive_pairs(stream, vocab_dim, rotate_prob=0.75):
    """
    vocab_dim: int
    """
    for pair in stream:
        if pair is None:
            yield pair
            continue
        pos_entity, neg_entity = pair
        pos_chord_label = str(pos_entity.chord_label.value)
        neg_chord_label = str(neg_entity.chord_label.value)
        pos_chord_idx = labels.chord_label_to_class_index(pos_chord_label,
                                                          vocab_dim)
        neg_chord_idx = labels.chord_label_to_class_index(neg_chord_label,
                                                          vocab_dim)
        if np.random.binomial(1, rotate_prob):
            shift = (pos_chord_idx - neg_chord_idx) % 12
            neg_entity = _pitch_shift(neg_entity, shift, 3)
        # print pos_entity.chord_label.value, neg_entity.chord_label.value
        yield biggie.Entity(cqt=pos_entity.cqt.value,
                            chord_idx=pos_chord_idx, is_chord=1)
        yield biggie.Entity(cqt=neg_entity.cqt.value,
                            chord_idx=pos_chord_idx, is_chord=0)
