# pylint: disable=attribute-defined-outside-init
""" Functions for loading and saving files to disk. """
import semver as SemVer
from box import Box

import marshmallow.class_registry

from mlspeclib.io import IO
from mlspeclib.mlschema import MLSchema
from mlspeclib.mlschemaenums import MLSchemaTypes
from mlspeclib.helpers import check_and_return_schema_type_by_string, \
                              recursive_fromkeys, \
                              convert_yaml_to_dict

class MLObject(Box):
    """ Contains all the fields loaded from an MLSpec, and validated against the MLSchema. Also
    provides load and save functions."""
    def set_type(self, schema_version, schema_type, \
                       schema=None, schema_object=None):
        """ Used primarily after MLObject instantiation to set the schema_version and
        schema_type. Does verification of both fields and then loads a stub object
        with all fields set to 'None' except schema_version and schema_type."""

        try:
            SemVer.parse(schema_version)
            self.__schema_version = schema_version
        except ValueError:
            raise ValueError(f"'{schema_version}' is not a valid semantic version.")
        except TypeError:
            raise ValueError(f"'{schema_version}' is not a valid semantic version.")

        self.__schema_type = check_and_return_schema_type_by_string(schema_type)
        self.__schema = schema
        self.__schema_object = schema_object

        self.create_stub_object()
        self.schema_version = self.get_schema_version()
        self.schema_type = self.get_schema_type().name.lower()


    def set_semver_and_type(self, schema_version=None, schema_type: MLSchemaTypes = None, \
                            contents_as_dict=None):
        """ Mostly internal function used to set variables for version and type. Should only \
            use rarely - if you use this separate from loading an object, you can get out \
            of sync."""

        if (schema_version is not None and schema_type is not None) and \
           (contents_as_dict is not None):
            raise Warning("Semantic version + schema type and a dictionary were \
                           provided as the version & schema type, defaulting to \
                           using the content from the dictionary.")

        if contents_as_dict is not None:
            try:
                schema_version = contents_as_dict['schema_version']
            except KeyError:
                raise KeyError("No field named 'schema_version' found at the top level of data.")

            try:
                schema_type = contents_as_dict['schema_type']
            except KeyError:
                raise KeyError("No field named 'schema_type' found at the top level of data.")


    def create_stub_object(self):
        """ Creates a stub dictionary based on the schema with all values set to None.
        We do this because our goal is to prevent (eventually) creation of new attributes
        directly by users - only allowing them to use what we already provide to them
        to keep the schema in sync with the object."""

        MLSchema.populate_registry()
        version_number = self.get_schema_version()
        schema_name = MLSchema.return_schema_name(version_number, self.get_schema_type().name)
        object_schema = marshmallow.class_registry.get_class(schema_name)
        self.__schema = object_schema()
        self.__schema_object = None
        these_fields = object_schema().fields
        this_key_dict = recursive_fromkeys(these_fields)
        self.merge_update(this_key_dict)

    def validate(self):
        """ Returns an array of errors after validating against the assigned
        schema. Each error is an array with the message at the 0-th index."""
        return self.get_schema().validate(self.dict_without_internal_variables())

    def save(self, file_path: str):
        """ Copies all internal data to an MLSchema, which it then
        uses to validate, and saves to disk. Returns True on success,
        or False and an array of errors if it fails schema validation. """
        errors = self.validate()
        file_write_success = False
        if len(errors) == 0:
            IO.write_content_to_path(file_path, self.dict_without_internal_variables())
            file_write_success = True
        return (file_write_success, errors)

    @staticmethod
    def create_object_from_file(file_path: str):
        """ Creates an MLObject based on a file path. File must be valid yaml."""
        ml_content_from_disk = IO.get_content_from_path(file_path)
        return MLObject.create_object_from_string(ml_content_from_disk)

    @staticmethod
    def create_object_from_string(file_contents: str):
        """ Creates an MLObject based on a string. String must be valid yaml.
        Returns Tuple MLObject and list of errors."""
        contents_as_dict = convert_yaml_to_dict(file_contents)

        # if (self.schema_type() is not None and self.version() is not None):
        #     schema_string = self.schema_type().name.lower()
        #     if (self.version() != contents_as_dict['schema_version'] or \
        #         schema_string != contents_as_dict['schema_type']):
        #         raise AttributeError("""The schema version and schema type were not in sync
        #     with those provided in the data. Rather than guessing which you want to use, we
        #     are throwing this error:
        #     Version Expected: %s
        #     Version Provided: %s
        #     Schema Type Expected: %s
        #     Schema Type Provided: %s """ % (self.version(), contents_as_dict['schema_version'], \
        #                                 schema_string, contents_as_dict['schema_type']))

        ml_object = MLObject()
        ml_object.set_type(schema_version=contents_as_dict["schema_version"], \
                                 schema_type=contents_as_dict['schema_type'])
        MLObject.update_tree(ml_object, contents_as_dict)
        errors = ml_object.validate()
        return ml_object, errors


    @staticmethod
    def update_tree(object_to_update, content):
        """ Updates the box tree to the content provided, and does a validation at the end. """
        for key in object_to_update:
            if isinstance(object_to_update[key], Box):
                MLObject.update_tree(object_to_update[key], content[key])

        object_to_update.merge_update(content)
        return object_to_update


    def dict_without_internal_variables(self):
        """ Returns a dict of all values on MLObject minus any with the prefix '_MLObject'
        (which are only for internal use). This allows us to validate on the whole dict."""
        return {k: v for k, v in self.to_dict().items() if not k.startswith('_MLObject')}

    # Simple getter functions with a prefix so that it's unlikely to be hidden
    # by values in the schema.

    # pylint: disable=missing-function-docstring
    def get_schema_version(self):
        return self.__schema_version

    # pylint: disable=missing-function-docstring
    def get_schema_type(self):
        return self.__schema_type

    # pylint: disable=missing-function-docstring
    def get_schema(self):
        return self.__schema

    # pylint: disable=missing-function-docstring
    def get_schema_object(self):
        return self.__schema_object