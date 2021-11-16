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

package com.epam.pipeline.acl.cluster;

import static com.epam.pipeline.security.acl.AclExpressions.ADMIN_ONLY;

import com.epam.pipeline.entity.cluster.nat.NatRoute;
import com.epam.pipeline.entity.cluster.nat.NatRoutingRulesRequest;
import com.epam.pipeline.manager.cluster.NatGatewayManager;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class NatGatewayApiService {

    private final NatGatewayManager natGatewayManager;

    @PreAuthorize(ADMIN_ONLY)
    public Set<String> resolveAddress(final String hostname) {
        return natGatewayManager.resolveAddress(hostname);
    }

    @PreAuthorize(ADMIN_ONLY)
    public List<NatRoute> registerRoutingRulesCreation(final NatRoutingRulesRequest request) {
        return natGatewayManager.registerRoutingRulesCreation(request);
    }

    @PreAuthorize(ADMIN_ONLY)
    public List<NatRoute> loadAllRoutes() {
        return natGatewayManager.loadAllRoutes();
    }

    @PreAuthorize(ADMIN_ONLY)
    public List<NatRoute> registerRoutingRulesRemoval(final NatRoutingRulesRequest request) {
        return natGatewayManager.registerRoutingRulesRemoval(request);
    }
}
