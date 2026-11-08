from __future__ import annotations

from tests.conftest import change_customer_password, login_customer


def _customer_ready(client):
    csrf, _login = login_customer(client)
    csrf = change_customer_password(client, csrf)
    consent = client.get('/api/consent').json()
    accepted = client.post(
        '/api/consent',
        headers={'Origin': 'http://testserver', 'X-CSRF-Token': csrf},
        json={
            'text_version': consent['version'],
            'request_id': 'b6a5dbcc-018b-41b8-aed5-f07a568be19a',
            'required_analytics': True,
            'push_alerts': False,
            'sms_alerts': False,
        },
    )
    assert accepted.status_code == 200, accepted.text
    return csrf


def test_retired_appliance_can_be_restored_with_version_check(client):
    csrf = _customer_ready(client)
    headers = {'Origin': 'http://testserver', 'X-CSRF-Token': csrf}
    created = client.post(
        '/api/customer/appliances',
        headers=headers,
        json={
            'name': 'Undo test fan', 'category': 'fan', 'rated_power_w': '55',
            'quantity': 1, 'duty_pct': '100', 'hours_per_day': '5',
            'days_per_week': 7, 'notes': 'temporary test item',
        },
    )
    assert created.status_code == 200, created.text
    appliance = created.json()['appliance']

    retired = client.request(
        "DELETE",
        f"/api/customer/appliances/{appliance['id']}",
        headers=headers,
        json={'action': 'retire', 'version': appliance['version']},
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()['version'] == appliance['version'] + 1
    assert all(item['id'] != appliance['id'] for item in client.get('/api/customer/appliances').json()['appliances'])

    stale = client.post(
        f"/api/customer/appliances/{appliance['id']}/restore",
        headers=headers,
        json={'version': appliance['version']},
    )
    assert stale.status_code == 409
    assert stale.json()['error']['code'] == 'version_conflict'

    restored = client.post(
        f"/api/customer/appliances/{appliance['id']}/restore",
        headers=headers,
        json={'version': retired.json()['version']},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()['appliance']['status'] == 'active'
    assert restored.json()['appliance']['version'] == retired.json()['version'] + 1
    assert any(item['id'] == appliance['id'] for item in client.get('/api/customer/appliances').json()['appliances'])


def test_restore_rejects_customer_name_collision(client):
    csrf = _customer_ready(client)
    headers = {'Origin': 'http://testserver', 'X-CSRF-Token': csrf}

    def create(name):
        return client.post('/api/customer/appliances', headers=headers, json={
            'name': name, 'category': 'fan', 'rated_power_w': '55',
            'quantity': 1, 'duty_pct': '100', 'hours_per_day': '5',
            'days_per_week': 7, 'notes': '',
        })

    first = create('Collision fan').json()['appliance']
    retired = client.request(
        "DELETE",
        f"/api/customer/appliances/{first['id']}", headers=headers,
        json={'action': 'retire', 'version': first['version']},
    )
    assert retired.status_code == 200
    assert create('Collision fan').status_code == 200

    conflict = client.post(
        f"/api/customer/appliances/{first['id']}/restore", headers=headers,
        json={'version': retired.json()['version']},
    )
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'duplicate_appliance'
