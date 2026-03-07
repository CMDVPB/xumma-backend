def normalize_sequence(seq):
    result = []
    for k in seq:
        if k.startswith("key"):
            result.append(k[3:])  # keyk -> k
        else:
            result.append(k)
    return result
