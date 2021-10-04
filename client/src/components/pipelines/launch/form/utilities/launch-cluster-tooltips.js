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

import React from 'react';
import {QuestionCircleFilled} from '@ant-design/icons';
import {Tooltip} from 'antd';

/*
 * Launch cluster tooltips.
 *
 * 4 tooltips are presented for 'Launch cluster' dialog:
 *  - Common tooltip for popup header (`CLUSTER_MODES_TOOLTIP`)
 *  - Enable grid engine tooltip for 'Cluster' tab (`ENABLE_GRID_ENGINE_TOOLTIP`)
 *  - Auto-scaled up to & default child nodes tooltips for 'Auto-scaled cluster' tab
 *    (`AUTOSCALED_CLUSTER_UP_TO_TOOLTIP`, `AUTOSCALED_CLUSTER_DEFAULT_NODES_COUNT_TOOLTIP`)
 *
 * You can use both text & markdown (html) for tooltips.
 * Tooltip won't be shown if no value is presented (`undefined`).
 */

const CLUSTER_MODES_TOOLTIP = (
  <div>
    <div>
      Cluster configuration allows you specify number of compute nodes that will process a job.
      This is useful if a job is too heavy for a single node or it uses scheduling approach to process a series of tasks across nodes.
    </div>
    <div>
      <ul type="circle" style={{listStyle: 'none', padding: 0}}>
        <li style={{marginLeft: 5}}>
          - <b>Single node</b>: no cluster will be provisioned - this is a default run configuration
        </li>
        <li style={{marginLeft: 5}}>
          - <b>Cluster</b>: a specified number of compute nodes will be created and interconnected via a shared filesystem (/common/) and SSH.
          Optionally, GridEngine can be configured for the cluster. See "Enable GridEngine" checkbox below
        </li>
        <li style={{marginLeft: 5}}>
          - <b>Autoscaling</b>: allows to startup a small cluster (even a single/master node) and then scale it up/down according to the workload.
          This mode will always setup GridEngine, as it is used to control the current jobs queue.
        </li>
      </ul>
    </div>
  </div>
);
const ENABLE_GRID_ENGINE_TOOLTIP = (
  <div>
    <div>
      Setting this checkbox will enable the <b>GridEngine</b> for the cluster, providing all the compatible command-line utilities, e.g.: <b>qsub, qstat, qhost, qconf,</b> etc.
    </div>
    <div>
      This checkbox is a convenience option for the <b>"CP_CAP_SGE=true"</b> parameter.
    </div>
  </div>
);
const ENABLE_SPARK_TOOLTIP = (
  <div>
    <div>
      Setting this checkbox will enable the <b>Apache Spark</b> for the cluster, with the access to <b>File/Object Storages</b> from the Spark Applications.
    </div>
    <div>
      This checkbox is a convenience option for the <b>"CP_CAP_SPARK=true"</b> parameter.
    </div>
  </div>
);
const ENABLE_SLURM_TOOLTIP = (
  <div>
    <div>
      Setting this checkbox will enable the <b>SLURM</b> scheduler for the cluster, providing all the compatible command-line utilities, e.g.: <b>sbatch, scancel, squeue, sinfo,</b> etc.
    </div>
    <div>
      This checkbox is a convenience option for the <b>"CP_CAP_SLURM=true"</b> parameter.
    </div>
  </div>
);
const ENABLE_KUBE_TOOLTIP = (
  <div>
    <div>
      Setting this checkbox will enable the <b>KUBERNETES</b> scheduler for the cluster.
    </div>
    <div>
      This checkbox is a convenience option for the <b>"CP_CAP_KUBE=true"</b> parameter.
    </div>
    <div>
      This also enables <b>"CP_CAP_DIND_CONTAINER"</b> and <b>"CP_CAP_SYSTEMD_CONTAINER"</b> parameters.
    </div>
  </div>
);
const AUTOSCALED_CLUSTER_UP_TO_TOOLTIP = (
  <div>
    <div>
      Defines <b>maximum number of compute nodes</b>, that can be created in the cluster (besides the master node and the "fixed" nodes, see "Default child nodes").
    </div>
    <div>
      GridEngine queue will be checked for the entries in "wait" state and new compute nodes will be spawned to schedule the jobs.
      Once the autoscaled nodes are not needed - they will terminated.
    </div>
  </div>
);
const AUTOSCALED_CLUSTER_DEFAULT_NODES_COUNT_TOOLTIP = (
  <div>
    <div>
      Defines <b>the number of compute nodes</b>, that will be created initially.
    </div>
    <div>
      These nodes will not be scaled down, even if no workload is currently running.
      It can be considered a "fixed" part of the cluster.
    </div>
    <div>
      If not set - only a master node will be available at a startup time.
    </div>
  </div>
);
const HYBRID_AUTOSCALED_CLUSTER_TOOLTIP = (
  <div>
    Compute nodes of the cluster will be created according to the jobs' requirements.
    By default, the same instance family (as the master) is used.
    But the size of the node will vary.
  </div>
);
const AUTOSCALE_PRICE_TYPE = (
  <div>
    <div>
      This is a convenience option for the <b>"CP_CAP_AUTOSCALE_PRICE_TYPE"</b> parameter.
    </div>
  </div>
);

export const LaunchClusterTooltip = {
  clusterMode: 'cluster mode',
  cluster: {
    enableGridEngine: 'enable grid engine',
    enableSpark: 'enable spark',
    enableSlurm: 'enable slurm',
    enableKube: 'enable kube'
  },
  autoScaledCluster: {
    autoScaledUpTo: 'up to',
    defaultNodesCount: 'default nodes count',
    hybridAutoScaledCluster: 'hybrid',
    autoScalePriceType: 'auto scale price type'
  }
};

const tooltips = {
  [LaunchClusterTooltip.clusterMode]:
    CLUSTER_MODES_TOOLTIP,
  [LaunchClusterTooltip.cluster.enableGridEngine]:
    ENABLE_GRID_ENGINE_TOOLTIP,
  [LaunchClusterTooltip.cluster.enableSpark]:
    ENABLE_SPARK_TOOLTIP,
  [LaunchClusterTooltip.cluster.enableSlurm]:
    ENABLE_SLURM_TOOLTIP,
  [LaunchClusterTooltip.cluster.enableKube]:
    ENABLE_KUBE_TOOLTIP,
  [LaunchClusterTooltip.autoScaledCluster.autoScaledUpTo]:
    AUTOSCALED_CLUSTER_UP_TO_TOOLTIP,
  [LaunchClusterTooltip.autoScaledCluster.defaultNodesCount]:
    AUTOSCALED_CLUSTER_DEFAULT_NODES_COUNT_TOOLTIP,
  [LaunchClusterTooltip.autoScaledCluster.hybridAutoScaledCluster]:
    HYBRID_AUTOSCALED_CLUSTER_TOOLTIP,
  [LaunchClusterTooltip.autoScaledCluster.autoScalePriceType]: AUTOSCALE_PRICE_TYPE
};

export function renderTooltip (tooltip, style) {
  if (!tooltips[tooltip]) {
    return null;
  }
  return (
    <Tooltip title={tooltips[tooltip]} overlayStyle={{fontSize: 'smaller'}}>
      <QuestionCircleFilled style={style} />
    </Tooltip>
  );
}
