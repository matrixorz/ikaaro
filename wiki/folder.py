# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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

# Import from itools
from itools.datatypes import Unicode

# Import from ikaaro
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro.registry import register_object_class
from page import WikiPage


class WikiFolder(Folder):

    class_id = 'WikiFolder'
    class_version = '20061229'
    class_title = u"Wiki"
    class_description = u"Container for a wiki"
    class_icon16 = 'images/WikiFolder16.png'
    class_icon48 = 'images/WikiFolder48.png'
    class_views = [['view'],
                   ['browse_content?mode=list',
                    'browse_content?mode=thumbnails',
                    'browse_content?mode=image'],
                   ['new_resource_form'],
                   ['edit_metadata_form'],
                   ['last_changes']]

    __fixed_handlers__ = ['FrontPage']


    @classmethod
    def _make_object(cls, folder, name):
        Folder._make_object.im_func(cls, folder, name)
        # FrontPage
        kw = {'dc:title': {'en': u"Front Page"}}
        metadata = WikiPage.build_metadata(**kw)
        folder.set_handler('%s/FrontPage.metadata' % name, metadata)


    def get_document_types(self):
        return [WikiPage, File]


    #######################################################################
    # User interface
    #######################################################################
    def GET(self, context):
        return context.uri.resolve2('FrontPage')


    view__access__ = 'is_allowed_to_view'
    view__label__ = u'View'
    def view(self, context):
        if context.has_form_value('message'):
            message = context.get_form_value('message', type=Unicode)
            return context.come_back(message, goto='FrontPage')

        return context.uri.resolve('FrontPage')


###########################################################################
# Register
###########################################################################
register_object_class(WikiFolder)
