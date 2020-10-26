# This code is part of Ansible, but is an independent component.
# This particular file snippet, and this file snippet only, is BSD licensed.
# Modules you write using this snippet, which is embedded dynamically by Ansible
# still belong to the author of the module, and may assign their own license
# to the complete work.
#
# (c) 2018 Red Hat Inc.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

import time

import ansible.errors
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

checkpoint_argument_spec_for_objects = dict(
    auto_publish_session=dict(type='bool'),
    wait_for_task=dict(type='bool', default=True),
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    version=dict(type='str')
)

checkpoint_argument_spec_for_facts = dict(
    version=dict(type='str')
)

checkpoint_argument_spec_for_commands = dict(
    wait_for_task=dict(type='bool', default=True),
    version=dict(type='str')
)

delete_params = ['name', 'uid', 'layer', 'exception-group-name', 'layer', 'rule-name']


# parse failure message with code and response
def parse_fail_message(code, response):
    return 'Checkpoint device returned error {0} with message {1}'.format(code, response)


# send the request to checkpoint
def send_request(connection, version, url, payload=None):
    code, response = connection.send_request('/gaia_api/' + version + url, payload)
    return code, response


# get the payload from the user parameters
def is_checkpoint_param(parameter):
    if parameter == 'auto_publish_session' or \
            parameter == 'state' or \
            parameter == 'wait_for_task' or \
            parameter == 'version':
        return False
    return True


# build the payload from the parameters which has value (not None), and they are parameter of checkpoint API as well
def get_payload_from_parameters(params):
    payload = {}
    for parameter in params:
        parameter_value = params[parameter]
        if parameter_value is not None and is_checkpoint_param(parameter):
            if isinstance(parameter_value, dict):
                payload[parameter.replace("_", "-")] = get_payload_from_parameters(parameter_value)
            elif isinstance(parameter_value, list) and len(parameter_value) != 0 and isinstance(parameter_value[0],
                                                                                                dict):
                payload_list = []
                for element_dict in parameter_value:
                    payload_list.append(get_payload_from_parameters(element_dict))
                payload[parameter.replace("_", "-")] = payload_list
            else:
                payload[parameter.replace("_", "-")] = parameter_value
    return payload


# wait for task
def wait_for_task(module, version, connection, task_id):
    task_id_payload = {'task-id': task_id}
    task_complete = False
    current_iteration = 0
    max_num_iterations = 300

    # As long as there is a task in progress
    while not task_complete and current_iteration < max_num_iterations:
        current_iteration += 1
        # Check the status of the task
        code, response = send_request(connection, version, 'show-task', task_id_payload)

        attempts_counter = 0
        while code != 200:
            if attempts_counter < 5:
                attempts_counter += 1
                time.sleep(2)
                code, response = send_request(connection, version, 'show-task', task_id_payload)
            else:
                response['message'] = "ERROR: Failed to handle asynchronous tasks as synchronous, tasks result is" \
                                      " undefined. " + response['message']
                module.fail_json(msg=parse_fail_message(code, response))

        # Count the number of tasks that are not in-progress
        completed_tasks = 0
        for task in response['tasks']:
            if task['status'] == 'failed':
                module.fail_json(msg='Task {0} with task id {1} failed. Look at the logs for more details'
                                 .format(task['task-name'], task['task-id']))
            if task['status'] == 'in progress':
                break
            completed_tasks += 1

        # Are we done? check if all tasks are completed
        if completed_tasks == len(response["tasks"]):
            task_complete = True
        else:
            time.sleep(2)  # Wait for two seconds
    if not task_complete:
        module.fail_json(msg="ERROR: Timeout. Task-id: {0}.".format(task_id_payload['task-id']))


# if user insert a specific version, we add it to the url
def get_version(module):
    return ('v' + module.params['version'] + '/') if module.params.get('version') else ''


def idempotent_api_call(module, api_call_object, ignore, keys):
    modules_params_original = module.params
    module_params_show = dict((k, v) for k, v in module.params.items() if k in keys and v is not None)
    module.params = module_params_show
    before = api_call(module=module, api_call_object="show-{0}".format(api_call_object))
    [before.pop(key) for key in ignore]

    # Run the command:
    module.params = modules_params_original
    res = api_call(module=module, api_call_object="set-{0}".format(api_call_object))
    module.params = module_params_show
    after = res.copy()
    [after.pop(key) for key in ignore]

    changed = False if before == after else True

    return {
        api_call_object.replace('-', '_'): res,
        "changed": changed
    }


def set_api_call(module, api_call_object, keys, add_params={}):
    changed = False
    module_params_show = dict((k, v) for k, v in module.params.items() if k in keys and v is not None)
    if is_delete_requested(module=module):
        api_call(module=module, api_call_object="delete-{0}".format(api_call_object))
        module.params = module_params_show
        return {}
    if not is_object_exists(module=module, api_call_object=api_call_object, keys=keys):
        current = add_api_call(module=module, api_call_object=api_call_object, keys=keys, add_params=add_params)
    elif is_change_required(module=module, api_call_object=api_call_object, keys=keys):
        current = api_call(module=module, api_call_object="set-{0}".format(api_call_object))
        changed = True
    else:
        module.params = module_params_show
        current = api_call(module=module, api_call_object="show-{0}".format(api_call_object))

    module.params = module_params_show

    return {
        api_call_object.replace('-', '_'): current,
        "changed": changed
    }


def is_delete_requested(module):
    if "state" not in module.params:
        return False
    state = module.params["state"]
    module.params.pop("state")
    return state == "absent"


def is_change_required(module, api_call_object, keys):
    modules_params_original = module.params
    module_params_input = dict((k.replace('_', '-'), v) for k, v in module.params.items() if v is not None)
    module_params_show = dict((k, v) for k, v in module.params.items() if k in keys and v is not None)
    module.params = module_params_show
    current = api_call(module=module, api_call_object="show-{0}".format(api_call_object))
    shared_items = {key: module_params_input[key] for key in module_params_input if
                    key in current and str(module_params_input[key]) == str(current[key])}
    module.params = modules_params_original
    return len(shared_items) < len(module_params_input)


def add_api_call(module, api_call_object, keys, add_params):
    modules_params_original = module.params
    [module.params.pop(key) for key in keys if key not in add_params]
    module.params.update(add_params)
    res = api_call(module=module, api_call_object="add-{0}".format(api_call_object))
    module.params = modules_params_original
    return res


def facts_api_call(module, api_call_object, keys):
    module_key_params = dict((k, v) for k, v in module.params.items() if k in keys and v is not None)

    if len(module_key_params) > 0:
        res = api_call(module=module, api_call_object="show-{0}".format(api_call_object))
    else:
        res = api_call(module=module, api_call_object="show-{0}s".format(api_call_object))
    return {
        "ansible_facts": res
    }


# handle api call
def api_call(module, api_call_object):
    payload = get_payload_from_parameters(module.params)
    connection = Connection(module._socket_path)
    version = get_version(module)
    code, response = send_request(connection, version, api_call_object, payload)
    if code != 200:
        module.fail_json(msg=parse_fail_message(code, response))

    return response


def is_object_exists(module, api_call_object, keys):
    modules_params_original = module.params
    module_params_show = dict((k, v) for k, v in module.params.items() if k in keys and v is not None)
    module.params = module_params_show
    payload = get_payload_from_parameters(module.params)
    connection = Connection(module._socket_path)
    version = get_version(module)
    code, response = send_request(connection, version, "show-{0}".format(api_call_object), payload)
    module.params = modules_params_original
    return code == 200
