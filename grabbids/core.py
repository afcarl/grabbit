import json
import os
import re
from collections import defaultdict, OrderedDict
from six import string_types
from os.path import join

__all__ = ['File', 'Entity', 'Structure']



# Utils for creating trees and converting them to plain dicts
def tree(): return defaultdict(tree)


def to_dict(tree):
    """
    turns a tree into a dictionary for printing purposes
    """
    if not isinstance(tree, dict):
        return tree
    return {k: to_dict(tree[k]) for k in tree}

def get_flattened_values(d):
    vals = []
    for k, v in d.items():
        if isinstance(v, dict):
            vals.extend(get_flattened_values(v))
        else:
            vals.append(v)
    return vals

class File(object):

    def __init__(self, filename):
        """
        Represents a single file.
        """
        # if not exists(filename):
        #     raise OSError("File '%s' can't be found." % filename)
        self.name = filename
        self.entities = {}


class Entity(object):

    def __init__(self, name, pattern, mandatory=False, missing_value=None,
                 directory=None):
        """
        Represents a single entity defined in the JSON specification.
        Args:
            name (str): The name of the entity (e.g., 'subject', 'run', etc.)
            pattern (str): A regex pattern used to match against file names.
                Must define at least one group, and only the first group is
                kept as the match.
        """
        self.name = name
        self.pattern = pattern
        self.mandatory = mandatory
        if missing_value is None:
            missing_value = self.name
        self.missing_value = missing_value
        self.directory = directory
        self.files = {}
        self.regex = re.compile(pattern)

    def matches(self, f):
        """
        Run a regex search against the passed file and update the entity/file
        mappings.
        Args:
            f (File): The File instance to match against.
        """
        m = self.regex.search(f.name)
        if m is not None:
            val = m.group(1)
            f.entities[self.name] = val

    def add_file(self, filename, value):
        """ Adds the specified filename to tracking. """
        self.files[filename] = value

    def unique(self):
        return list(set(self.files.values()))

    def count(self, files=False):
        return len(self.files) if files else len(self.unique())


class Structure(object):

    def __init__(self, specification, path):
        """
        A container for all the files and metadata found at the specified path.
        Args:
            specification (str): The path to the JSON specification file
                that defines the entities and paths for the current structure.
            path (str): The root path of the structure.
        """
        self.spec = json.load(open(specification, 'r'))
        self.path = path
        self.entities = OrderedDict()
        self.files = {}
        self.mandatory = set()

        # Set up the entities we need to track
        for e in self.spec['entities']:
            ent = Entity(**e)
            if ent.mandatory:
                self.mandatory.add(ent)
            self.entities[ent.name] = ent

        # Loop over all files
        for root, directories, filenames in os.walk(path):
            for f in filenames:
                f = File(f)
                for e in self.entities.values():
                    e.matches(f)
                fe = f.entities.keys()
                # Only keep Files that match at least one Entity, and all
                # mandatory Entities
                if fe and not (self.mandatory - set(fe)):
                    self.files[f.name] = f
                    # Bind the File to all of the matching entities
                    for ent, val in f.entities.items():
                        self.entities[ent].add_file(f.name, val)

    def get(self, entities, return_type='file', filter=None, extensions=None,
            hierarchy=None, flatten=False):
        """
        Retrieve files and/or metadata from the current Structure.
        Args:
            entities (str, iterable): One or more entities to retrieve data
                for. Only files that match at least one of the passed entity
                names will be returned.
            return_type (str): What to return. At present, only 'file' works.
            filter (dict): A dictionary of optional key/values to filter the
                entities on. Keys are entity names, values are regexes to
                filter on. For example, passing filter={ 'subject': 'sub-[12]'}
                would return only files that match the first two subjects.
            extensions (str, list): One or more file extensions to filter on.
                Files with any other extensions will be excluded.
        Returns:
            A nested dictionary, with the levels of the hierarchy defined
            in a json spec file (currently using the "result" key).
        """
        if isinstance(entities, string_types):
            entities = [entities]

        result = tree()

        if hierarchy is None:
            hierarchy = self.spec.get('hierarchy', self.entities.keys())

        if extensions is not None:
            extensions = '(' + '|'.join(extensions) + ')$'

        for filename, file in self.files.items():

            include = True
            _call = 'result'
            for i, ent in enumerate(hierarchy):
                missing_value = self.entities[ent].missing_value
                key = file.entities.get(ent, missing_value)
                _call += '["%s"]' % key

                # Filter on entity values
                if filter is not None and ent in filter:
                    if re.search(filter[ent], key) is None:
                        include = False
                        break

                # Filter on extensions
                if extensions is not None:
                    if re.search(extensions, filename) is None:
                        include = False
                        break

            if include:
                _call += ' = "%s"' % (filename)
                exec(_call)

        result = to_dict(result)
        return get_flattened_values(result) if flatten else result

    def unique(self, entity):
        """
        Return a list of unique values for the named entity.
        Args:
            entity (str): The name of the entity to retrieve unique values of.
        """
        return self.entities[entity].unique()

    def count(self, entity, files=False):
        """
        Return the count of unique values or files for the named entity.
        Args:
            entity (str): The name of the entity.
            files (bool): If True, counts the number of filenames that contain
                at least one value of the entity, rather than the number of
                unique values of the entity.
        """
        return self.entities[entity].count(files)
