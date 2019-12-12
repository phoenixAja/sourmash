"An Abstract Base Class for collections of signatures."

from abc import ABCMeta, abstractmethod
from collections import namedtuple

# compatible with Python 2 *and* 3:
ABC = ABCMeta("ABC", (object,), {"__slots__": ()})


class Index(ABC):
    @abstractmethod
    def signatures(self):
        "Return an iterator over all signatures in the Index object."

    @abstractmethod
    def search(self, signature, *args, **kwargs):
        """ """

    @abstractmethod
    def gather(self, signature, *args, **kwargs):
        """ """

    @abstractmethod
    def insert(self, node):
        """ """

    @abstractmethod
    def save(self, path, storage=None, sparseness=0.0, structure_only=False):
        """ """

    @classmethod
    @abstractmethod
    def load(cls, location, leaf_loader=None, storage=None, print_version_warning=True):
        """ """


class LinearIndex(Index):
    def __init__(self, _signatures=None, filename=None):
        self._signatures = []
        if _signatures:
            self._signatures = list(_signatures)
        self.filename = filename

    def signatures(self):
        return iter(self._signatures)

    def __len__(self):
        return len(self._signatures)

    def insert(self, node):
        self._signatures.append(node)

    def find(self, search_fn, *args, **kwargs):
        matches = []

        for node in self.signatures():
            if search_fn(node, *args):
                matches.append(node)
        return matches

    def search(self, query, *args, **kwargs):
        """@@

        Note, the "best only" hint is ignored by LinearIndex.
        """

        # check arguments
        if 'threshold' not in kwargs:
            raise TypeError("'search' requires 'threshold'")
        threshold = kwargs['threshold']

        do_containment = kwargs.get('do_containment', False)
        ignore_abundance = kwargs.get('ignore_abundance', False)

        # configure search - containment? ignore abundance?
        if do_containment:
            query_match = lambda x: query.contained_by(x, downsample=True)
        else:
            query_match = lambda x: query.similarity(
                x, downsample=True, ignore_abundance=ignore_abundance)

        # do the actual search:
        matches = []

        for ss in self.signatures():
            similarity = query_match(ss)
            if similarity >= threshold:
                # @CTB: check duplicates via md5sum - here or later?
                matches.append((similarity, ss, self.filename))

        # sort!
        matches.sort(key=lambda x: -x[0])
        return matches

    def gather(self, query, *args, **kwargs):
        "Return the best containment in the list."
        results = []
        for ss in self.signatures():
            cont = query.minhash.containment_ignore_maxhash(ss.minhash)
            if cont:
                results.append((cont, ss, self.filename))

        results.sort(reverse=True)        # CTB: sort on ss.name() too?

        return results

    def save(self, path):
        from .signature import save_signatures
        with open(path, 'wt') as fp:
            save_signatures(self.signatures(), fp)

    @classmethod
    def load(cls, location):
        from .signature import load_signatures
        si = load_signatures(location)

        lidx = LinearIndex(si, filename=location)
        return lidx
