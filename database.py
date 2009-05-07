# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import from the Standard Library
from subprocess import call, PIPE

# Import from itools
from itools.core import get_pipe
from itools.handlers import ROGitDatabase, GitDatabase, make_git_database
from itools.web import get_context
from itools.xapian import Catalog, make_catalog

# Import from ikaaro
from folder import Folder
from registry import get_register_fields



class ReadOnlyDatabase(ROGitDatabase):

    def __init__(self, target, cache_size):
        self.path = '%s/database' % target

        # Database/Catalog
        ROGitDatabase.__init__(self, self.path, cache_size)
        self.catalog = Catalog('%s/catalog' % target, get_register_fields(),
                               read_only=True)



class Database(GitDatabase):
    """Adds a Git archive to the itools database.
    """

    def __init__(self, target, cache_size):
        # Database/Catalog
        path = '%s/database' % target
        GitDatabase.__init__(self, path, cache_size)
        self.catalog = Catalog('%s/catalog' % target, get_register_fields())

        # Events
        self.resources_added = {}
        self.resources_changed = {}
        self.resources_removed = set()


    #######################################################################
    # Events API
    #######################################################################
    def remove_resource(self, resource):
        resources_removed = self.resources_removed
        resources_added = self.resources_added
        resources_changed = self.resources_changed

        if isinstance(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.get_canonical_path())
                if path in resources_added:
                    del resources_added[path]
                if path in resources_changed:
                    del resources_changed[path]
                resources_removed.add(path)
        else:
            path = str(resource.get_canonical_path())
            if path in resources_added:
                del resources_added[path]
            if path in resources_changed:
                del resources_changed[path]
            resources_removed.add(path)


    def add_resource(self, resource):
        resources_added = self.resources_added

        # Catalog
        if isinstance(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.get_canonical_path())
                resources_added[path] = x
        else:
            path = str(resource.get_canonical_path())
            resources_added[path] = resource


    def change_resource(self, resource):
        path = str(resource.get_canonical_path())
        if path in self.resources_removed:
            raise ValueError, 'XXX'
        if path in self.resources_added:
            return
        self.resources_changed[path] = resource


    #######################################################################
    # Transactions API
    #######################################################################
    def _before_commit(self):
        catalog = self.catalog
        documents_to_index = []

        # Removed
        for path in self.resources_removed:
            catalog.unindex_document(path)
        self.resources_removed.clear()

        # Added
        for path, resource in self.resources_added.iteritems():
            values = resource._get_catalog_values()
            documents_to_index.append((resource, values))
        self.resources_added.clear()

        # Changed
        for path, resource in self.resources_changed.iteritems():
            catalog.unindex_document(path)
            values = resource._get_catalog_values()
            documents_to_index.append((resource, values))
        self.resources_changed.clear()

        # Find out commit author & message
        git_author = 'nobody <>'
        git_message = 'no comment'
        context = get_context()
        if context is not None:
            # Author
            user = context.user
            if user is not None:
                email = user.get_property('email')
                git_author = '%s <%s>' % (user.name, email)
            # Message
            try:
                git_message = getattr(context, 'git_message')
            except AttributeError:
                pass
            else:
                git_message = git_message.encode('utf-8')

        # Ok
        return git_author, git_message, documents_to_index


    def _save_changes(self, data):
        git_author, git_message, documents_to_index = data

        # (1) Save filesystem changes
        GitDatabase._save_changes(self, (git_author, git_message))

        # (2) Catalog
        catalog = self.catalog
        for resource, values in documents_to_index:
            values = resource.get_catalog_values(values)
            catalog.index_document(values)
        catalog.save_changes()


    def _abort_changes(self):
        GitDatabase._abort_changes(self)

        # Catalog
        self.catalog.abort_changes()

        # Clear events
        self.resources_removed.clear()
        self.resources_added.clear()
        self.resources_changed.clear()



def make_database(target):
    size = 5000
    # GitDatabase
    path = '%s/database' % target
    make_git_database(path, size)
    # The catalog
    make_catalog('%s/catalog' % target, get_register_fields())
    # Ok
    return Database(target, size)


def get_database(path, cache_size, read_only=False):
    if read_only is True:
        return ReadOnlyDatabase(path, cache_size)

    return Database(path, cache_size)


def check_database(target):
    """This function checks whether the database is in a consisitent state,
    this is to say whether a transaction was not brutally aborted and left
    the working directory with changes not committed.

    This is meant to be used by scripts, like 'icms-start.py'
    """
    cwd = '%s/database' % target

    # Check modifications to the working tree not yet in the index.
    command = ['git', 'ls-files', '-m', '-d', '-o']
    data1 = get_pipe(command, cwd=cwd).read()

    # Check changes in the index not yet committed.
    command = ['git', 'diff-index', 'HEAD', '--name-only']
    data2 = get_pipe(command, cwd=cwd).read()

    # Everything looks fine
    if len(data1) == 0 and len(data2) == 0:
        return True

    # Something went wrong
    print 'The database is not in a consistent state.  Fix it manually with'
    print 'the help of Git:'
    print
    print '  $ cd %s/database' % target
    print '  $ git clean -fxd'
    print '  $ git checkout -f'
    print
    return False