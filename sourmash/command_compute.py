"""
Functions implementing the 'compute' command and related functions.
"""
from __future__ import print_function, division, absolute_import

import argparse
import os
import os.path
import sys
import random
import screed
import time

from bam2fasta import cli as bam2fasta_cli
from .sourmash_args import SourmashArgumentParser
from . import DEFAULT_SEED, MinHash
from . import signature as sig
from . import sourmash_args
from .logging import notify, error, set_quiet

from .sourmash_args import DEFAULT_N
DEFAULT_COMPUTE_K = '21,31,51'
DEFAULT_LINE_COUNT = 1500


def compute_add_args(parser):

    def ksize_parser(ksizes):
        # get list of k-mer sizes for which to compute sketches
        if ',' in ksizes:
            ksizes = ksizes.split(',')
            ksizes = list(map(int, ksizes))
        else:
            ksizes = [int(ksizes)]

        return ksizes

    parser.add_argument('filenames', nargs='+',
                        help='file(s) of sequences')

    sourmash_args.add_construct_moltype_args(parser)

    parser.add_argument('-q', '--quiet', action='store_true',
                        help='suppress non-error output')
    parser.add_argument('--input-is-protein', action='store_true',
                        help='Consume protein sequences - no translation needed.')
    parser.add_argument('-k', '--ksizes',
                        default=list(map(int, DEFAULT_COMPUTE_K.split(","))),
                        type=ksize_parser,
                        help='comma-separated list of k-mer sizes (default: %(default)s)')
    parser.add_argument('-n', '--num-hashes', type=int,
                        default=DEFAULT_N,
                        help='number of hashes to use in each sketch (default: %(default)i)')
    parser.add_argument('--check-sequence', action='store_true',
                        help='complain if input sequence is invalid (default: False)')
    parser.add_argument('-f', '--force', action='store_true',
                        help='recompute signatures even if the file exists (default: False)')
    parser.add_argument('-o', '--output', type=argparse.FileType('wt'),
                        help='output computed signatures to this file')
    parser.add_argument('--singleton', action='store_true',
                        help='compute a signature for each sequence record individually (default: False)')
    parser.add_argument('--merge', '--name', type=str, default='', metavar="MERGED",
                        help="merge all input files into one signature named this")
    parser.add_argument('--name-from-first', action='store_true',
                        help="name the signature generated from each file after the first record in the file (default: False)")
    parser.add_argument('--input-is-10x', action='store_true',
                        help="Input is 10x single cell output folder (default: False)")
    parser.add_argument('--count-valid-reads', default=0, type=int,
                        help="For 10x input only (i.e input-is-10x flag is True), "
                        "A barcode is only considered a valid barcode read "
                        "and its signature is written if number of umis are greater "
                        "than count-valid-reads. It is used to weed out cell barcodes "
                        "with few umis that might have been due to false rna enzyme reactions")
    parser.add_argument('--write-barcode-meta-csv', type=str,
                        help="For 10x input only (i.e input-is-10x flag is True), for each of the unique barcodes, "
                        "Write to a given path, number of reads and number of umis per barcode.")
    parser.add_argument('-p', '--processes', default=2, type=int,
                        help='For 10x input only (i.e input-is-10x flag is True, '
                        'Number of processes to use for reading 10x bam file')
    parser.add_argument('--save-fastas', default="", type=str,
                        help='For 10x input only (i.e input-is-10x flag is True), '
                        'save merged fastas for all the unique barcodes to {CELL_BARCODE}.fasta '
                        'in the absolute path given by this flag, By default, fastas are not saved')
    parser.add_argument('--line-count', type=int,
                        help='For 10x input only (i.e input-is-10x flag is True), line count for each bam shard',
                        default=DEFAULT_LINE_COUNT)
    parser.add_argument('--track-abundance', action='store_true',
                        help='track k-mer abundances in the generated signature (default: False)')
    parser.add_argument('--scaled', type=float, default=0,
                        help='choose number of hashes as 1 in FRACTION of input k-mers')
    parser.add_argument('--seed', type=int,
                        help='seed used by MurmurHash (default: 42)',
                        default=DEFAULT_SEED)
    parser.add_argument('--randomize', action='store_true',
                        help='shuffle the list of input filenames randomly')
    parser.add_argument('--license', default='CC0', type=str,
                        help='signature license. Currently only CC0 is supported.')
    parser.add_argument('--rename-10x-barcodes', type=str,
                        help="Tab-separated file mapping 10x barcode name "
                        "to new name, e.g. with channel or cell "
                        "annotation label", required=False)
    parser.add_argument('--barcodes-file', type=str,
                        help="Barcodes file if the input is unfiltered 10x bam file", required=False)

def compute(filenames=None, check_sequence=False, ksizes=(21, 31, 51), dna=True, dayhoff=False,
            singleton=False, count_valid_reads=0, barcodes_file=None, line_count=DEFAULT_LINE_COUNT,
            rename_10x_barcodes=None, write_barcode_meta_csv=None, save_fastas=None,
            email='', scaled=10000, force=False, output=None, num_hashes=500, protein=False,
            name_from_first=False, seed=42, input_is_protein=False, merge=None, quiet=False,
            track_abundance=False, randomize=False, license='CC0',
            input_is_10x=False, processes=2, **kwargs):
    """Compute the signature for one or more files.

    Use cases:
        sourmash compute multiseq.fa              => multiseq.fa.sig, etc.
        sourmash compute genome.fa --singleton    => genome.fa.sig
        sourmash compute file1.fa file2.fa -o file.sig
            => creates one output file file.sig, with one signature for each
               input file.
        sourmash compute file1.fa file2.fa --merge merged -o file.sig
            => creates one output file file.sig, with all sequences from
               file1.fa and file2.fa combined into one signature.
    """
    set_quiet(quiet)

    if license != 'CC0':
        error('error: sourmash only supports CC0-licensed signatures. sorry!')
        sys.exit(-1)

    if input_is_protein and dna:
        notify('WARNING: input is protein, turning off nucleotide hashing')
        dna = False
        protein = True

    if scaled:
        if scaled < 1:
            error('ERROR: --scaled value must be >= 1')
            sys.exit(-1)
        if scaled != round(scaled, 0):
            error('ERROR: --scaled value must be integer value')
            sys.exit(-1)
        if scaled >= 1e9:
            notify('WARNING: scaled value is nonsensical!? Continuing anyway.')

        if num_hashes != 0:
            notify('setting num_hashes to 0 because --scaled is set')
            num_hashes = 0
 
    notify('computing signatures for files: {}', ", ".join(filenames))

    if randomize:
        notify('randomizing file list because of --randomize')
        random.shuffle(filenames)

    notify('Computing signature for ksizes: {}', str(ksizes))
    num_sigs = 0
    if dna and protein:
        notify('Computing both nucleotide and protein signatures.')
        num_sigs = 2*len(ksizes)
    elif dna and dayhoff:
        notify('Computing both nucleotide and Dayhoff-encoded protein '
               'signatures.')
        num_sigs = 2*len(ksizes)
    elif dna:
        notify('Computing only nucleotide (and not protein) signatures.')
        num_sigs = len(ksizes)
    elif protein:
        notify('Computing only protein (and not nucleotide) signatures.')
        num_sigs = len(ksizes)
    elif dayhoff:
        notify('Computing only Dayhoff-encoded protein (and not nucleotide) '
               'signatures.')
        num_sigs = len(ksizes)

    if (protein or dayhoff) and not input_is_protein:
        bad_ksizes = [ str(k) for k in ksizes if k % 3 != 0 ]
        if bad_ksizes:
            error('protein ksizes must be divisible by 3, sorry!')
            error('bad ksizes: {}', ", ".join(bad_ksizes))
            sys.exit(-1)

    notify('Computing a total of {} signature(s).', num_sigs)

    if num_sigs == 0:
        error('...nothing to calculate!? Exiting!')
        sys.exit(-1)

    if merge and not output:
        error("must specify -o with --merge")
        sys.exit(-1)

    def make_minhashes():
        # one minhash for each ksize
        Elist = []
        for k in ksizes:
            if protein:
                E = MinHash(ksize=k, n=num_hashes,
                            is_protein=True,
                            dayhoff=False,
                            track_abundance=track_abundance,
                            scaled=scaled,
                            seed=seed)
                Elist.append(E)
            if dayhoff:
                E = MinHash(ksize=k, n=num_hashes,
                            is_protein=True,
                            dayhoff=True,
                            track_abundance=track_abundance,
                            scaled=scaled,
                            seed=seed)
                Elist.append(E)
            if dna:
                E = MinHash(ksize=k, n=num_hashes,
                            is_protein=False,
                            dayhoff=False,
                            track_abundance=track_abundance,
                            scaled=scaled,
                            seed=seed)
                Elist.append(E)
        return Elist

    def add_seq(Elist, seq, input_is_protein, check_sequence):
        for E in Elist:
            if input_is_protein:
                E.add_protein(seq)
            else:
                E.add_sequence(seq, not check_sequence)

    def build_siglist(Elist, filename, name=None):
        return [ sig.SourmashSignature(E, filename=filename,
                                       name=name) for E in Elist ]

    def save_siglist(siglist, output_fp, filename=None):
        # save!
        if output_fp:
            sigfile_name = output.name
            sig.save_signatures(siglist, output)
        else:
            if filename is None:
                raise Exception("internal error, filename is None")
            with open(filename, 'w') as fp:
                sigfile_name = filename
                sig.save_signatures(siglist, fp)
        notify(
            'saved signature(s) to {}. Note: signature license is CC0.',
            sigfile_name)

    if track_abundance:
        notify('Tracking abundance of input k-mers.')

    if not merge:
        if output:
            siglist = []

        for filename in filenames:
            sigfile = os.path.basename(filename) + '.sig'
            if not output and os.path.exists(sigfile) and not force:
                notify('skipping {} - already done', filename)
                continue

            if singleton:
                siglist = []
                for n, record in enumerate(screed.open(filename)):
                    # make minhashes for each sequence
                    Elist = make_minhashes()
                    add_seq(Elist, record.sequence,
                            input_is_protein, check_sequence)

                    siglist += build_siglist(Elist, filename, name=record.name)

                notify('calculated {} signatures for {} sequences in {}',
                       len(siglist), n + 1, filename)
            elif input_is_10x:

                # Initializing time
                startt = time.time()
                metadata = [
                    "--write-barcode-meta-csv", write_barcode_meta_csv] if write_barcode_meta_csv else ['', '']
                save_fastas = ["--save-fastas", save_fastas] if save_fastas else ['', '']
                barcodes_file = ["--barcodes-file", barcodes_file] if barcodes_file else ['', '']
                rename_10x_barcodes = \
                    ["--rename-10x-barcodes", rename_10x_barcodes] if rename_10x_barcodes else ['', '']

                bam_to_fasta_args = [
                    '--filename', filename,
                    '--min-umi-per-barcode', str(count_valid_reads),
                    '--processes', str(processes),
                    '--line-count', str(line_count),
                    barcodes_file[0], barcodes_file[1],
                    rename_10x_barcodes[0], rename_10x_barcodes[1],
                    save_fastas[0], save_fastas[1],
                    metadata[0], metadata[1]]
                bam_to_fasta_args = [arg for arg in bam_to_fasta_args if arg != '']

                fastas = bam2fasta_cli.convert(bam_to_fasta_args)
                # TODO move to bam2fasta since pool imap creates this empty lists and returns them
                fastas = [fasta for fasta in fastas if fasta != []]

                siglist = []
                for fasta in fastas:
                    for n, record in enumerate(screed.open(fasta)):
                        # make minhashes for each sequence
                        Elist = make_minhashes()
                        add_seq(Elist, record.sequence, input_is_protein, check_sequence)

                    siglist += build_siglist(Elist, fasta, name=record.name)

                    notify('calculated {} signatures for {} sequences in {}',
                           len(siglist), n + 1, fasta)

                notify("time taken to calculate signature records for 10x file is {:.5f} seconds",
                       time.time() - startt)
            else:
                # make minhashes for the whole file
                Elist = make_minhashes()

                # consume & calculate signatures
                notify('... reading sequences from {}', filename)
                name = None
                for n, record in enumerate(screed.open(filename)):
                    if n % 10000 == 0:
                        if n:
                            notify('\r...{} {}', filename, n, end='')
                        elif name_from_first:
                            name = record.name

                    add_seq(Elist, record.sequence,
                            input_is_protein, check_sequence)

                notify('...{} {} sequences', filename, n, end='')

                sigs = build_siglist(Elist, filename, name)
                if output:
                    siglist += sigs
                else:
                    siglist = sigs

                notify('calculated {} signatures for {} sequences in {}',
                       len(sigs), n + 1, filename)

            if not output:
                save_siglist(siglist, output, sigfile)

        if output:
            save_siglist(siglist, output, sigfile)
    else:                             # single name specified - combine all
        # make minhashes for the whole file
        Elist = make_minhashes()

        total_seq = 0
        for filename in filenames:
            # consume & calculate signatures
            notify('... reading sequences from {}', filename)

            for n, record in enumerate(screed.open(filename)):
                if n % 10000 == 0 and n:
                    notify('\r... {} {}', filename, n, end='')

                add_seq(Elist, record.sequence,
                        input_is_protein, check_sequence)
            notify('... {} {} sequences', filename, n + 1)

            total_seq += n + 1

        siglist = build_siglist(Elist, filename, name=merge)
        notify('calculated {} signatures for {} sequences taken from {} files',
               len(siglist), total_seq, len(filenames))

        # at end, save!
        save_siglist(siglist, output)
compute.add_args = compute_add_args
