"""
Find potential matches for unlinked glosses in all concept lists.
"""
import re


def register(parser):
    parser.add_argument(
        '--full',
        action='store_true',
        default=False,
        help='',
    )
    parser.add_argument(
        '--inid',
        default=False,
        help="substring in list ID for lists to consider - leave empty to consider all.",
    )
    parser.add_argument(
        '--gloss',
        default=False,
        help="Pass a gloss to check if any unlinked concepts would be mapped to it.",
    )
    parser.add_argument(
        '--similarity-threshold',
        type=int,
        default=2,
        help='Maximal (dis)similarity index to still regard as potential match',
    )


def run(args):
    i, notlinked = 0, []
    for _, cl in sorted(args.repos.conceptlists.items(), key=lambda p: p[0]):
        if (not args.inid) or args.inid in cl.id:
            for concept in sorted(
                    cl.concepts.values(),
                    key=lambda p: int(re.match('([0-9]+)', p.number).groups()[0])):
                if not concept.concepticon_id:
                    notlinked.append(concept)
    to = [('1', args.gloss)] if args.gloss else None
    for j, matches in enumerate(args.repos.lookup(
            [c.label for c in notlinked], full_search=not args.full, to=to)):
        if matches:
            candidates = sorted(matches, key=lambda x: x[-1])
            cid, cgl = candidates[0][2:4]
            if cgl <= args.similarity_threshold:
                i += 1
                print('{0} {1.id}: {1.label}: {2} [{3}]'.format(i, notlinked[j], cid, cgl))
