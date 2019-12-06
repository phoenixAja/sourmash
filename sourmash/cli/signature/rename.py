import sourmash
from sourmash.cli.utils import add_ksize_arg, add_moltype_args

def subparser(subparsers):
    subparser = subparsers.add_parser('rename')
    subparser.add_argument('sigfiles', nargs='+')
    subparser.add_argument('name')
    subparser.add_argument(
        '-q', '--quiet', action='store_true',
        help='suppress non-error output'
    )
    subparser.add_argument(
        '-d', '--debug', action='store_true',
        help='print debugging output'
    )
    subparser.add_argument(
        '-o', '--output', metavar='FILE', help='output to this file'
    )
    add_ksize_arg(subparser, 31)
    add_moltype_args(subparser)


def main(args):
    print(args)
