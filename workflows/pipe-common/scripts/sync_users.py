# Copyright 2017-2021 EPAM Systems, Inc. (https://www.epam.com/)
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

import logging
import os
import traceback
import time
from functools import reduce

from pipeline.api import PipelineAPI
from pipeline.log.logger import LocalLogger, RunLogger, TaskLogger, LevelLogger
from pipeline.utils.account import create_user


def _get_run_shared_users_and_groups(api, run_id):
    run = api.load_run(run_id) or {}
    run_sids = run.get('runSids', [])
    return reduce(
        lambda (us, gs), sid: (us + [sid['name']], gs) if sid['isPrincipal'] else (us, gs + [sid['name']]),
        run_sids,
        ([], []))


def _get_group_users(api, run_groups):
    groups = (api.load_roles() or []) if run_groups else []
    for group in groups:
        group_id = group.get('id')
        group_name = group.get('name')
        if not group_id or group_name not in run_groups:
            continue
        group_users = (api.load_role(group_id) or {}).get('users', [])
        for group_user in group_users:
            yield group_user['userName']


def _get_local_users():
    with open('/etc/passwd', 'r') as f:
        lines = f.readlines()
    for line in lines:
        stripped_line = line.strip()
        if stripped_line:
            yield stripped_line.split(':')[0]


if __name__ == '__main__':
    api_url = os.environ['API']
    api_token = os.environ['API_TOKEN']
    run_id = os.environ['RUN_ID']
    shared_dir = os.getenv('SHARED_ROOT', '/common')
    shared_home_dir = os.getenv('CP_CAP_SYNC_USERS_HOME_DIR', os.path.join(shared_dir, 'home'))
    sync_timeout = int(os.getenv('CP_CAP_SYNC_USERS_TIMEOUT_SECONDS', '60'))
    logging_directory = os.getenv('CP_CAP_SYNC_USERS_LOG_DIR', os.getenv('LOG_DIR', '/var/log'))
    logging_level = os.getenv('CP_CAP_SYNC_USERS_LOGGING_LEVEL', 'ERROR')
    logging_level_local = os.getenv('CP_CAP_SYNC_USERS_LOGGING_LEVEL_LOCAL', 'DEBUG')
    logging_format = os.getenv('CP_CAP_SYNC_USERS_LOGGING_FORMAT', '%(asctime)s:%(levelname)s: %(message)s')

    logging.basicConfig(level=logging_level_local, format=logging_format,
                        filename=os.path.join(logging_directory, 'sync_users.log'))

    api = PipelineAPI(api_url=api_url, log_dir=logging_directory)
    logger = RunLogger(api=api, run_id=run_id)
    logger = TaskLogger(task='UsersSynchronization', inner=logger)
    logger = LevelLogger(level=logging_level, inner=logger)
    logger = LocalLogger(inner=logger)

    while True:
        try:
            time.sleep(sync_timeout)
            logger.info('Starting users synchronization...')

            logger.info('Loading shared users and groups...')
            run_users, run_groups = _get_run_shared_users_and_groups(api, run_id)
            shared_users = set()
            shared_users.update(run_users)
            shared_users.update(_get_group_users(api, run_groups))
            logger.info('Loaded {} shared users.'.format(len(shared_users)))
            logger.debug('Loaded shared users: {}'.format(shared_users))

            logger.info('Loading existing users...')
            local_users = set(_get_local_users())

            users_to_create = shared_users - local_users
            logger.info('Creating {} users...'.format(len(users_to_create)))
            logger.debug('Creating users {}...'.format(users_to_create))
            for user in users_to_create:
                user_home_dir = os.path.join(shared_home_dir, user)
                create_user(user, user, home_dir=user_home_dir, skip_existing=True, logger=logger)

            logger.info('Finishing users synchronization...')
        except KeyboardInterrupt:
            logging.warning('Interrupted.')
            break
        except BaseException as e:
            traceback.print_exc()
            stacktrace = traceback.format_stack()
            logger.error('Users synchronization has failed: {} {}'.format(e, stacktrace))
