#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Ansible module to manage CheckPoint Firewall (c) 2019
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = """
module: cp_gaia_vlan_interface
author: Nitzan Efrati (@nitzanefdome9)
description:
- Add, set or delete Vlan interface
short_description: Add, set or delete Vlan interface
version_added: '2.9'
options:
  comments:
    description: interface Comments.
    required: false
    type: str
  enabled:
    description: interface State.
    required: false
    type: bool
  ipv4_address:
    description: Interface IPv4 address.
    required: false
    type: str
  ipv4_mask_length:
    description: Interface IPv4 address mask length.
    required: false
    type: int
  ipv6_address:
    description: Interface IPv6 address.
    required: false
    type: str
  ipv6_autoconfig:
    description: Configure IPv6 auto-configuration.
    required: false
    type: bool
  ipv6_mask_length:
    description: Interface IPv6 address mask length.
    required: false
    type: int
  mtu:
    description: interface mtu.
    required: false
    type: int
  name:
    description: interface name.
    required: true
    type: str
  state:
    description:
      - if state=present and interface not exists, interface will be created
      - if state=present and interface exists with required changes, interface will be updated
      - if state=absent, interface will be removed
    required: false
    type: str
    default: present
    choices: [present, absent]

"""

EXAMPLES = """
- name: Create a vlan interface
  cp_gaia_vlan_interface:
    name: eth0.2
    
- name: Set vlan interface ipv4 address and mask length:
  cp_gaia_vlan_interface:
    name: eth0.2
    ipv4_address: 1.1.1.1
    ipv4_mask_length: 24
    
- name: Delete vlan interface:
  cp_gaia_vlan_interface:
    name: eth0.2
    state: absent

"""

RETURN = """
vlan_interface:
  description: The current/updated/added interface details.
  returned: state == present.
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.check_point.gaia.plugins.module_utils.checkpoint import set_api_call


def main():
    # arguments for the module:
    fields = dict(
        ipv6_address=dict(required=False, type="str"),
        ipv4_mask_length=dict(required=False, type="int"),
        name=dict(required=True, type="str"),
        ipv6_autoconfig=dict(required=False, type="bool"),
        enabled=dict(required=False, type="bool"),
        comments=dict(required=False, type="str"),
        mtu=dict(required=False, type="int"),
        ipv4_address=dict(required=False, type="str"),
        ipv6_mask_length=dict(required=False, type="int"),
        state=dict(requierd=False, type="str", default="present", choices=["present", "absent"])
    )
    module = AnsibleModule(argument_spec=fields, supports_check_mode=True)
    api_call_object = 'vlan-interface'
    keys = ["name"]
    parent_and_id = module.params["name"].split(".")
    add_params = {"parent": parent_and_id[0], "id": parent_and_id[1]}

    res = set_api_call(module=module, api_call_object=api_call_object, keys=keys, add_params=add_params)
    module.exit_json(**res)


if __name__ == "__main__":
    main()
