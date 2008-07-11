# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
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

# Import from the Standard Library
from copy import deepcopy
from operator import itemgetter

# Import from itools
from itools.csv import Record, UniqueError, Table as TableFile
from itools.datatypes import DataType, is_datatype
from itools.datatypes import Integer, Enumerate, Date, Tokens
from itools.gettext import MSG
from itools.http import Forbidden
from itools.stl import stl
from itools.web import FormError, STLView

# Import from ikaaro
from base import DBObject
from file import File
from forms import AutoForm, get_default_widget, ReadOnlyWidget
from messages import *
from registry import register_object_class
from views import BrowseForm
from widgets import batch, table


###########################################################################
# Views
###########################################################################
class TableView(BrowseForm):

    access = 'is_allowed_to_view'
    tab_label = MSG(u'View')
    tab_icon = 'view.png'


    def get_namespace(self, model, context, query):
        namespace = {}

        # The input parameters
        start = query['batchstart']
        size = 50

        # The batch
        handler = model.handler
        total = handler.get_n_records()
        namespace['batch'] = batch(context.uri, start, size, total)

        # The table
        actions = []
        if total:
            ac = model.get_access_control()
            if ac.is_allowed_to_edit(context.user, model):
                actions = [('del_record_action', u'Remove', 'button_delete',
                            None)]

        fields = [('index', u'id')]
        widgets = self.get_widgets()
        for widget in widgets:
            fields.append((widget.name, getattr(widget, 'title', widget.name)))
        records = []

        for record in handler.get_records():
            id = record.id
            records.append({})
            records[-1]['id'] = str(id)
            records[-1]['checkbox'] = True
            # Fields
            records[-1]['index'] = id, ';edit_record_form?id=%s' % id
            for field, field_title in fields[1:]:
                value = handler.get_value(record, field)
                datatype = handler.get_datatype(field)

                multiple = getattr(datatype, 'multiple', False)
                is_tokens = is_datatype(datatype, Tokens)
                if multiple is True or is_tokens:
                    if multiple:
                        value.sort()
                    value_length = len(value)
                    if value_length > 0:
                        rmultiple = value_length > 1
                        value = value[0]
                    else:
                        rmultiple = False
                        value = None

                is_enumerate = getattr(datatype, 'is_enumerate', False)
                if is_enumerate:
                    records[-1][field] = datatype.get_value(value)
                else:
                    records[-1][field] = value

                if multiple is True or is_tokens:
                    records[-1][field] = (records[-1][field], rmultiple)
        # Sorting
        sortby = query['sortby']
        sortorder = query['sortorder']
        if sortby:
            reverse = (sortorder == 'down')
            records.sort(key=itemgetter(sortby[0]), reverse=reverse)

        records = records[start:start+size]
        for record in records:
            for field, field_title in fields[1:]:
                if isinstance(record[field], tuple):
                    if record[field][1] is True:
                        record[field] = '%s [...]' % record[field][0]
                    else:
                        record[field] = record[field][0]

        namespace['table'] = table(fields, records, [sortby], sortorder,
                                   actions)

        return namespace



class AddRecordForm(AutoForm):

    access = 'is_allowed_to_edit'
    tab_label = MSG(u'Add')
    tab_icon = 'new.png'

    form_title = MSG(u'Add a new record')
    form_action = ';add_record'
    submit_value = MSG(u'Add')
    submit_class = 'button_ok'


    def get_schema(self, model):
        return model.handler.schema


    def get_widgets(self, model):
        return model.get_form()


    def action(self, model, context, form):
        schema = self.get_schema(model)
        handler = model.handler
#       # check form
#       check_fields = {}
#       for name in schema:
#           datatype = handler.get_datatype(name)
#           if getattr(datatype, 'multiple', False) is True:
#               datatype = Multiple(type=datatype)
#           check_fields[name] = datatype

#       try:
#           form = self.check_form_input(model, check_fields)
#       except FormError:
#           context.message = MSG_MISSING_OR_INVALID
#           return

        record = {}
        for name in schema:
            datatype = handler.get_datatype(name)
            if getattr(datatype, 'multiple', False) is True:
                if is_datatype(datatype, Enumerate):
                    value = form[name]
                else: # textarea -> string
                    values = form[name]
                    values = values.splitlines()
                    value = []
                    for index in range(len(values)):
                        tmp = values[index].strip()
                        if tmp:
                            value.append(datatype.decode(tmp))
            else:
                value = form[name]
            record[name] = value
        try:
            handler.add_record(record)
            message = u'New record added.'
        except UniqueError, error:
            title = model.get_field_title(error.name)
            message = str(error) % (title, error.value)
        except ValueError, error:
            title = model.get_field_title(error.name)
            message = MSG(u'Error: $message')
            message = message.gettext(message=strerror)

        context.message = message


class EditRecordForm(AutoForm):

    access = 'is_allowed_to_edit'

    form_action = ';edit_record'
    submit_value = u'Change'
    submit_class = 'button_ok'


    def edit_record_form(self, context):
        # Get the record
        id = context.get_form_value('id', type=Integer)
        record = self.handler.get_record(id)

        form_hidden = [{'name': 'id', 'value': id}]
        return generate_form(context, u'Edit record %s' % id,
            self.handler.schema, self.get_form(), form_action, form_hidden,
            method=record.get_value)


    def action(self, model, context):
        id = context.get_form_value('id', None, type=Integer)
        if id is None:
            return context.come_back(MSG_MISSING_OR_INVALID)

        # check form
        check_fields = {}
        for widget in self.get_form():
            datatype = self.handler.get_datatype(widget.name)
            if getattr(datatype, 'multiple', False) is True:
                datatype = Multiple(type=datatype)
            check_fields[widget.name] = datatype

        try:
            form = context.check_form_input(check_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID,
                                     keep=context.get_form_keys())

        # Get the record
        record = {}
        for widget in self.get_form():
            datatype = self.handler.get_datatype(widget.name)
            if getattr(datatype, 'multiple', False) is True:
                if is_datatype(datatype, Enumerate):
                    value = form[widget.name]
                else: # textarea -> string
                    values = form[widget.name]
                    values = values.splitlines()
                    value = []
                    for index in range(len(values)):
                        tmp = values[index].strip()
                        if tmp:
                            value.append(datatype.decode(tmp))
            else:
                value = form[widget.name]
            record[widget.name] = value

        try:
            self.handler.update_record(id, **record)
            message = MSG_CHANGES_SAVED
            return context.come_back(message, goto=';view')
        except UniqueError, error:
            title = self.get_field_title(error.name)
            message = str(error) % (title, error.value)
        except ValueError, error:
            title = self.get_field_title(error.name)
            message = MSG(u'Error: $message')
            message = message.gettext(message=strerror)

        goto = context.uri.resolve2('../;edit_record_form')
        return context.come_back(message, goto=goto, keep=['id'])




###########################################################################
# Model
###########################################################################
class Multiple(DataType):

    def decode(self, data):
        if isinstance(data, list):
            lines = data
        else:
            lines = data.splitlines()

        return [ self.type.decode(x) for x in lines ]



class Table(File):

    class_id = 'table'
    class_version = '20071216'
    class_title = MSG(u'Table')
    class_views = [['view'],
                   ['add_record'],
                   ['edit_metadata'],
                   ['history']]
    class_handler = TableFile
    record_class = Record
    form = []

    def GET(self, context):
        method = self.get_firstview()
        # Check access
        if method is None:
            raise Forbidden
        # Redirect
        return context.uri.resolve2(';%s' % method)


    @classmethod
    def get_form(cls):
        if cls.form != []:
            return cls.form
        form = []
        for key, value in cls.class_handler.schema.items():
            widget = get_default_widget(value)
            form.append(widget(key))
        return form


    #########################################################################
    # User Interface
    #########################################################################
    new_instance = DBObject.new_instance


    @classmethod
    def get_field_title(cls, name):
        for widget in cls.form:
            if widget.name == name:
                return  getattr(widget, 'title', name)
        return name


    #########################################################################
    # User Interface
    #########################################################################
    edit_form__access__ = False
    view = TableView()


    #########################################################################
    # View
    del_record_action__access__ = 'is_allowed_to_edit'
    def del_record_action(self, context):
        ids = context.get_form_values('ids', type=Integer)
        for id in ids:
            self.handler.del_record(id)

        message = u'Record deleted.'
        return context.come_back(message)


    #########################################################################
    # Add, Edit
    add_record = AddRecordForm()
    edit_record = EditRecordForm()



###########################################################################
# Register
###########################################################################
register_object_class(Table)
