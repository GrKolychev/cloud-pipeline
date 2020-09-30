/*
 * Copyright 2017-2020 EPAM Systems, Inc. (https://www.epam.com/)
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

package com.epam.pipeline.acl.region;

import com.epam.pipeline.controller.vo.region.AWSRegionDTO;
import com.epam.pipeline.controller.vo.region.AbstractCloudRegionDTO;
import com.epam.pipeline.entity.info.CloudRegionInfo;
import com.epam.pipeline.entity.region.AbstractCloudRegion;
import com.epam.pipeline.entity.region.AwsRegion;
import com.epam.pipeline.entity.region.CloudProvider;
import com.epam.pipeline.manager.region.CloudRegionManager;
import com.epam.pipeline.security.acl.AclPermission;
import com.epam.pipeline.test.acl.AbstractAclTest;
import org.junit.Before;
import org.junit.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.test.context.support.WithMockUser;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.doReturn;

public class CloudRegionApiServiceTest extends AbstractAclTest {

    @Autowired
    private CloudRegionApiService cloudRegionApiService;

    @Autowired
    private CloudRegionManager cloudRegionManager;

    private final AbstractCloudRegionDTO cloudRegionDTO = new AWSRegionDTO();

    private final List<String> availableCloudsList = Arrays.asList("AWS", "AZURE", "GCP");

    private AwsRegion region;

    private List<AbstractCloudRegion> clouds;

    private List<CloudRegionInfo> cloudRegionInfoList;

    @Before
    public void setUp() throws Exception {
        region = new AwsRegion();
        region.setId(1L);
        region.setName("");
        region.setOwner(ADMIN_ROLE);

        clouds = new ArrayList<>();
        clouds.add(region);

        cloudRegionInfoList = new ArrayList<>();
        cloudRegionInfoList.add(new CloudRegionInfo(region));
    }

    @Test
    @WithMockUser(roles = ADMIN_ROLE)
    public void shouldAllowLoadRegionsInfoForAdmin() {
        doReturn(cloudRegionInfoList).when(cloudRegionManager).loadAllRegionsInfo();

        assertThat(cloudRegionApiService.loadAllRegionsInfo()).isEqualTo(cloudRegionInfoList);
    }

    @Test
    @WithMockUser(roles = GENERAL_USER_ROLE)
    public void shouldAllowLoadRegionsInfoForGeneralUser() {
        doReturn(cloudRegionInfoList).when(cloudRegionManager).loadAllRegionsInfo();

        assertThat(cloudRegionApiService.loadAllRegionsInfo()).isEqualTo(cloudRegionInfoList);
    }

    @Test(expected = AccessDeniedException.class)
    @WithMockUser(roles = SIMPLE_USER_ROLE)
    public void shouldDenyLoadRegionsInfoForNotAdminOrGeneralUser() {
        doReturn(cloudRegionInfoList).when(cloudRegionManager).loadAllRegionsInfo();

        cloudRegionApiService.loadAllRegionsInfo();
    }

    @Test
    @WithMockUser(roles = ADMIN_ROLE)
    public void shouldCreateAbstractCloudRegionForAdmin() {
        doReturn(region).when(cloudRegionManager).create(cloudRegionDTO);

        assertThat(cloudRegionApiService.create(cloudRegionDTO)).isEqualTo(region);
    }

    @Test(expected = AccessDeniedException.class)
    @WithMockUser(roles = SIMPLE_USER_ROLE)
    public void shouldNotCreateAbstractCloudRegionForNotAdmin() {
        doReturn(region).when(cloudRegionManager).create(cloudRegionDTO);

        cloudRegionApiService.create(cloudRegionDTO);
    }

    @Test
    @WithMockUser(roles = ADMIN_ROLE)
    public void shouldUpdateAbstractCloudRegionForAdmin() {
        doReturn(region).when(cloudRegionManager).update(region.getId(), cloudRegionDTO);

        assertThat(cloudRegionApiService.update(region.getId(), cloudRegionDTO)).isEqualTo(region);
    }

    @Test(expected = AccessDeniedException.class)
    @WithMockUser(roles = SIMPLE_USER_ROLE)
    public void shouldNotUpdateAbstractCloudRegionForNotAdmin() {
        doReturn(region).when(cloudRegionManager).update(region.getId(), cloudRegionDTO);

        cloudRegionApiService.update(region.getId(), cloudRegionDTO);
    }

    @Test
    @WithMockUser(roles = ADMIN_ROLE)
    public void shouldDeleteAbstractCloudRegionForAdmin() {
        doReturn(region).when(cloudRegionManager).delete(region.getId());

        assertThat(cloudRegionApiService.delete(region.getId())).isEqualTo(region);
    }

    @Test(expected = AccessDeniedException.class)
    @WithMockUser(roles = SIMPLE_USER_ROLE)
    public void shouldDeleteAbstractCloudRegionForNotAdmin() {
        doReturn(region).when(cloudRegionManager).delete(region.getId());

        cloudRegionApiService.delete(region.getId());
    }

    @Test
    @WithMockUser(roles = ADMIN_ROLE)
    public void shouldLoadAllAvailableCloudsForAdmin() {
        doReturn(availableCloudsList).when(cloudRegionManager).loadAllAvailable(CloudProvider.AWS);

        assertThat(cloudRegionApiService.loadAllAvailable(CloudProvider.AWS)).isEqualTo(availableCloudsList);
    }

    @Test(expected = AccessDeniedException.class)
    @WithMockUser(roles = SIMPLE_USER_ROLE)
    public void shouldNotLoadAllAvailableCloudsForNotAdmin() {
        doReturn(availableCloudsList).when(cloudRegionManager).loadAllAvailable(CloudProvider.AWS);

        cloudRegionApiService.loadAllAvailable(CloudProvider.AWS);
    }

    @Test
    @WithMockUser(roles = ADMIN_ROLE)
    public void shouldReturnAllCloudRegions() {
        initAclEntity(region, Collections.singletonList(new UserPermission(ADMIN_ROLE, AclPermission.READ.getMask())));
        doReturn(clouds).when(cloudRegionManager).loadAll();

        assertThat(cloudRegionApiService.loadAll()).isEqualTo(clouds);
    }

    @Test
    @WithMockUser(roles = SIMPLE_USER_ROLE)
    public void shouldFailReturningCloudRegions() {
        initAclEntity(region);
        doReturn(clouds).when(cloudRegionManager).loadAll();

        cloudRegionApiService.loadAll();

        assertThat(clouds).isEmpty();
    }

    @Test
    @WithMockUser(roles = ADMIN_ROLE)
    public void shouldReturnCloudRegion() {
        initAclEntity(region, Collections.singletonList(new UserPermission(ADMIN_ROLE, AclPermission.READ.getMask())));
        doReturn(region).when(cloudRegionManager).load(region.getId());

        assertThat(cloudRegionApiService.load(region.getId())).isEqualTo(region);
    }

    @Test(expected = AccessDeniedException.class)
    @WithMockUser(roles = SIMPLE_USER_ROLE)
    public void shouldFailReturningCloudRegion() {
        initAclEntity(region);
        doReturn(region).when(cloudRegionManager).load(region.getId());

        cloudRegionApiService.load(region.getId());

        assertThat(region).isNull();
    }
}
