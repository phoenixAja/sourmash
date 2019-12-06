from argparse import FileType

def subparser(subparsers):
    subparser = subparsers.add_parser('ingest')
    subparser.add_argument('filenames', nargs='+')
    subparser.add_argument(
        '-q', '--quiet', action='store_true',
        help='suppress non-error output'
    )
    subparser.add_argument(
        '-o', '--output', metavar='FILE', type=FileType('wt'),
        help='output signature to this file'
    )

    # Dirty hack to simultaneously support new and previous interface
    # If desired, this function can be removed with a major version bump.
    subparser = subparsers.add_parser('import')
    subparser.add_argument('filenames', nargs='+')
    subparser.add_argument(
        '-q', '--quiet', action='store_true',
        help='suppress non-error output'
    )
    subparser.add_argument(
        '-o', '--output', metavar='FILE', type=FileType('wt'),
        help='output signature to this file'
    )


def main(args):
    print(args)
