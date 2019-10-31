from enum import Enum

from ._lowlevel import lib


class HashFunctions(Enum):
    murmur64_DNA = lib.HASH_FUNCTIONS_MURMUR64_DNA
    murmur64_protein = lib.HASH_FUNCTIONS_MURMUR64_PROTEIN
    murmur64_dayhoff = lib.HASH_FUNCTIONS_MURMUR64_DAYHOFF

    @classmethod
    def from_string(cls, hash_str):
        if hash_str == "0.murmur64_DNA":
            return cls.murmur64_DNA
        elif hash_str == "0.murmur64_protein":
            return cls.murmur64_protein
        elif hash_str == "0.murmur64_dayhoff":
            return cls.murmur64_dayhoff
        else:
            raise Exception("unknown molecule type: {}".format(hash_str))


def hashfunction_from_string(hash_str):
    return HashFunctions.from_string(hash_str)
