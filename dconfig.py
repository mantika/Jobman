
#
#
# Utility
#
#

class Config (object):
    """A class to store experiment configurations.

    Configuration variables are stored in class instance __dict__.  This class
    ensures that keys are alphanumeric strings, and that values can be rebuilt
    from their representations.

    It can be serialized to/from a python file.
    
    """
    def __init__(self, __dict__=None, **kwargs):
        if __dict__:
            Config.__checkkeys__(*__dict__.keys())
            self.__dict__.update(__dict__)
        if kwargs:
            Config.__checkkeys__(*kwargs.keys())
            self.__dict__.update(kwargs)

    def __setattr__(self, attr, value):
        Config.__checkkeys__(attr)
        self.__dict__[attr] = value

    def __hash__(self):
        """Compute a hash string from a dict, based on items().

        @type dct: dict of hashable keys and values.
        @param dct: compute the hash of this dict

        @rtype: string

        """
        items = list(self.items())
        items.sort()
        return hash(repr(items))

    def keys(self):
        return self.__dict__.keys()

    def items(self):
        return self.__dict__.items()

    def update(self, dct):
        Config.__checkkeys__(*dct.keys())
        self.__dict__.update(dct)

    def save(self, filename):
        """Write a python file as a way of serializing a dictionary

        @type dct: dict
        @param dct: the input dictionary

        @type filename: string
        @param filename: filename to open (overwrite) to save dictionary contents

        @return None

        """
        f = open(filename, 'w')
        for key, val in self.items():
            Config.__checkkeys__(key) # should never raise... illegal keys are not
            # supposed to ever get into the dictionary
            repr_val = repr(val)
            assert val == eval(repr_val)
            print >> f, key, '=', repr_val
        f.close()

    def update_fromfile(self, filename):
        """Read the local variables from a python file

        @type filename: string, filename suitable for __import__()
        @param filename: a file whose module variables will be returned as a
        dictionary

        @rtype: dict
        @return: the local variables of the imported filename

        @note:
        This implementation silently ignores all module symbols that don't meet
        the standards enforced by L{Config.__checkkeys__}. This is meant to
        ignore module special variables.

        """
        #m = __import__(filename) #major security problem, or feature?
        f = open(filename)
        for line in f:
            line = line[:-1] #trim the '\n'
            tokens = line.split(' ')
            key = tokens[0]
            assert '=' == tokens[1]
            repr_val = ' '.join(tokens[2:])
            val = eval(repr_val)
            setattr(self, key, val)

    @staticmethod
    def __checkkeys__(*args):
        conf = Config()
        for k in args:
            #must be string
            if type(k) != str:
                raise KeyError(k)
            #mustn't be part of Config class interface
            if hasattr(conf, k):
                raise KeyError(k)
            #all alphanumeric
            for c in k:
                if c not in ('abcdefghijklmnopqrstuvwxyz'
                        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                        '_0123456789'):
                    raise KeyError(k)
            #no symbols that look like reserved symbols
            if k[:2]=='__' and k[-2:]=='__' and len(k)>4:
                raise KeyError(k)

def load(*filenames):
    rval = Config()
    for filename in filenames:
        rval.update_fromfile(filename)
    return rval
