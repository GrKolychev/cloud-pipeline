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

import boto3
import argparse
import pykube
import time

RUN_ID_LABEL = 'runid'
AWS_REGION_LABEL = 'aws_region'
CLOUD_REGION_LABEL = 'cloud_region'
AWS_TERMINATION_ATTEMPTS = 3


def find_instance(ec2, run_id):
    response = ec2.describe_instances(
        Filters=[
            run_id_filter(run_id),
            {
                'Name': 'instance-state-name',
                'Values': ['pending', 'running', 'rebooting']
            }
        ]
    )
    if len(response['Reservations']) > 0:
        ins_id = response['Reservations'][0]['Instances'][0]['InstanceId']
    else:
        ins_id = None
    return ins_id

def terminate_instance(ec2, run_id, ins_id):
    ec2.terminate_instances(InstanceIds=[ins_id])
    terminated_instance_id = find_instance(ec2, run_id)
    return terminated_instance_id == None

def run_id_filter(run_id):
    return {
                'Name': 'tag:Name',
                'Values': [run_id]
           }

def get_nodename(api, nodename):
    node = pykube.Node.objects(api).filter(field_selector={'metadata.name': nodename})
    if len(node.response['items']) > 0:
        return nodename
    else:
        return ''

def find_node(nodes, api):
    for nodename in nodes:
        ret_namenode = get_nodename(api, nodename)
        if ret_namenode:
            return ret_namenode
    return ''

def verify_regnode(ec2, ins_id, api):
    response = ec2.describe_instances(InstanceIds=[ins_id])
    nodename_full = response['Reservations'][0]['Instances'][0]['PrivateDnsName']
    nodename = nodename_full.split('.', 1)[0]

    ret_namenode = find_node([ins_id, nodename, nodename_full], api)    

    if not ret_namenode:
        raise RuntimeError("Failed to find Node {}".format(ins_id))
    return ret_namenode


def delete_kube_node(nodename, run_id, api):
    if nodename is None:
        nodes = pykube.Node.objects(api).filter(selector={RUN_ID_LABEL: run_id})
        if len(nodes.response['items']) > 0:
            node = nodes.response['items'][0]
            nodename = node['metadata']['name']
        else:
            raise RuntimeError("Failed to find Node for Run ID {}".format(run_id))
    if nodename is not None:
        obj = {
            "apiVersion": "v1",
            "kind": "Node",
            "metadata": {
                "name": nodename,
                "labels": {
                    "runid": run_id
                }
            }
        }
        pykube.Node(api, obj).delete()


def get_aws_region(api, run_id):
    nodes = pykube.Node.objects(api).filter(selector={RUN_ID_LABEL: run_id})
    if len(nodes.response['items']) == 0:
        raise RuntimeError('Cannot find node matching RUN ID %s' % run_id)
    node = nodes.response['items'][0]
    labels = node['metadata']['labels']
    if AWS_REGION_LABEL not in labels and CLOUD_REGION_LABEL not in labels:
        raise RuntimeError('Node %s is not labeled with AWS Region' % node['metadata']['name'])
    return labels[CLOUD_REGION_LABEL] if CLOUD_REGION_LABEL in labels else labels[AWS_REGION_LABEL]


def get_kube_api():
    api = pykube.HTTPClient(pykube.KubeConfig.from_file("~/.kube/config"))
    api.session.verify = False
    return api

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", "-kid", type=str, required=True)
    parser.add_argument("--ins_id", "-id", type=str, required=False)  # do we need?
    args, unknown = parser.parse_known_args()
    run_id = args.run_id
    api = get_kube_api()
    aws_region = get_aws_region(api, run_id)
    ec2 = boto3.client('ec2', region_name=aws_region)
    try:
        ins_id = find_instance(ec2, run_id)
    except Exception:
        ins_id = None
    if ins_id is None:
        delete_kube_node(None, run_id, api)
    else:
        try:
            nodename = verify_regnode(ec2, ins_id, api)
        except Exception:
            nodename = None

        delete_kube_node(nodename, run_id, api)
        termination_attempts = 1
        is_terminated = False
        while termination_attempts <= AWS_TERMINATION_ATTEMPTS:
            is_terminated = terminate_instance(ec2, run_id, ins_id)
            if is_terminated:
                break
            else:
                time.sleep(1)
            termination_attempts+=1
        if not is_terminated:
            raise RuntimeError("Unable to terminate {} after {} attempts".format(ins_id, termination_attempts))

if __name__ == '__main__':
    main()
