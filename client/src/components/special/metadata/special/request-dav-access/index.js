/*
 * Copyright 2017-2021 EPAM Systems, Inc. (https://www.epam.com/)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

import React from 'react';
import PropTypes from 'prop-types';
import classNames from 'classnames';
import moment from 'moment-timezone';
import {message} from 'antd';
import {inject} from 'mobx-react';
import displayDate from '../../../../../utils/displayDate';
import roleModel from '../../../../../utils/roleModel';
import DSWebDavAccessEnable from '../../../../../models/dataStorage/DataStorageWebDavAccessEnable';
import DSWebDavAccessRemove from '../../../../../models/dataStorage/DataStorageWebDavAccessRemove';
import styles from './request-dav-access.css';

const METADATA_KEY = 'dav-mount';

function davAccessInfo (value) {
  if (!value) {
    return undefined;
  }
  if (
    (typeof value === 'string' && !Number.isNaN(Number(value))) ||
    typeof value === 'number'
  ) {
    const time = moment.utc(new Date(Number(value) * 1000));
    const now = moment.utc();
    return {
      available: now < time,
      expiresAt: displayDate(time, 'D MMM YYYY, HH:mm')
    };
  }
  if (typeof value === 'boolean') {
    return {
      available: Boolean(value)
    };
  }
  return {
    available: /^true$/i.test(value)
  };
}

function RequestDavAccess (
  {
    metadata = {},
    readOnly: disabled = false,
    info,
    reload,
    preferences
  }
) {
  const {
    storageId,
    storageMask = 0
  } = info || {};
  const readOnly = disabled || !roleModel.readAllowed({mask: storageMask}) || !storageId;
  const {value = undefined} = metadata;
  const accessInfo = davAccessInfo(value);
  let infoString = 'Request file system access';
  if (readOnly) {
    infoString = 'File system access disabled';
  }
  if (accessInfo && accessInfo.available) {
    infoString = 'File system access enabled';
    if (accessInfo.expiresAt) {
      infoString = `File system access enabled till ${accessInfo.expiresAt}`;
    }
    if (!readOnly) {
      infoString = infoString.concat('.');
    }
  }
  const enabled = accessInfo && accessInfo.available;
  const enableAccess = () => {
    const hide = message.loading('Enabling file system access...', 0);
    const request = new DSWebDavAccessEnable();
    preferences
      .fetchIfNeededOrWait()
      .then(() => {
        const duration = preferences.webdavStorageAccessDurationSeconds;
        const payload = {
          id: storageId,
          time: duration
        };
        return request.send(payload);
      })
      .then(() => {
        if (request.error) {
          throw new Error(request.error);
        }
      })
      .catch(e => message.error(e.message, 5))
      .then(hide)
      .then(() => reload ? reload() : undefined);
  };
  const disableAccess = () => {
    const hide = message.loading('Disabling file system access...', 0);
    const request = new DSWebDavAccessRemove(storageId);
    request
      .send()
      .then(() => {
        if (request.error) {
          throw new Error(request.error);
        }
      })
      .catch(e => message.error(e.message, 5))
      .then(hide)
      .then(() => reload ? reload() : undefined);
  };
  return (
    <div
      className={
        classNames(
          styles.container,
          {
            [styles.enabled]: enabled,
            [styles.readOnly]: readOnly
          }
        )
      }
    >
      <span
        style={{marginRight: 5}}
        onClick={!readOnly && !enabled ? enableAccess : undefined}
      >
        {infoString}
      </span>
      {
        enabled && !readOnly && (
          <a
            className={styles.disableButton}
            onClick={disableAccess}
          >
            Disable
          </a>
        )
      }
    </div>
  );
}

RequestDavAccess.metatadaKey = METADATA_KEY;

RequestDavAccess.propTypes = {
  metadata: PropTypes.object,
  readOnly: PropTypes.bool,
  onChange: PropTypes.func,
  info: PropTypes.object,
  reload: PropTypes.func
};

export {METADATA_KEY};

export default inject('preferences')(RequestDavAccess);
