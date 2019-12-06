import sourmash
from sourmash.cli.utils import add_ksize_arg

def subparser(subparsers):
    subparser = subparsers.add_parser('categorize')
    subparser.add_argument('sbt_name', help='name of SBT to load')
    subparser.add_argument(
        'queries', nargs='+',
        help='list of signatures to categorize'
    )
    subparser.add_argument(
        '-q', '--quiet', action='store_true',
        help='suppress non-error output'
    )
    add_ksize_arg(subparser, 31)
    subparser.add_argument(
        '--threshold', default=0.08, type=float,
        help='minimum threshold for reporting matches; default=0.08'
    )
    subparser.add_argument('--traverse-directory', action="store_true")
    subparser.add_argument(
        '--ignore-abundance', action='store_true',
        help='do NOT use k-mer abundances if present'
    )


def main(args):
    print(args)
