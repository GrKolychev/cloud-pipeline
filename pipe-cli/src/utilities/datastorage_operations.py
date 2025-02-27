# Copyright 2017-2020 EPAM Systems, Inc. (https://www.epam.com/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import multiprocessing
import os
import platform
import sys

import click
import prettytable
from future.utils import iteritems
from operator import itemgetter

from src.api.data_storage import DataStorage
from src.api.folder import Folder
from src.model.data_storage_wrapper import DataStorageWrapper, S3BucketWrapper
from src.model.data_storage_wrapper_type import WrapperType
from src.utilities.du import DataUsageHelper
from src.utilities.du_format_type import DuFormatType
from src.utilities.patterns import PatternMatcher
from src.utilities.storage.common import TransferResult, UploadResult
from src.utilities.storage.mount import Mount
from src.utilities.storage.umount import Umount

FOLDER_MARKER = '.DS_Store'


class DataStorageOperations(object):
    @classmethod
    def cp(cls, source, destination, recursive, force, exclude, include, quiet, tags, file_list, symlinks, threads,
           io_threads, clean=False, skip_existing=False, verify_destination=False):
        source_wrapper = DataStorageWrapper.get_wrapper(source, symlinks)
        destination_wrapper = DataStorageWrapper.get_wrapper(destination)
        files_to_copy = []

        if source_wrapper is None:
            click.echo('Could not resolve path {}'.format(source), err=True)
            sys.exit(1)
        if not source_wrapper.exists():
            click.echo("Source {} doesn't exist".format(source), err=True)
            sys.exit(1)
        if destination_wrapper is None:
            click.echo('Could not resolve path {}'.format(destination), err=True)
            sys.exit(1)
        if not recursive and not source_wrapper.is_file():
            click.echo('Flag --recursive (-r) is required to copy folders.', err=True)
            sys.exit(1)
        if file_list:
            if source_wrapper.is_file():
                click.echo('Option --file-list (-l) allowed for folders copy only.', err=True)
                sys.exit(1)
            if not os.path.exists(file_list):
                click.echo('Specified --file-list file does not exist.', err=True)
                sys.exit(1)
            files_to_copy = cls.__get_file_to_copy(file_list, source_wrapper.path)
        if threads and not recursive:
            click.echo('-n (--threads) is allowed for folders only.', err=True)
            sys.exit(1)
        if threads and platform.system() == 'Windows':
            click.echo('-n (--threads) is not supported for Windows OS', err=True)
            sys.exit(1)
        relative = os.path.basename(source) if source_wrapper.is_file() else None
        if not force and not verify_destination and not destination_wrapper.is_empty(relative=relative):
            click.echo('The destination already exists. Specify --force (-f) flag to overwrite data or '
                       '--verify-destination (-vd) flag to enable existence check for each destination path.',
                       err=True)
            sys.exit(1)

        # append slashes to path to correctly determine file/folder type
        if not source_wrapper.is_file():
            if not source_wrapper.is_local() and not source_wrapper.path.endswith('/'):
                source_wrapper.path = source_wrapper.path + '/'
            if destination_wrapper.is_local() and not destination_wrapper.path.endswith(os.path.sep):
                destination_wrapper.path = destination_wrapper.path + os.path.sep
            if not destination_wrapper.is_local() and not destination_wrapper.path.endswith('/'):
                destination_wrapper.path = destination_wrapper.path + '/'

        # copying a file to a remote destination, we need to set folder/file flag correctly
        if source_wrapper.is_file() and not destination_wrapper.is_local() and not destination.endswith('/'):
            destination_wrapper.is_file_flag = True

        command = 'mv' if clean else 'cp'
        permission_to_check = os.R_OK if command == 'cp' else os.W_OK
        manager = DataStorageWrapper.get_operation_manager(source_wrapper, destination_wrapper, command)
        items = files_to_copy if file_list else source_wrapper.get_items()
        items = cls._filter_items(items, manager, source_wrapper, destination_wrapper, permission_to_check,
                                  include, exclude, force, quiet, skip_existing, verify_destination)
        sorted_items = list()
        transfer_results = []
        for item in items:
            full_path = item[1]
            relative_path = item[2]
            size = item[3]
            if threads:
                sorted_items.append(item)
            else:
                transfer_result = manager.transfer(source_wrapper, destination_wrapper, path=full_path,
                                                   relative_path=relative_path, clean=clean, quiet=quiet, size=size,
                                                   tags=tags, io_threads=io_threads)
                if not destination_wrapper.is_local() and transfer_result:
                    transfer_results.append(transfer_result)
                    transfer_results = cls._flush_transfer_results(source_wrapper, destination_wrapper,
                                                                   transfer_results, clean=clean)
        if threads:
            cls._multiprocess_transfer_items(sorted_items, threads, manager, source_wrapper, destination_wrapper,
                                             clean, quiet, tags, io_threads)
        else:
            if not destination_wrapper.is_local():
                cls._flush_transfer_results(source_wrapper, destination_wrapper,
                                            transfer_results, clean=clean, flush_size=1)

    @classmethod
    def _filter_items(cls, items, manager, source_wrapper, destination_wrapper, permission_to_check,
                      include, exclude, force, quiet, skip_existing, verify_destination):
        filtered_items = []
        for item in items:
            full_path = item[1]
            relative_path = item[2]
            source_size = item[3]

            if relative_path.endswith(FOLDER_MARKER):
                filtered_items.append(item)
                continue

            # check that we have corresponding permission for the file before take action
            if source_wrapper.is_local() and not os.access(full_path, permission_to_check):
                continue
            if not include and not exclude:
                if source_wrapper.is_file() and not source_wrapper.path == full_path:
                    continue
                if not source_wrapper.is_file():
                    possible_folder_name = source_wrapper.path_with_trailing_separator()
                    if not full_path.startswith(possible_folder_name):
                        continue
            if not PatternMatcher.match_any(relative_path, include):
                if not quiet:
                    click.echo("Skipping file {} since it doesn't match any of include patterns [{}]."
                               .format(full_path, ",".join(include)))
                continue
            if PatternMatcher.match_any(relative_path, exclude, default=False):
                if not quiet:
                    click.echo("Skipping file {} since it matches exclude patterns [{}]."
                               .format(full_path, ",".join(exclude)))
                continue

            if not skip_existing and (force or not verify_destination):
                filtered_items.append(item)
                continue

            destination_key = manager.get_destination_key(destination_wrapper, relative_path)
            destination_size = manager.get_destination_size(destination_wrapper, destination_key)
            destination_is_empty = destination_size is None
            if destination_is_empty:
                filtered_items.append(item)
                continue
            if skip_existing:
                source_key = manager.get_source_key(source_wrapper, full_path)
                need_to_overwrite = not manager.skip_existing(source_key, source_size, destination_key,
                                                              destination_size, quiet)
                if need_to_overwrite and not force:
                    cls._force_required()
                if need_to_overwrite:
                    filtered_items.append(item)
                continue
            if not force:
                cls._force_required()
            filtered_items.append(item)
        return filtered_items

    @classmethod
    def storage_remove_item(cls, path, yes, version, hard_delete, recursive, exclude, include):
        """ Removes file or folder
        """
        if version and hard_delete:
            click.echo('"version" argument should\'t be combined with "hard-delete" option', err=True)
            sys.exit(1)
        source_wrapper = DataStorageWrapper.get_cloud_wrapper(path, versioning=version is not None or hard_delete)
        if source_wrapper is None or not source_wrapper.exists():
            click.echo('Storage path "{}" was not found'.format(path), err=True)
            sys.exit(1)
        if len(source_wrapper.path) == 0:
            click.echo('Cannot remove root folder \'{}\''.format(path), err=True)
            sys.exit(1)
        if not source_wrapper.is_file() and not recursive:
            click.echo('Flag --recursive (-r) is required to remove folders.', err=True)
            sys.exit(1)
        if (version or hard_delete) and not source_wrapper.bucket.policy.versioning_enabled:
            click.echo('Error: versioning is not enabled for storage.', err=True)
            sys.exit(1)
        if not yes:
            click.confirm('Are you sure you want to remove everything at path \'{}\'?'.format(path),
                          abort=True)
        click.echo('Removing {} ...'.format(path), nl=False)

        manager = source_wrapper.get_delete_manager(versioning=version or hard_delete)
        manager.delete_items(source_wrapper.path, version=version, hard_delete=hard_delete,
                             exclude=exclude, include=include, recursive=recursive and not source_wrapper.is_file())
        click.echo(' done.')

    @classmethod
    def save_data_storage(cls, name, description, sts_duration, lts_duration, versioning,
                          backup_duration, type, parent_folder, on_cloud, path, region_id):
        directory = None
        if parent_folder:
            directory = Folder.load(parent_folder)
            if directory is None:
                click.echo("Error: Directory with name '{}' not found! "
                           "Check if it exists and you have permission to read it".format(parent_folder), err=True)
                sys.exit(1)
        if region_id == 'default':
            region_id = None
        else:
            try:
                region_id = int(region_id)
            except ValueError:
                click.echo("Error: Given region id '{}' is not a number.".format(region_id))
                sys.exit(1)
        DataStorage.save(name, path, description, sts_duration, lts_duration, versioning, backup_duration, type,
                         directory.id if directory else None, on_cloud, region_id)

    @classmethod
    def delete(cls, name, on_cloud, yes):
        if not yes:
            if on_cloud:
                click.confirm(
                    'Are you sure you want to delete datastorage {} and also delete it from a cloud?'.format(name),
                    abort=True)
            else:
                click.confirm(
                    'Are you sure you want to delete datastorage {}?'.format(name),
                    abort=True)

        DataStorage.delete(name, on_cloud)

    @classmethod
    def policy(cls, storage_name, sts_duration, lts_duration, backup_duration, versioning):
        DataStorage.policy(storage_name, sts_duration, lts_duration, backup_duration, versioning)

    @classmethod
    def mvtodir(cls, name, directory):
        folder_id = None
        if directory is not "/":
            if os.path.split(directory)[0]:  # case with path
                folder = Folder.load(directory)
            else:
                folder = Folder.load_by_name(directory)
            if folder is None:
                click.echo("Directory with name {} does not exist!".format(directory), err=True)
                sys.exit(1)
            folder_id = folder.id
        DataStorage.mvtodir(name, folder_id)

    @classmethod
    def restore(cls, path, version, recursive, exclude, include):
        source_wrapper = DataStorageWrapper.get_cloud_wrapper(path, True)
        if source_wrapper is None:
            click.echo('Storage path "{}" was not found'.format(path), err=True)
            sys.exit(1)
        if (recursive or exclude or include) and not isinstance(source_wrapper, S3BucketWrapper):
            click.echo('Folder restore allowed for S3 provider only', err=True)
            sys.exit(1)
        if not source_wrapper.bucket.policy.versioning_enabled:
            click.echo('Versioning is not enabled for storage "{}"'.format(source_wrapper.bucket.name), err=True)
            sys.exit(1)
        if version and recursive:
            click.echo('"version" argument should\'t be combined with "recursive" option', err=True)
            sys.exit(1)
        if not recursive and not source_wrapper.is_file():
            click.echo('Flag --recursive (-r) is required to restore folders.', err=True)
            sys.exit(1)
        manager = source_wrapper.get_restore_manager()
        manager.restore_version(version, exclude, include, recursive=recursive)

    @classmethod
    def storage_list(cls, path, show_details, show_versions, recursive, page, show_all):
        """Lists storage contents
        """
        if path:
            root_bucket = None
            original_path = ''
            root_bucket, original_path, _ = DataStorage.load_from_uri(path)
            if show_versions and not root_bucket.policy.versioning_enabled:
                click.echo('Error: versioning is not enabled for storage.', err=True)
                sys.exit(1)
            if root_bucket is None:
                click.echo('Storage path "{}" was not found'.format(path), err=True)
                sys.exit(1)
            else:
                relative_path = original_path if original_path != '/' else ''
                cls.__print_data_storage_contents(root_bucket, relative_path, show_details, recursive,
                                                  page_size=page, show_versions=show_versions, show_all=show_all)
        else:
            # If no argument is specified - list brief details of all buckets
            cls.__print_data_storage_contents(None, None, show_details, recursive, show_all=show_all)

    @classmethod
    def storage_mk_dir(cls, folders):
        """ Creates a directory
        """
        for original_path in folders:
            bucket, full_path, relative_path = DataStorage.load_from_uri(original_path)
            if len(relative_path) == 0:
                click.echo('Cannot create folder \'{}\': already exists'.format(original_path), err=True)
                continue
            click.echo('Creating folder {}...'.format(original_path), nl=False)
            result = DataStorage.create_folder(bucket.identifier, relative_path)
            if result is not None and result.error is None:
                click.echo('done.')
            elif result is not None and result.error is not None:
                click.echo('failed.')
                click.echo(result.error, err=True)

    @classmethod
    def set_object_tags(cls, path, tags, version):
        root_bucket, full_path, relative_path = DataStorage.load_from_uri(path)
        updated_tags = DataStorage.set_object_tags(root_bucket.identifier, relative_path,
                                                   cls.convert_input_pairs_to_json(tags), version)
        if not updated_tags:
            raise RuntimeError("Failed to set tags for path '{}'.".format(path))

    @classmethod
    def get_object_tags(cls, path, version):
        root_bucket, full_path, relative_path = DataStorage.load_from_uri(path)
        tags = DataStorage.get_object_tags(root_bucket.identifier, relative_path, version)
        if not tags:
            click.echo("No tags available for path '{}'.".format(path))
        else:
            click.echo(cls.create_table(tags))

    @classmethod
    def delete_object_tags(cls, path, tags, version):
        if not tags:
            click.echo("Error: Missing argument \"tags\"", err=True)
            sys.exit(1)
        root_bucket, full_path, relative_path = DataStorage.load_from_uri(path)
        DataStorage.delete_object_tags(root_bucket.identifier, relative_path, tags, version)

    @classmethod
    def du(cls, storage_name, relative_path=None, format='M', depth=None):
        if depth and not storage_name:
            click.echo("Error: bucket path must be provided with --depth option", err=True)
            sys.exit(1)
        du_helper = DataUsageHelper(format)
        items_table = prettytable.PrettyTable()
        fields = ["Storage", "Files count", "Size (%s)" % DuFormatType.pretty_type(format)]
        items_table.field_names = fields
        items_table.align = "l"
        items_table.border = False
        items_table.padding_width = 2
        items_table.align['Size'] = 'r'
        if storage_name:
            if not relative_path or relative_path == "/":
                relative_path = ''
            storage = DataStorage.get(storage_name)
            if storage is None:
                raise RuntimeError('Storage "{}" was not found'.format(storage_name))
            if storage.type.lower() == 'nfs':
                if depth:
                    raise RuntimeError('--depth option is not supported for NFS storages')
                items_table.add_row(du_helper.get_nfs_storage_summary(storage_name, relative_path))
            else:
                for item in du_helper.get_cloud_storage_summary(storage, relative_path, depth):
                    items_table.add_row(item)
        else:
            # If no argument is specified - list all buckets
            items = du_helper.get_total_summary()
            if items is None:
                click.echo("No datastorages available.")
                sys.exit(0)
            for item in items:
                items_table.add_row(item)
        click.echo(items_table)
        click.echo()

    @classmethod
    def convert_input_pairs_to_json(cls, tags):
        result = dict()
        for tags_for_update in tags:
            if "=" not in tags_for_update:
                raise ValueError("Tags must be specified as KEY=VALUE pair.")
            pair = tags_for_update.split("=", 1)
            result.update({pair[0]: pair[1]})
        return result

    @classmethod
    def create_table(cls, tags):
        table = prettytable.PrettyTable()
        table.field_names = ["Tag name", "Value"]
        table.align = "l"
        table.header = True
        for (key, value) in iteritems(tags):
            table.add_row([key, value])
        return table

    @classmethod
    def __print_data_storage_contents(cls, bucket_model, relative_path,
                                      show_details, recursive, page_size=None, show_versions=False, show_all=False):
        items = []
        header = None
        if bucket_model is not None:
            wrapper = DataStorageWrapper.get_cloud_wrapper_for_bucket(bucket_model, relative_path)
            manager = wrapper.get_list_manager(show_versions=show_versions)
            items = manager.list_items(relative_path, recursive=recursive, page_size=page_size, show_all=show_all)
        else:
            # If no argument is specified - list brief details of all buckets
            items = list(DataStorage.list())
            if not items:
                click.echo("No datastorages available.")
                sys.exit(0)

        if recursive and header is not None:
            click.echo(header)

        if show_details:
            items_table = prettytable.PrettyTable()
            fields = ["Type", "Labels", "Modified", "Size", "Name"]
            if show_versions:
                fields.append("Version")
            items_table.field_names = fields
            items_table.align = "l"
            items_table.border = False
            items_table.padding_width = 2
            items_table.align['Size'] = 'r'
            for item in items:
                name = item.name
                changed = ''
                size = ''
                labels = ''
                if item.type is not None and item.type in WrapperType.cloud_types():
                    name = item.path
                item_updated = item.deleted or item.changed
                if item_updated is not None:
                    if bucket_model is None:
                        # need to wrap into datetime since bucket listing returns str
                        item_datetime = datetime.datetime.strptime(item_updated, '%Y-%m-%d %H:%M:%S')
                    else:
                        item_datetime = item_updated
                    changed = item_datetime.strftime('%Y-%m-%d %H:%M:%S')
                if item.size is not None and not item.deleted:
                    size = item.size
                if item.labels is not None and len(item.labels) > 0 and not item.deleted:
                    labels = ', '.join(map(lambda i: i.value, item.labels))
                item_type = "-File" if item.delete_marker or item.deleted else item.type
                row = [item_type, labels, changed, size, name]
                if show_versions:
                    row.append('')
                items_table.add_row(row)
                if show_versions and item.type == 'File':
                    if item.deleted:
                        # Additional synthetic delete version
                        row = ['-File', '', item.deleted.strftime('%Y-%m-%d %H:%M:%S'), size, name, '- (latest)']
                        items_table.add_row(row)
                    for version in item.versions:
                        version_type = "-File" if version.delete_marker else "+File"
                        version_label = "{} (latest)".format(version.version) if version.latest else version.version
                        labels = ', '.join(map(lambda i: i.value, version.labels))
                        size = '' if version.size is None else version.size
                        row = [version_type, labels, version.changed.strftime('%Y-%m-%d %H:%M:%S'), size, name, version_label]
                        items_table.add_row(row)

            click.echo(items_table)
            click.echo()
        else:
            for item in items:
                click.echo('{}\t\t'.format(item.path), nl=False)
            click.echo()

    @classmethod
    def __get_file_to_copy(cls, file_path, source_path):
        with open(file_path, 'rb') as source:
            for line in source:
                line = line.strip()
                splitted = line.split('\t')
                path = splitted[0]
                size = long(float(splitted[1]))
                yield ('File', os.path.join(source_path, path), path, size)

    @classmethod
    def mount_storage(cls, mountpoint, file=False, bucket=None, log_file=None, log_level=None, options=None,
                      custom_options=None, quiet=False, threading=False, mode=700, timeout=1000):
        if not file and not bucket:
            click.echo('Either file system mode should be enabled (-f/--file) '
                       'or bucket name should be specified (-b/--bucket BUCKET).', err=True)
            sys.exit(1)
        Mount().mount_storages(mountpoint, file, bucket, options, custom_options=custom_options, quiet=quiet,
                               log_file=log_file, log_level=log_level,  threading=threading,
                               mode=mode, timeout=timeout)

    @classmethod
    def umount_storage(cls, mountpoint, quiet=False):
        cls.check_platform("umount")
        if not os.path.isdir(mountpoint):
            click.echo('Mountpoint "%s" is not a folder.' % mountpoint, err=True)
            sys.exit(1)
        if not os.path.ismount(mountpoint):
            click.echo('Directory "%s" is not a mountpoint.' % mountpoint, err=True)
            sys.exit(1)
        Umount().umount_storages(mountpoint, quiet=quiet)

    @classmethod
    def check_platform(self, command):
        if platform.system() == 'Windows':
            click.echo('%s command is not supported for Windows OS.' % command, err=True)
            sys.exit(1)

    @classmethod
    def _split_items_by_process(cls, sorted_items, threads):
        splitted_items = list()
        for i in range(threads):
            splitted_items.append(list())
        for i in range(len(sorted_items)):
            j = i % threads
            splitted_items[j].append(sorted_items[i])
        return splitted_items

    @classmethod
    def _multiprocess_transfer_items(cls, sorted_items, threads, manager, source_wrapper, destination_wrapper, clean,
                                     quiet, tags, io_threads):
        size_index = 3
        sorted_items.sort(key=itemgetter(size_index), reverse=True)
        splitted_items = cls._split_items_by_process(sorted_items, threads)
        lock = multiprocessing.Lock()

        workers = []
        for i in range(threads):
            process = multiprocessing.Process(target=cls._transfer_items,
                                              args=(splitted_items[i],
                                                    manager,
                                                    source_wrapper,
                                                    destination_wrapper,
                                                    clean,
                                                    quiet,
                                                    tags,
                                                    io_threads,
                                                    lock))
            process.start()
            workers.append(process)
        cls._handle_keyboard_interrupt(workers)

    @classmethod
    def _transfer_items(cls, items, manager, source_wrapper, destination_wrapper, clean, quiet, tags, io_threads, lock):
        transfer_results = []
        for item in items:
            full_path = item[1]
            relative_path = item[2]
            size = item[3]
            transfer_result = manager.transfer(source_wrapper, destination_wrapper, path=full_path,
                                               relative_path=relative_path, clean=clean, quiet=quiet, size=size,
                                               tags=tags, io_threads=io_threads, lock=lock)
            if not destination_wrapper.is_local() and transfer_result:
                transfer_results.append(transfer_result)
                transfer_results = cls._flush_transfer_results(source_wrapper, destination_wrapper,
                                                               transfer_results, clean=clean)
        if not destination_wrapper.is_local():
            cls._flush_transfer_results(source_wrapper, destination_wrapper,
                                        transfer_results, clean=clean, flush_size=1)

    @classmethod
    def _flush_transfer_results(cls, source_wrapper, destination_wrapper, transfer_results,
                                clean=False, flush_size=100):
        if len(transfer_results) < flush_size:
            return transfer_results
        tag_objects = []
        source_tags_map = {}
        if transfer_results and isinstance(transfer_results[0], TransferResult):
            source_tags = DataStorage.batch_load_object_tags(source_wrapper.bucket.identifier,
                                                             [{'path': transfer_result.source_key}
                                                              for transfer_result in transfer_results])
            for source_tag in source_tags:
                source_object_path = source_tag.get('object', {}).get('path', '')
                source_object_tags = source_tags_map.get(source_object_path, {})
                source_object_tags[source_tag.get('key', '')] = source_tag.get('value', '')
                source_tags_map[source_object_path] = source_object_tags
        for transfer_result in transfer_results:
            all_tags = {}
            all_tags.update(source_tags_map.get(transfer_result.source_key, {}))
            all_tags.update(transfer_result.tags)
            for key, value in all_tags.items():
                tag_objects.append({
                    'path': transfer_result.destination_key,
                    'key': key,
                    'value': value
                })
                if destination_wrapper.bucket.policy.versioning_enabled and transfer_result.destination_version:
                    tag_objects.append({
                        'path': transfer_result.destination_key,
                        'version': transfer_result.destination_version,
                        'key': key,
                        'value': value
                    })
        DataStorage.batch_insert_object_tags(destination_wrapper.bucket.identifier, tag_objects)
        if clean and not source_wrapper.is_local() and not source_wrapper.bucket.policy.versioning_enabled:
            DataStorage.batch_delete_all_object_tags(source_wrapper.bucket.identifier,
                                                     [{'path': transfer_result.source_key}
                                                      for transfer_result in transfer_results])
        return []

    @staticmethod
    def _handle_keyboard_interrupt(workers):
        try:
            for worker in workers:
                worker.join()
        except KeyboardInterrupt:
            for worker in workers:
                worker.terminate()
                worker.join()

    @staticmethod
    def _force_required():
        click.echo('Flag --force (-f) is required to overwrite files in the destination data.', err=True)
        sys.exit(1)
