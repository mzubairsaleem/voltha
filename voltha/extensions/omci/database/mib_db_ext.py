#
# Copyright 2018 the original author or authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from mib_db_api import *
from voltha.protos.omci_mib_db_pb2 import MibInstanceData, MibClassData, \
    MibDeviceData, MibAttributeData
from voltha.extensions.omci.omci_entities import *
from scapy.fields import StrField


class MibDbExternal(MibDbApi):
    """
    A persistent external OpenOMCI MIB Database
    """
    CURRENT_VERSION = 1                       # VOLTHA v1.3.0 release

    _TIME_FORMAT = '%Y%m%d-%H%M%S.%f'

    # Paths from root proxy
    MIB_PATH = '/omci_mibs'
    DEVICE_PATH = MIB_PATH + '/{}'            # .format(device_id)

    # Classes, Instances, and Attributes as lists from root proxy
    CLASSES_PATH = DEVICE_PATH + '/classes'                               # .format(device_id)
    INSTANCES_PATH = DEVICE_PATH +'/classes/{}/instances'                 # .format(device_id, class_id)
    ATTRIBUTES_PATH = DEVICE_PATH + '/classes/{}/instances/{}/attributes'  # .format(device_id, class_id, instance_id)

    # Single Class, Instance, and Attribute as objects from device proxy
    CLASS_PATH = '/classes/{}'                                 # .format(class_id)
    INSTANCE_PATH = '/classes/{}/instances/{}'                 # .format(class_id, instance_id)
    ATTRIBUTE_PATH = '/classes/{}/instances/{}/attributes/{}'  # .format(class_id, instance_id
                                                               #         attribute_name)

    def __init__(self, omci_agent):
        """
        Class initializer
        :param omci_agent: (OpenOMCIAgent) OpenOMCI Agent
        """
        super(MibDbExternal, self).__init__(omci_agent)
        self._core = omci_agent.core

    def start(self):
        """
        Start up/restore the database
        """
        self.log.debug('start')

        if not self._started:
            super(MibDbExternal, self).start()
            root_proxy = self._core.get_proxy('/')

            try:
                base = root_proxy.get(MibDbExternal.MIB_PATH)
                self.log.info('db-exists', num_devices=len(base))

            except Exception as e:
                self.log.exception('start-failure', e=e)
                raise

    def stop(self):
        """
        Start up the database
        """
        self.log.debug('stop')

        if self._started:
            super(MibDbExternal, self).stop()
            # TODO: Delete this method if nothing else is done except calling the base class

    def _time_to_string(self, time):
        return time.strftime(MibDbExternal._TIME_FORMAT) if time is not None else ''

    def _string_to_time(self, time):
        return datetime.strptime(time, MibDbExternal._TIME_FORMAT) if len(time) else None

    def _attribute_to_string(self, device_id, class_id, attr_name, value):
        """
        Convert an ME's attribute value to string representation

        :param device_id: (str) ONU Device ID
        :param class_id: (int) Class ID
        :param attr_name: (str) Attribute Name (see EntityClasses)
        :param value: (various) Attribute Value

        :return: (str) String representation of the value
        :raises KeyError: Device, Class ID, or Attribute does not exist
        """
        try:
            me_map = self._omci_agent.get_device(device_id).me_map
            entity = me_map[class_id]
            attr_index = entity.attribute_name_to_index_map[attr_name]
            eca = entity.attributes[attr_index]
            field = eca.field

            if isinstance(field, StrFixedLenField):
                #  For StrFixedLenField, value is an str already (or possibly JSON encoded object)
                if hasattr(value, 'to_json'):
                    str_value = value.to_json()
                else:
                    str_value = str(value)

            elif isinstance(field, (StrField, MACField, IPField)):
                #  For StrField, value is an str already
                #  For MACField, value is a string in ':' delimited form
                #  For IPField, value is a string in '.' delimited form
                str_value = str(value)

            elif isinstance(field, (ByteField, ShortField, IntField, LongField)):
                #  For ByteField, ShortField, IntField, and LongField value is an int
                str_value = str(value)

            elif isinstance(field, BitField):
                # For BitField, value is a long
                #
                str_value = str(value)

            else:
                self.log.warning('default-conversion', type=type(field),
                                 class_id=class_id, attribute=attr_name, value=str(value))
                str_value = str(value)

            return str_value

        except Exception as e:
            self.log.exception('attr-to-string', device_id=device_id,
                               class_id=class_id, attr=attr_name,
                               value=value, e=e)
            raise

    def _string_to_attribute(self, device_id, class_id, attr_name, str_value):
        """
        Convert an ME's attribute value-string to its Scapy decode equivalent

        :param device_id: (str) ONU Device ID
        :param class_id: (int) Class ID
        :param attr_name: (str) Attribute Name (see EntityClasses)
        :param str_value: (str) Attribute Value in string form

        :return: (various) String representation of the value
        :raises KeyError: Device, Class ID, or Attribute does not exist
        """
        try:
            me_map = self._omci_agent.get_device(device_id).me_map
            entity = me_map[class_id]
            attr_index = entity.attribute_name_to_index_map[attr_name]
            eca = entity.attributes[attr_index]
            field = eca.field

            if isinstance(field, StrFixedLenField):
                from scapy.base_classes import Packet_metaclass
                if isinstance(field.default, Packet_metaclass) and \
                        hasattr(field.default, 'to_json'):
                    value = json.loads(str_value)
                else:
                    value = str_value

            elif isinstance(field, MACField):
                value = str_value

            elif isinstance(field, IPField):
                value = str_value

            elif isinstance(field, (ByteField, ShortField, IntField, LongField)):
                if str_value.lower() in ('true', 'false'):
                    str_value = '1' if str_value.lower() == 'true' else '0'
                value = int(str_value)

            elif isinstance(field, BitField):
                value = long(str_value)

            else:
                self.log.warning('default-conversion', type=type(field),
                                 class_id=class_id, attribute=attr_name, value=str_value)
                value = None

            return value

        except Exception as e:
            self.log.exception('attr-to-string', device_id=device_id,
                               class_id=class_id, attr=attr_name,
                               value=str_value, e=e)
            raise

    def add(self, device_id, overwrite=False):
        """
        Add a new ONU to database

        :param device_id: (str) Device ID of ONU to add
        :param overwrite: (bool) Overwrite existing entry if found.

        :raises KeyError: If device already exists and 'overwrite' is False
        """
        self.log.debug('add-device', device_id=device_id, overwrite=overwrite)

        now = datetime.utcnow()
        found = False
        root_proxy = self._core.get_proxy('/')
        data = MibDeviceData(device_id=device_id,
                             created=self._time_to_string(now),
                             last_sync_time='',
                             mib_data_sync=0,
                             version=MibDbExternal.CURRENT_VERSION)
        try:
            dev_proxy = self._device_proxy(device_id)
            found = True

            if not overwrite:
                # Device already exists
                raise KeyError('Device with ID {} already exists in MIB database'.
                               format(device_id))

            # Overwrite with new data
            data = dev_proxy.get('/', depth=0)
            self._root_proxy.update(MibDbExternal.DEVICE_PATH.format(device_id), data)
            self._modified = now

        except KeyError:
            if found:
                raise
            # Did not exist, add it now
            root_proxy.add(MibDbExternal.MIB_PATH, data)
            self._created = now
            self._modified = now

    def remove(self, device_id):
        """
        Remove an ONU from the database

        :param device_id: (str) Device ID of ONU to remove from database
        """
        self.log.debug('remove-device', device_id=device_id)

        if not self._started:
            raise DatabaseStateError('The Database is not currently active')

        if not isinstance(device_id, basestring):
            raise TypeError('Device ID should be an string')

        try:
            # self._root_proxy.get(MibDbExternal.DEVICE_PATH.format(device_id))
            self._root_proxy.remove(MibDbExternal.DEVICE_PATH.format(device_id))
            self._modified = datetime.utcnow()

        except KeyError:
            # Did not exists, which is not a failure
            pass

        except Exception as e:
            self.log.exception('remove-exception', device_id=device_id, e=e)
            raise

    @property
    def _root_proxy(self):
        return self._core.get_proxy('/')

    def _device_proxy(self, device_id):
        """
        Return a config proxy to the OMCI MIB_DB leaf for a given device

        :param device_id: (str) ONU Device ID
        :return: (ConfigProxy) Configuration proxy rooted at OMCI MIB DB
        :raises KeyError: If the device does not exist in the database
        """
        if not isinstance(device_id, basestring):
            raise TypeError('Device ID should be an string')

        if not self._started:
            raise DatabaseStateError('The Database is not currently active')

        return self._core.get_proxy(MibDbExternal.DEVICE_PATH.format(device_id))

    def _class_proxy(self, device_id, class_id, create=False):
        """
        Get a config proxy to a specific managed entity class
        :param device_id: (str) ONU Device ID
        :param class_id: (int) Class ID
        :param create: (bool) If true, create default instance (and class)
        :return: (ConfigProxy) Class configuration proxy

        :raises DatabaseStateError: If database is not started
        :raises KeyError: If Instance does not exist and 'create' is False
        """
        if not self._started:
            raise DatabaseStateError('The Database is not currently active')

        if not 0 <= class_id <= 0xFFFF:
            raise ValueError('class-id is 0..0xFFFF')

        fmt = MibDbExternal.DEVICE_PATH + MibDbExternal.CLASS_PATH
        path = fmt.format(device_id, class_id)

        try:
            return self._core.get_proxy(path)

        except KeyError:
            if not create:
                self.log.error('class-proxy-does-not-exist', device_id=device_id,
                               class_id=class_id)
                raise

        # Create class
        data = MibClassData(class_id=class_id)
        root_path = MibDbExternal.CLASSES_PATH.format(device_id)
        self._root_proxy.add(root_path, data)

        return self._core.get_proxy(path)

    def _instance_proxy(self, device_id, class_id, instance_id, create=False):
        """
        Get a config proxy to a specific managed entity instance
        :param device_id: (str) ONU Device ID
        :param class_id: (int) Class ID
        :param instance_id: (int) Instance ID
        :param create: (bool) If true, create default instance (and class)
        :return: (ConfigProxy) Instance configuration proxy

        :raises DatabaseStateError: If database is not started
        :raises KeyError: If Instance does not exist and 'create' is False
        """
        if not self._started:
            raise DatabaseStateError('The Database is not currently active')

        if not isinstance(device_id, basestring):
            raise TypeError('Device ID is a string')

        if not 0 <= class_id <= 0xFFFF:
            raise ValueError('class-id is 0..0xFFFF')

        if not 0 <= instance_id <= 0xFFFF:
            raise ValueError('instance-id is 0..0xFFFF')

        fmt = MibDbExternal.DEVICE_PATH + MibDbExternal.INSTANCE_PATH
        path = fmt.format(device_id, class_id, instance_id)

        try:
            return self._core.get_proxy(path)

        except KeyError:
            if not create:
                self.log.error('instance-proxy-does-not-exist', device_id=device_id,
                               class_id=class_id, instance_id=instance_id)
                raise

        # Create instance, first make sure class exists
        self._class_proxy(device_id, class_id, create=True)

        now = self._time_to_string(datetime.utcnow())
        data = MibInstanceData(instance_id=instance_id, created=now, modified=now)
        root_path = MibDbExternal.INSTANCES_PATH.format(device_id, class_id)
        self._root_proxy.add(root_path, data)

        return self._core.get_proxy(path)

    def on_mib_reset(self, device_id):
        """
        Reset/clear the database for a specific Device

        :param device_id: (str) ONU Device ID
        :raises DatabaseStateError: If the database is not enabled
        :raises KeyError: If the device does not exist in the database
        """
        self.log.debug('on-mib-reset', device_id=device_id)

        try:
            device_proxy = self._device_proxy(device_id)
            data = device_proxy.get(depth=2)

            # Wipe out any existing class IDs
            class_ids = [c.class_id for c in data.classes]

            if len(class_ids):
                for class_id in class_ids:
                    device_proxy.remove(MibDbExternal.CLASS_PATH.format(class_id))

            # Reset MIB Data Sync to zero
            now = datetime.utcnow()
            data = MibDeviceData(device_id=device_id,
                                 created=data.created,
                                 last_sync_time=data.last_sync_time,
                                 mib_data_sync=0,
                                 version=MibDbExternal.CURRENT_VERSION)
            # Update
            self._root_proxy.update(MibDbExternal.DEVICE_PATH.format(device_id),
                                    data)
            self._modified = now
            self.log.debug('mib-reset-complete', device_id=device_id)

        except Exception as e:
            self.log.exception('mib-reset-exception', device_id=device_id, e=e)
            raise

    def save_mib_data_sync(self, device_id, value):
        """
        Save the MIB Data Sync to the database in an easy location to access

        :param device_id: (str) ONU Device ID
        :param value: (int) Value to save
        """
        self.log.debug('save-mds', device_id=device_id, value=value)

        try:
            if not isinstance(value, int):
                raise TypeError('MIB Data Sync is an integer')

            if not 0 <= value <= 255:
                raise ValueError('Invalid MIB-data-sync value {}.  Must be 0..255'.
                                 format(value))
            device_proxy = self._device_proxy(device_id)
            data = device_proxy.get(depth=0)

            now = datetime.utcnow()
            data.mib_data_sync = value

            # Update
            self._root_proxy.update(MibDbExternal.DEVICE_PATH.format(device_id),
                                    data)
            self._modified = now
            self.log.debug('save-mds-complete', device_id=device_id)

        except Exception as e:
            self.log.exception('save-mds-exception', device_id=device_id, e=e)
            raise

    def get_mib_data_sync(self, device_id):
        """
        Get the MIB Data Sync value last saved to the database for a device

        :param device_id: (str) ONU Device ID
        :return: (int) The Value or None if not found
        """
        self.log.debug('get-mds', device_id=device_id)

        try:
            device_proxy = self._device_proxy(device_id)
            data = device_proxy.get(depth=0)
            return int(data.mib_data_sync)

        except KeyError:
            return None     # OMCI MIB_DB entry has not yet been created

        except Exception as e:
            self.log.exception('get-mds-exception', device_id=device_id, e=e)
            raise

    def save_last_sync(self, device_id, value):
        """
        Save the Last Sync time to the database in an easy location to access

        :param device_id: (str) ONU Device ID
        :param value: (DateTime) Value to save
        """
        self.log.debug('save-last-sync', device_id=device_id, time=str(value))

        try:
            if not isinstance(value, datetime):
                raise TypeError('Expected a datetime object, got {}'.
                                format(type(datetime)))

            device_proxy = self._device_proxy(device_id)
            data = device_proxy.get(depth=0)

            now = datetime.utcnow()
            data.last_sync_time = self._time_to_string(value)

            # Update
            self._root_proxy.update(MibDbExternal.DEVICE_PATH.format(device_id),
                                    data)
            self._modified = now
            self.log.debug('save-mds-complete', device_id=device_id)

        except Exception as e:
            self.log.exception('save-last-sync-exception', device_id=device_id, e=e)
            raise

    def get_last_sync(self, device_id):
        """
        Get the Last Sync Time saved to the database for a device

        :param device_id: (str) ONU Device ID
        :return: (int) The Value or None if not found
        """
        self.log.debug('get-last-sync', device_id=device_id)

        try:
            device_proxy = self._device_proxy(device_id)
            data = device_proxy.get(depth=0)
            return self._string_to_time(data.last_sync_time)

        except KeyError:
            return None     # OMCI MIB_DB entry has not yet been created

        except Exception as e:
            self.log.exception('get-last-sync-exception', e=e)
            raise

    def _add_new_class(self, device_id, class_id, instance_id, attributes):
        """
        Create an entry for a new class in the external database

        :param device_id: (str) ONU Device ID
        :param class_id: (int) ME Class ID
        :param instance_id: (int) ME Entity ID
        :param attributes: (dict) Attribute dictionary

        :returns: (bool) True if the value was saved to the database. False if the
                         value was identical to the current instance
        """
        self.log.debug('add', device_id=device_id, class_id=class_id,
                       instance_id=instance_id, attributes=attributes)

        now = self._time_to_string(datetime.utcnow())
        attrs = [MibAttributeData(name=k,
                                  value=self._attribute_to_string(device_id,
                                                                  class_id,
                                                                  k,
                                                                  v)) for k, v in attributes.items()]
        class_data = MibClassData(class_id=class_id,
                                  instances=[MibInstanceData(instance_id=instance_id,
                                                             created=now,
                                                             modified=now,
                                                             attributes=attrs)])

        self._root_proxy.add(MibDbExternal.CLASSES_PATH.format(device_id), class_data)
        self.log.debug('set-complete', device_id=device_id, class_id=class_id,
                       entity_id=instance_id, attributes=attributes)
        return True

    def _add_new_instance(self,  device_id, class_id, instance_id, attributes):
        """
        Create an entry for a instance of an existing class in the external database

        :param device_id: (str) ONU Device ID
        :param class_id: (int) ME Class ID
        :param instance_id: (int) ME Entity ID
        :param attributes: (dict) Attribute dictionary

        :returns: (bool) True if the value was saved to the database. False if the
                         value was identical to the current instance
        """
        self.log.debug('add', device_id=device_id, class_id=class_id,
                       instance_id=instance_id, attributes=attributes)

        now = self._time_to_string(datetime.utcnow())
        attrs = [MibAttributeData(name=k,
                                  value=self._attribute_to_string(device_id,
                                                                  class_id,
                                                                  k,
                                                                  v)) for k, v in attributes.items()]
        instance_data = MibInstanceData(instance_id=instance_id,
                                        created=now,
                                        modified=now,
                                        attributes=attrs)

        self._root_proxy.add(MibDbExternal.INSTANCES_PATH.format(device_id, class_id),
                             instance_data)

        self.log.debug('set-complete', device_id=device_id, class_id=class_id,
                       entity_id=instance_id, attributes=attributes)
        return True

    def set(self, device_id, class_id, instance_id, attributes):
        """
        Set a database value.  This should only be called by the MIB synchronizer
        and its related tasks

        :param device_id: (str) ONU Device ID
        :param class_id: (int) ME Class ID
        :param instance_id: (int) ME Entity ID
        :param attributes: (dict) Attribute dictionary

        :returns: (bool) True if the value was saved to the database. False if the
                         value was identical to the current instance

        :raises KeyError: If device does not exist
        :raises DatabaseStateError: If the database is not enabled
        """
        self.log.debug('set', device_id=device_id, class_id=class_id,
                       instance_id=instance_id, attributes=attributes)
        try:
            if not isinstance(device_id, basestring):
                raise TypeError('Device ID should be a string')

            if not 0 <= class_id <= 0xFFFF:
                raise ValueError("Invalid Class ID: {}, should be 0..65535".format(class_id))

            if not 0 <= instance_id <= 0xFFFF:
                raise ValueError("Invalid Instance ID: {}, should be 0..65535".format(instance_id))

            if not isinstance(attributes, dict):
                raise TypeError("Attributes should be a dictionary")

            if not self._started:
                raise DatabaseStateError('The Database is not currently active')

            # Determine the best strategy to add the information
            dev_proxy = self._device_proxy(device_id)

            try:
                class_data = dev_proxy.get(MibDbExternal.CLASS_PATH.format(class_id), deep=True)

                inst_data = next((inst for inst in class_data.instances
                                 if inst.instance_id == instance_id), None)

                if inst_data is None:
                    return self._add_new_instance(device_id, class_id, instance_id, attributes)

                # Possibly adding to or updating an existing instance
                # Get instance proxy, creating it if needed

                exist_attr_indexes = dict()
                attr_len = len(inst_data.attributes)

                for index in xrange(0, attr_len):
                    exist_attr_indexes[inst_data.attributes[index].name] = index

                modified = False
                new_attributes = []

                for k, v in attributes.items():
                    str_value = self._attribute_to_string(device_id, class_id, k, v)
                    new_attributes.append(MibAttributeData(name=k, value=str_value))

                    if k not in exist_attr_indexes or \
                            inst_data.attributes[exist_attr_indexes[k]].value != str_value:
                        modified = True

                if modified:
                    now = datetime.utcnow()
                    new_data = MibInstanceData(instance_id=instance_id,
                                               created=inst_data.created,
                                               modified=self._time_to_string(now),
                                               attributes=new_attributes)
                    dev_proxy.remove(MibDbExternal.INSTANCE_PATH.format(class_id, instance_id))
                    self._root_proxy.add(MibDbExternal.INSTANCES_PATH.format(device_id,
                                                                             class_id), new_data)

                self.log.debug('set-complete', device_id=device_id, class_id=class_id,
                               entity_id=instance_id, attributes=attributes, modified=modified)

                return modified

            except KeyError:
                # Here if the class-id does not yet exist in the database
                return self._add_new_class(device_id, class_id, instance_id,
                                           attributes)
        except Exception as e:
            self.log.exception('set-exception', device_id=device_id, class_id=class_id,
                               instance_id=instance_id, attributes=attributes, e=e)
            raise

    def delete(self, device_id, class_id, entity_id):
        """
        Delete an entity from the database if it exists.  If all instances
        of a class are deleted, the class is deleted as well.

        :param device_id: (str) ONU Device ID
        :param class_id: (int) ME Class ID
        :param entity_id: (int) ME Entity ID

        :returns: (bool) True if the instance was found and deleted. False
                         if it did not exist.

        :raises KeyError: If device does not exist
        :raises DatabaseStateError: If the database is not enabled
        """
        self.log.debug('delete', device_id=device_id, class_id=class_id,
                       entity_id=entity_id)

        if not self._started:
            raise DatabaseStateError('The Database is not currently active')

        if not isinstance(device_id, basestring):
            raise TypeError('Device ID should be an string')

        if not 0 <= class_id <= 0xFFFF:
            raise ValueError('class-id is 0..0xFFFF')

        if not 0 <= entity_id <= 0xFFFF:
            raise ValueError('instance-id is 0..0xFFFF')

        try:
            # Remove instance
            self._instance_proxy(device_id, class_id, entity_id).remove('/')
            now = datetime.utcnow()

            # If resulting class has no instance, remove it as well
            class_proxy = self._class_proxy(device_id, class_id)
            class_data = class_proxy.get('/', depth=1)

            if len(class_data.instances) == 0:
                class_proxy.remove('/')

            self._modified = now
            return True

        except KeyError:
            return False    # Not found

        except Exception as e:
            self.log.exception('get-last-sync-exception', device_id=device_id, e=e)
            raise

    def query(self, device_id, class_id=None, instance_id=None, attributes=None):
        """
        Get database information.

        This method can be used to request information from the database to the detailed
        level requested

        :param device_id: (str) ONU Device ID
        :param class_id:  (int) Managed Entity class ID
        :param instance_id: (int) Managed Entity instance
        :param attributes: (list/set or str) Managed Entity instance's attributes

        :return: (dict) The value(s) requested. If class/inst/attribute is
                        not found, an empty dictionary is returned
        :raises KeyError: If the requested device does not exist
        :raises DatabaseStateError: If the database is not enabled
        """
        self.log.debug('query', device_id=device_id, class_id=class_id,
                       instance_id=instance_id, attributes=attributes)
        try:
            if class_id is None:
                # Get full device info
                dev_data = self._device_proxy(device_id).get('/', depth=-1)
                data = self._device_to_dict(dev_data)

            elif instance_id is None:
                # Get all instances of the class
                try:
                    cls_data = self._class_proxy(device_id, class_id).get('/', depth=-1)
                    data = self._class_to_dict(device_id, cls_data)

                except KeyError:
                    data = dict()

            else:
                # Get all attributes of a specific ME
                try:
                    inst_data = self._instance_proxy(device_id, class_id, instance_id).\
                        get('/', depth=-1)

                    if attributes is None:
                        # All Attributes
                        data = self._instance_to_dict(device_id, class_id, inst_data)

                    else:
                        # Specific attribute(s)
                        if isinstance(attributes, basestring):
                            attributes = {attributes}

                        data = {
                            attr.name: self._string_to_attribute(device_id,
                                                                 class_id,
                                                                 attr.name,
                                                                 attr.value)
                            for attr in inst_data.attributes if attr.name in attributes}

                except KeyError:
                    data = dict()

            return data

        except KeyError:
            self.log.warn('query-no-device', device_id=device_id)
            raise

        except Exception as e:
            self.log.exception('get-last-sync-exception', device_id=device_id, e=e)
            raise

    def _instance_to_dict(self, device_id, class_id, instance):
        if not isinstance(instance, MibInstanceData):
            raise TypeError('{} is not of type MibInstanceData'.format(type(instance)))

        data = {
            INSTANCE_ID_KEY: instance.instance_id,
            CREATED_KEY: self._string_to_time(instance.created),
            MODIFIED_KEY: self._string_to_time(instance.modified),
            ATTRIBUTES_KEY: dict()
        }
        for attribute in instance.attributes:
            data[ATTRIBUTES_KEY][attribute.name] = self._string_to_attribute(device_id,
                                                                             class_id,
                                                                             attribute.name,
                                                                             attribute.value)
        return data

    def _class_to_dict(self, device_id, val):
        if not isinstance(val, MibClassData):
            raise TypeError('{} is not of type MibClassData'.format(type(val)))

        data = {
            CLASS_ID_KEY: val.class_id,
        }
        for instance in val.instances:
            data[instance.instance_id] = self._instance_to_dict(device_id,
                                                                val.class_id,
                                                                instance)
        return data

    def _device_to_dict(self, val):
        if not isinstance(val, MibDeviceData):
            raise TypeError('{} is not of type MibDeviceData'.format(type(val)))

        data = {
            DEVICE_ID_KEY: val.device_id,
            CREATED_KEY: self._string_to_time(val.created),
            LAST_SYNC_KEY: self._string_to_time(val.last_sync_time),
            MDS_KEY: val.mib_data_sync,
            VERSION_KEY: val.version
        }
        for class_data in val.classes:
            data[class_data.class_id] = self._class_to_dict(val.device_id,
                                                            class_data)
        return data
