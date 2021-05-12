/*
 * Copyright 2017-2021 EPAM Systems, Inc. (https://www.epam.com/)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.epam.pipeline.manager.user;

import com.epam.pipeline.common.MessageConstants;
import com.epam.pipeline.common.MessageHelper;
import com.epam.pipeline.entity.user.RunnerSid;
import com.epam.pipeline.entity.user.PipelineUser;
import com.epam.pipeline.entity.user.Role;
import com.epam.pipeline.repository.user.PipelineUserRepository;
import lombok.RequiredArgsConstructor;
import org.apache.commons.collections4.ListUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@RequiredArgsConstructor
@Service
public class UserRunnersManager {
    private final PipelineUserRepository pipelineUserRepository;
    private final MessageHelper messageHelper;

    public List<RunnerSid> getRunners(final Long id) {
        return getUserOrThrow(id).getAllowedRunners();
    }

    public boolean hasUserAsRunner(final PipelineUser user, final String runAsUser) {
        return ListUtils.emptyIfNull(getUserByNameOrThrow(runAsUser).getAllowedRunners()).stream()
                .anyMatch(aclSidEntity -> isRunnerAllowed(aclSidEntity, user));
    }

    @Transactional
    public List<RunnerSid> saveRunners(final Long id, final List<RunnerSid> runners) {
        final PipelineUser user = getUserOrThrow(id);
        user.setAllowedRunners(ListUtils.emptyIfNull(runners));
        pipelineUserRepository.save(user);
        return runners;
    }

    private PipelineUser getUserOrThrow(final Long id) {
        return Optional.of(pipelineUserRepository.findOne(id)).orElseThrow(() -> new IllegalArgumentException(
                messageHelper.getMessage(MessageConstants.ERROR_USER_ID_NOT_FOUND, id)));
    }

    private PipelineUser getUserByNameOrThrow(final String userName) {
        return pipelineUserRepository.findByUserName(userName).orElseThrow(() -> new IllegalArgumentException(
                messageHelper.getMessage(MessageConstants.ERROR_USER_NAME_NOT_FOUND, userName)));
    }

    private boolean isRunnerAllowed(final RunnerSid runnersAclSid, final PipelineUser user) {
        return isRunnerAllowedForUser(runnersAclSid, user.getUserName())
                || isRunnerAllowedForRoles(runnersAclSid, user.getRoles());
    }

    private boolean isRunnerAllowedForUser(final RunnerSid runnerSid, final String userName) {
        return runnerSid.isPrincipal() && runnerSid.getName().equalsIgnoreCase(userName);
    }

    private boolean isRunnerAllowedForRoles(final RunnerSid runnersAclSid, final List<Role> roles) {
        return !runnersAclSid.isPrincipal()
                && ListUtils.emptyIfNull(roles).stream()
                .anyMatch(role -> role.getName().equalsIgnoreCase(runnersAclSid.getName()));
    }
}
