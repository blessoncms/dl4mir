import numpy as np
from dl4mir.chords import labels

import biggie

import dl4mir.common.util as util

from scipy.spatial.distance import cdist


def _circshift(entity, pitch_shift, bins_per_pitch):
    values = entity.values()
    data, chord_label = values.pop('data'), str(values.pop('chord_label'))

    # Change the chord label if it has a harmonic root.
    if chord_label not in [labels.NO_CHORD, labels.SKIP_CHORD]:
        root, quality, exts, bass = labels.split(chord_label)
        root = (labels.pitch_class_to_semitone(root) + pitch_shift) % 12
        new_root = labels.semitone_to_pitch_class(root)
        new_label = labels.join(new_root, quality, exts, bass)
        # print "Input %12s // Shift: %3s // Output %12s" % \
        #     (chord_label, pitch_shift, new_label)
        chord_label = new_label

    # Always rotate the CQT.
    data = util.circshift(data, 0, pitch_shift)
    return biggie.Entity(data=data, chord_label=chord_label, **values)


def _padshift(entity, pitch_shift, bins_per_pitch, fill_value=0.0):
    """
    entity : Entity
        CQT entity to shift; must have fields {data, chord_label}.
    """
    values = entity.values()
    data, chord_label = values.pop('data'), str(values.pop('chord_label'))

    # Change the chord label if it has a harmonic root.
    if chord_label not in [labels.NO_CHORD, labels.SKIP_CHORD]:
        root, quality, exts, bass = labels.split(chord_label)
        root = (labels.pitch_class_to_semitone(root) + pitch_shift) % 12
        new_root = labels.semitone_to_pitch_class(root)
        new_label = labels.join(new_root, quality, exts, bass)
        # print "Input %12s // Shift: %3s // Output %12s" % \
        #     (chord_label, pitch_shift, new_label)
        chord_label = new_label

    # Always rotate the CQT.
    bin_shift = pitch_shift*bins_per_pitch
    data = util.translate(data[0], 0, bin_shift, fill_value)[np.newaxis, ...]
    return biggie.Entity(data=data, chord_label=chord_label, **values)


def pitch_shift_cqt(stream, max_pitch_shift=6, bins_per_pitch=3):
    """Apply a random circular shift to the CQT, and rotate the root."""
    for entity in stream:
        if entity is None:
            yield entity
            continue

        # Determine the amount of pitch-shift.
        shift = np.random.randint(low=-max_pitch_shift,
                                  high=max_pitch_shift)
        yield _padshift(entity, shift, bins_per_pitch)


def pitch_shift_chroma(stream, max_pitch_shift=12):
    """Apply a random circular shift to the CQT, and rotate the root."""
    for entity in stream:
        if entity is None:
            yield entity
            continue

        # Determine the amount of pitch-shift.
        shift = np.random.randint(low=-max_pitch_shift,
                                  high=max_pitch_shift)
        yield _circshift(entity, shift, 1)


def map_to_class_index(stream, index_mapper, *args, **kwargs):
    """
    vocab_dim: int
    """
    for entity in stream:
        if entity is None:
            yield entity
            continue
        class_idx = index_mapper(entity, *args, **kwargs)
        yield None if class_idx is None else biggie.Entity(data=entity.data,
                                                           class_idx=class_idx)


def concatenate(stream, key='data', axis=-1):
    for entity in stream:
        if entity is None:
            yield entity
            continue
        values = entity.values()
        values[key] = np.concatenate([values.pop(key)]*2, axis=axis)
        yield biggie.Entity(**values)


def reshape(stream, newshape, key):
    for entity in stream:
        if entity is None:
            yield entity
            continue
        values = entity.values()
        values[key] = np.reshape(values.pop(key), newshape)
        yield biggie.Entity(**values)


def transpose(stream, axes, key):
    for entity in stream:
        if entity is None:
            yield entity
            continue
        values = entity.values()
        values[key] = np.transpose(values.pop(key), axes)
        yield biggie.Entity(**values)


def map_to_chroma(stream, bins_per_pitch=1):
    """
    vocab_dim: int
    """
    for entity in stream:
        if entity is None:
            yield entity
            continue
        values = entity.values()
        data, chord_label = values.pop('data'), str(values.pop('chord_label'))
        chroma = labels.chord_label_to_chroma(chord_label, bins_per_pitch)
        if (chroma < 0).any():
            yield None
        yield biggie.Entity(data=data, target=chroma)


def note_numbers_to_chroma(stream, bins_per_pitch=1):
    """
    vocab_dim: int
    """
    for entity in stream:
        if entity is None:
            yield entity
            continue
        pitches = set([_ % 12 for _ in eval(str(entity.note_numbers))])
        chroma = np.zeros(12*bins_per_pitch)
        for p in pitches:
            chroma[p*bins_per_pitch] = 1.0
        yield biggie.Entity(data=entity.data, target=chroma)


def note_numbers_to_pitch(stream, bins_per_pitch=1, max_pitch=84):
    """
    vocab_dim: int
    """
    for entity in stream:
        if entity is None:
            yield entity
            continue
        pitches = set(eval(str(entity.note_numbers)))
        pitch_vec = np.zeros(max_pitch+1)
        for p in pitches:
            pitch_vec[p] = 1.0
        yield biggie.Entity(data=entity.data, target=pitch_vec)


def chord_index_to_tonnetz(stream, vocab_dim):
    chord_labels = [labels.index_to_chord_label(n, vocab_dim)
                    for n in range(vocab_dim)]
    T = np.array([labels.chord_label_to_tonnetz(l)
                  for l in chord_labels]).squeeze()
    for entity in stream:
        if entity is None:
            yield entity
            continue
        yield biggie.Entity(cqt=entity.cqt, target=T[entity.chord_idx])


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


def chord_index_to_tonnetz_distance(stream, vocab_dim):
    chord_labels = [labels.index_to_chord_label(n, vocab_dim)
                    for n in range(vocab_dim)]
    X = np.array([labels.chord_label_to_tonnetz(l) for l in chord_labels])
    ssm = cdist(X.squeeze(), X.squeeze())
    sn_distance = 1 - ssm / ssm.max()
    for entity in stream:
        if entity is None:
            yield entity
            continue
        yield biggie.Entity(cqt=entity.cqt,
                            target=sn_distance[entity.chord_idx])


def chord_index_to_affinity_vectors(stream, vocab_dim):
    affinity_vectors = labels.affinity_vectors(vocab_dim)
    for entity in stream:
        if entity is None:
            yield entity
            continue
        yield biggie.Entity(cqt=entity.cqt,
                            target=affinity_vectors[entity.chord_idx])


def chord_index_to_onehot_vectors(stream, vocab_dim):
    one_hots = np.eye(vocab_dim)
    for entity in stream:
        if entity is None:
            yield entity
            continue
        yield biggie.Entity(cqt=entity.cqt,
                            target=one_hots[entity.chord_idx])


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
        chroma = entity.chroma.reshape(1, 12)
        chord_label = str(entity.chord_label)
        chord_idx = labels.chord_label_to_class_index(chord_label, 157)
        shift = target_root - chord_idx % 12
        # print chord_idx, shift, chord_label
        yield util.circshift(chroma, 0, shift).flatten()


def rotate_chord_to_root(stream, target_root):
    """Apply a circular shift to the CQT, and rotate the root."""
    for entity in stream:
        if entity is None:
            yield entity
            continue
        chord_label = str(entity.chord_label)
        chord_idx = labels.chord_label_to_class_index(chord_label, 157)
        shift = target_root - chord_idx % 12
        # print chord_idx, shift, chord_label
        yield _padshift(entity, shift, 3)


def unpack_contrastive_pairs(stream, vocab_dim, min_val=0.0, max_val=1.0,
                             rotate_prob=0.0):
    """
    vocab_dim: int
    """
    for pair in stream:
        if pair is None:
            yield pair
            continue
        pos_entity, neg_entity = pair
        pos_chord_label = str(pos_entity.chord_label)
        neg_chord_label = str(neg_entity.chord_label)
        pos_chord_idx = labels.chord_label_to_class_index(pos_chord_label,
                                                          vocab_dim)
        neg_chord_idx = labels.chord_label_to_class_index(neg_chord_label,
                                                          vocab_dim)
        if np.random.binomial(1, rotate_prob):
            shift = (pos_chord_idx - neg_chord_idx) % 12
            neg_entity = _padshift(neg_entity, shift, 3)
        yield biggie.Entity(cqt=pos_entity.cqt, chord_idx=pos_chord_idx,
                            target=np.array([max_val]))
        yield biggie.Entity(cqt=neg_entity.cqt, chord_idx=pos_chord_idx,
                            target=np.array([min_val]))


def binomial_mask(stream, max_dropout=0.25):
    for entity in stream:
        if entity is None:
            yield entity
            continue
        p = 1.0 - np.random.uniform(0, max_dropout)
        mask = np.random.binomial(1, p, entity.data.shape)
        entity.data = entity.data * mask
        yield entity


def awgn(stream, mu=0.0, sigma=0.1):
    for entity in stream:
        if entity is None:
            yield entity
            continue
        noise = np.random.normal(mu, sigma, entity.data.shape)
        entity.data = entity.data + noise * np.random.normal(0, 0.25)
        yield entity


def drop_frames(stream, max_dropout=0.1):
    for entity in stream:
        if entity is None:
            yield entity
            continue
        p = 1.0 - np.random.uniform(0, max_dropout)
        mask = np.random.binomial(1, p, entity.data.shape[1])
        mask[len(mask)/2] = 1.0
        entity.data = entity.data * mask[np.newaxis, :, np.newaxis]
        yield entity


def wrap_cqt(stream, length=40, stride=36):
    for entity in stream:
        if entity is None:
            yield entity
            continue
        assert entity.cqt.shape[0] == 1
        entity.cqt = util.fold_array(entity.cqt[0], length, stride)
        yield entity
