"""
Find potential matches for unlinked glosses in all concept lists.
"""
import re


def run(args):
    i = 0
    for _, cl in sorted(args.repos.conceptlists.items(), key=lambda p: p[0]):
        for concept in sorted(
                cl.concepts.values(),
                key=lambda p: int(re.match('([0-9]+)', p.number).groups()[0])):
            if not concept.concepticon_id:
                candidates = [c for c in list(args.repos.lookup([concept.label]))[0] if c[3] < 3]
                if candidates:
                    candidate = sorted(candidates, key=lambda c: c[3])[0]
                    candidate = "{0} [{1}]".format(candidate[2], candidate[1])
                    i += 1
                    print("{0} {1.id}: {1.label}: {2}".format(i, concept, candidate))
