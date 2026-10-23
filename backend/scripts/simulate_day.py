#!/usr/bin/env python
"""Simulate a day through the API."""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from shifts.models import Shift

User = get_user_model()
b, _ = User.objects.get_or_create(username='sim_b', defaults={'name': 'Sim Bartender', 'role': User.BARTENDER, 'pin_hash': '1111'})
item, _ = Item.objects.get_or_create(name_en='Nile Special', defaults={'name_sw': 'Nile Special', 'category': 'beer', 'base_unit': 'bottle', 'buy_price': 2000, 'par_level': 24})
unit, _ = ItemUnit.objects.get_or_create(item=item, label='Bottle', defaults={'qty_in_base_unit': 1, 'sell_price': 3000, 'can_sell': True})

c = APIClient()
c.force_authenticate(user=b)
r = c.post('/api/v1/shifts/open/', {})
print('open', r.status_code)
sid = r.data['id']
c.post(f'/api/v1/shifts/{sid}/count/', {'type': 'OPENING', 'counts': [{'item_id': item.id, 'counted_qty': 24}]}, format='json')
c.post('/api/v1/sales/', {'shift_id': sid, 'lines': [{'item_unit_id': unit.id, 'qty': 2}], 'payments': [{'method': 'CASH', 'amount': 6000}]}, format='json')
c.post(f'/api/v1/shifts/{sid}/count/', {'type': 'CLOSING', 'counts': [{'item_id': item.id, 'counted_qty': 22}]}, format='json')
r2 = c.post(f'/api/v1/shifts/{sid}/submit/', {})
print('submit', r2.status_code)
