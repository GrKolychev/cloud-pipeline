import os
import socket
import time
import uuid
from random import randint
from time import sleep

from googleapiclient import discovery

from pipeline.autoscaling import utils

INSTANCE_USER_NAME = "pipeline"

NO_BOOT_DEVICE_NAME = 'sdb1'


class GCPInstanceProvider(object):

    def __init__(self, cloud_region):
        self.cloud_region = cloud_region
        self.project_id = os.environ["GCP_PROJECT_ID"]
        self.client = discovery.build('compute', 'v1')

    def run_instance(self, ins_type, ins_hdd, ins_img, ins_key_path, run_id, kms_encyr_key_id, kube_ip, kubeadm_token):
        ssh_pub_key = utils.read_ssh_key(ins_key_path)
        user_data_script = utils.get_user_data_script(self.cloud_region, ins_type, ins_img, kube_ip, kubeadm_token)

        allowed_networks = utils.get_networks_config(self.cloud_region)
        subnet_id = None
        network_name = None
        if allowed_networks and len(allowed_networks) > 0:
            network_num = randint(0, len(allowed_networks) - 1)
            network_name = allowed_networks.items()[network_num][0]
            subnet_id = allowed_networks.items()[network_num][1]
            utils.pipe_log('- Networks list found, subnet {} in Network {} will be used'.format(subnet_id, network_name))
        else:
            utils.pipe_log('- Networks list NOT found, default subnet in random AZ will be used')

        machine_type = 'zones/{}/machineTypes/{}'.format(self.cloud_region, ins_type)
        instance_name = "gcp-" + uuid.uuid4().hex[0:16]

        labels = {}
        for key, value in utils.get_tags(run_id).iteritems():
            labels[key.lower()] = value.lower()

        body = {
            'name': instance_name,
            'machineType': machine_type,
            'scheduling': {
                'preemptible': False
            },
            'canIpForward': True,
            'disks': [
                #TODO
                self.__get_boot_device(10, ins_img),
                self.__get_device(ins_hdd)
            ],
            'networkInterfaces': [
                {
                    'accessConfigs': [
                        {
                            'name': 'External NAT',
                            'type': 'ONE_TO_ONE_NAT'
                        }
                    ],
                    'network': 'projects/{project}/global/networks/{network}'.format(project=self.project_id,
                                                                                     network=network_name),
                    'subnetwork': 'projects/{project}/regions/us-central1/subnetworks/{subnet}'.format(
                        project=self.project_id, subnet=subnet_id)
                }
            ],

            'labels': labels,
            "metadata": {
                "items": [
                    {
                        "key": "ssh-keys",
                        "value": "{key} pipeline".format(key=ssh_pub_key)
                    },
                    {
                        "key": "startup-script",
                        "value": user_data_script
                    }

                ]
            }

        }

        response = self.client.instances().insert(
            project=self.project_id,
            zone=self.cloud_region,
            body=body).execute()

        self.wait_for_operation(response['name'])

        ip_response = self.client.instances().get(
            project=self.project_id,
            zone=self.cloud_region,
            instance=instance_name
        ).execute()

        private_ip = ip_response['networkInterfaces'][0]['networkIP']
        return instance_name, private_ip

    def find_and_tag_instance(self, old_id, new_id):
        instance = self.find_instance(old_id)
        if instance:
            labels = instance['labels']
            labels['name'] = new_id
            labels_body = {'labels': labels, 'labelFingerprint': instance['labelFingerprint']}
            reassign = self.client.instances().setLabels(
                project=self.project_id,
                zone=self.cloud_region,
                instance=instance['name'],
                body=labels_body).execute()
            self.wait_for_operation(reassign['name'])
        else:
            raise RuntimeError('Instance with id: {} not found!'.format(old_id))

    def verify_run_id(self, run_id):
        utils.pipe_log('Checking if instance already exists for RunID {}'.format(run_id))
        instance = self.find_instance(run_id)
        if instance and len(instance['networkInterfaces'][0]) > 0:
            ins_id = instance['name']
            ins_ip = instance['networkInterfaces'][0]['networkIP']
            utils.pipe_log('Found existing instance (ID: {}, IP: {}) for RunID {}\n-'.format(ins_id, ins_ip, run_id))
        else:
            ins_id = ''
            ins_ip = ''
            utils.pipe_log('No existing instance found for RunID {}\n-'.format(run_id))
        return ins_id, ins_ip

    def check_instance(self, ins_id, run_id, num_rep, time_rep):
        utils.pipe_log('Checking instance ({}) boot state'.format(ins_id))
        port = 8888
        response = self.find_instance(run_id)
        ipaddr = response['networkInterfaces'][0]['networkIP']
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        utils.pipe_log('- Waiting for instance boot up...')
        result = utils.poll_instance(sock, time_rep, ipaddr, port)
        rep = 0
        while result != 0:
            sleep(time_rep)
            result = utils.poll_instance(sock, time_rep, ipaddr, port)
            rep = utils.increment_or_fail(num_rep, rep,
                                          'Exceeded retry count ({}) for instance ({}) network check on port {}'.format(
                                              num_rep, ins_id, port))
        utils.pipe_log('Instance is booted. ID: {}, IP: {}\n-'.format(ins_id, ipaddr))

    def get_instance_names(self, ins_id):
        for instance in self.__list_instances():
            instance_name = instance['name']
            if instance_name == ins_id:
                # according to https://cloud.google.com/compute/docs/internal-dns#about_internal_dns
                return '{}.{}.c.{}.internal'.format(instance_name, self.cloud_region, self.project_id), instance_name
        return None, None

    def find_instance(self, run_id):
        items = self.__list_instances()
        if items:
            filtered = [ins for ins in items if 'labels' in ins and ins['labels']['name'] == run_id]
            if filtered and len(filtered) == 1:
                return filtered[0]
        return None

    def terminate_instance(self, ins_id):
        delete = self.client.instances().delete(
            project=self.project_id,
            zone=self.cloud_region,
            instance=ins_id).execute()

        self.wait_for_operation(delete['name'])

    def terminate_instance_by_ip(self, internal_ip):
        items = self.__list_instances()
        for instance in items:
            if instance['networkInterfaces'][0]['networkIP'] == internal_ip:
                self.terminate_instance(instance.name)

    def __list_instances(self):
        result = self.client.instances().list(
            project=self.project_id,
            zone=self.cloud_region
        ).execute()
        if 'items' in result:
            return result['items']
        else:
            return None

    def __get_boot_device(self, disk_size, image_family):
        project_and_family = image_family.split(":")
        if len(project_and_family) != 2:
            print("node_image parameter doesn't match to Google image name convention: <project>:<imageFamily>")
        return {
            'boot': True,
            'autoDelete': True,
            'deviceName': 'sda1',
            'initializeParams': {
                'diskSizeGb': disk_size,
                'diskType': 'projects/{}/zones/{}/diskTypes/pd-ssd'.format(self.project_id, self.cloud_region),
                'sourceImage': 'projects/{}/global/images/{}'.format(project_and_family[0], project_and_family[1])
            },
            'mode': 'READ_WRITE',
            'type': 'PERSISTENT'
        }

    def __get_device(self, ins_hdd):
        return {
            'boot': False,
            'autoDelete': True,
            'deviceName': NO_BOOT_DEVICE_NAME,
            'mode': 'READ_WRITE',
            'type': 'PERSISTENT',
            'initializeParams': {
                'diskSizeGb': ins_hdd,
                'diskType': 'projects/{}/zones/{}/diskTypes/pd-ssd'.format(self.project_id, self.cloud_region)
            }
        }

    def wait_for_operation(self, operation):
        while True:
            result = self.client.zoneOperations().get(
                project=self.project_id,
                zone=self.cloud_region,
                operation=operation).execute()

            if result['status'] == 'DONE':
                if 'error' in result:
                    raise Exception(result['error'])
                return result

            time.sleep(1)
